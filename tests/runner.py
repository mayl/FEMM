#!/usr/bin/env python3
"""
FEMM regression test runner.

Each test is a directory containing:
  sim.lua        — FEMM Lua script; must accept /lua-var=outdir=<wine_path>
                   and write key=value scalar results to outdir/results.txt
  expected.json  — baseline values and tolerances (see format below)

Usage:
  # Run specific tests:
  python3 tests/runner.py tests/inductance

  # Run all tests under tests/:
  python3 tests/runner.py

  # Update expected.json from the current simulation output:
  python3 tests/runner.py --update-baseline tests/inductance

  # Launch FEMM with a visible window for manual inspection:
  python3 tests/runner.py --interactive tests/radial_bearing

  # Show all checks (not just failures):
  python3 tests/runner.py --verbose tests/inductance

  # Override flake location (default: auto-detected as nearest ancestor with flake.nix):
  python3 tests/runner.py --flake /path/to/repo tests/inductance

expected.json format:
  {
    "description": "...",
    "baseline_date": "YYYY-MM-DD",
    "scalars": {
      "<key>": {"expected": <float>, "tol": <float>, "note": "<str>"},
      ...
    },
    "ans": {
      "A_stats": {
        "min":   {"expected": <float>, "tol": <float>},
        "max":   {"expected": <float>, "tol": <float>},
        "mean":  {"expected": <float>, "tol": <float>},
        "stdev": {"expected": <float>, "tol": <float>},
        "p10":   {"expected": <float>, "tol": <float>},
        "p90":   {"expected": <float>, "tol": <float>}
      },
      "block_values": {"expected": [<float>, ...], "tol": <float>}
    }
  }
"""

import argparse
import json
import os
import pathlib
import shutil
import statistics
import subprocess
import sys
import tempfile
import time


# ── .ans file parser ──────────────────────────────────────────────────────────

def parse_ans(path):
    """Parse a FEMM magnetics .ans file and return key features.

    Returns a dict with:
      num_nodes, num_elements,
      A_stats  (min, max, mean, stdev, p10, p90),
      block_values  (list of per-block solution scalars)
    """
    lines = pathlib.Path(path).read_text(encoding="latin-1").splitlines()

    sol_idx = next(
        i for i, l in enumerate(lines) if l.strip().startswith("[Solution]")
    )
    num_nodes = int(lines[sol_idx + 1].strip())

    A_vals = []
    for l in lines[sol_idx + 2 : sol_idx + 2 + num_nodes]:
        parts = l.split()
        A_vals.append(float(parts[2]))

    num_elements = int(lines[sol_idx + 2 + num_nodes].strip())

    post = lines[sol_idx + 3 + num_nodes + num_elements :]
    block_n = int(post[0].strip())
    block_vals = [float(post[i + 1].split()[1]) for i in range(block_n)]

    A_sorted = sorted(A_vals)
    n = len(A_sorted)

    def percentile(p):
        i = p / 100 * (n - 1)
        lo, hi = int(i), min(int(i) + 1, n - 1)
        return A_sorted[lo] + (i - lo) * (A_sorted[hi] - A_sorted[lo])

    mean = sum(A_vals) / n
    variance = sum((v - mean) ** 2 for v in A_vals) / (n - 1)

    return {
        "num_nodes": num_nodes,
        "num_elements": num_elements,
        "A_stats": {
            "min":   A_sorted[0],
            "max":   A_sorted[-1],
            "mean":  mean,
            "stdev": variance ** 0.5,
            "p10":   percentile(10),
            "p90":   percentile(90),
        },
        "block_values": block_vals,
    }


# ── results.txt parser ────────────────────────────────────────────────────────

def parse_results(path):
    """Parse key=value results.txt written by sim.lua. Returns dict of str→float."""
    result = {}
    for line in pathlib.Path(path).read_text().splitlines():
        line = line.strip()
        if "=" in line:
            k, _, v = line.partition("=")
            result[k.strip()] = float(v.strip())
    return result


# ── comparison helpers ────────────────────────────────────────────────────────

class CheckResult:
    def __init__(self, name, actual, expected, tol, passed, note=""):
        self.name = name
        self.actual = actual
        self.expected = expected
        self.tol = tol
        self.passed = passed
        self.note = note

    def __str__(self):
        status = "PASS" if self.passed else "FAIL"
        if self.tol is None:
            diff_str = f"actual={self.actual}"
        else:
            diff = abs(self.actual - self.expected)
            diff_str = f"diff={diff:.3e} tol={self.tol:.3e}"
        note = f"  # {self.note}" if self.note else ""
        return f"  {status}  {self.name}: {self.actual}  (expected {self.expected}  {diff_str}){note}"


def check_exact(name, actual, expected, note=""):
    passed = actual == expected
    return CheckResult(name, actual, expected, None, passed, note)


def check_tol(name, actual, expected, tol, note=""):
    passed = abs(actual - expected) <= tol
    return CheckResult(name, actual, expected, tol, passed, note)


# ── FEMM runner ───────────────────────────────────────────────────────────────

def find_flake(start_dir):
    """Walk up from start_dir to find a directory containing flake.nix."""
    p = pathlib.Path(start_dir).resolve()
    while p != p.parent:
        if (p / "flake.nix").exists():
            return p
        p = p.parent
    raise FileNotFoundError(f"No flake.nix found above {start_dir}")


def run_femm(flake_dir, wine_script, wine_outdir, timeout=300, interactive=False,
             femm_exe=None):
    """Run FEMM via the Nix flake wrapper. Raises on non-zero exit.

    If femm_exe is given (absolute Linux path to a built femm.exe), use the
    femm-dev wine wrapper instead of the pre-built installer.
    """
    if femm_exe:
        cmd = ["nix", "run", f"{flake_dir}#femm-dev", "--", str(femm_exe)]
    else:
        cmd = ["nix", "run", f"{flake_dir}#femm", "--"]
    if not interactive:
        cmd.append("/windowhide")
    cmd += [
        f"/lua-script={wine_script}",
        f"/lua-var=outdir={wine_outdir}",
    ]
    if interactive:
        cmd.append("/lua-var=interactive=1")
    if interactive:
        result = subprocess.run(cmd, timeout=timeout)
    else:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0 and not interactive:
        raise RuntimeError(
            f"FEMM exited with code {result.returncode}\n"
            f"stderr:\n{result.stderr}"
        )


def linux_to_wine(path):
    """Convert an absolute Linux path to a Wine Z: drive path (lowercase)."""
    return ("Z:" + str(path)).replace("/", "\\").lower()


# ── per-test logic ────────────────────────────────────────────────────────────

def run_test(test_dir, flake_dir, verbose=False, update_baseline=False, interactive=False,
             femm_exe=None):
    test_dir = pathlib.Path(test_dir).resolve()
    name = test_dir.name

    print(f"\n{'='*60}")
    print(f"Test: {name}")
    print(f"{'='*60}")

    sim_lua = test_dir / "sim.lua"
    expected_json = test_dir / "expected.json"

    if not sim_lua.exists():
        print(f"  ERROR: {sim_lua} not found")
        return False
    if not expected_json.exists() and not update_baseline and not interactive:
        print(f"  ERROR: {expected_json} not found (run with --update-baseline to create)")
        return False

    expected = json.loads(expected_json.read_text()) if expected_json.exists() else {}

    # ── set up temp workspace (all-lowercase to survive FEMM path lowercasing) ─
    # Use mkdtemp under /tmp so the path is always lowercase and always fresh.
    work_dir = pathlib.Path(tempfile.mkdtemp(prefix=f"femm_{name}_", dir="/tmp"))
    # Copy all files from the test directory (sim.lua + any data files like .fem)
    for f in test_dir.iterdir():
        if f.is_file():
            shutil.copy(f, work_dir / f.name)

    wine_script = linux_to_wine(work_dir / "sim.lua")
    wine_outdir = linux_to_wine(work_dir)

    # ── run FEMM ──────────────────────────────────────────────────────────────
    if interactive:
        print(f"  Launching FEMM interactively (window will open)...")
        print(f"  Work dir: {work_dir}")
        try:
            run_femm(flake_dir, wine_script, wine_outdir, interactive=True, femm_exe=femm_exe)
        except Exception as e:
            print(f"  FEMM session ended: {e}")
        return True

    print(f"  Running FEMM (headless)...")
    t0 = time.monotonic()
    try:
        run_femm(flake_dir, wine_script, wine_outdir, femm_exe=femm_exe)
    except Exception as e:
        print(f"  ERROR: FEMM run failed: {e}")
        return False
    elapsed = time.monotonic() - t0
    print(f"  Solver finished in {elapsed:.1f}s")

    results_file = work_dir / "results.txt"
    ans_file = work_dir / "sim.ans"

    if not results_file.exists() or results_file.stat().st_size == 0:
        print("  ERROR: results.txt missing or empty (Lua post-processing failed)")
        return False
    if not ans_file.exists():
        print("  ERROR: sim.ans not produced (solver did not run)")
        return False

    scalars = parse_results(results_file)
    ans_data = parse_ans(ans_file)

    # ── update-baseline mode ──────────────────────────────────────────────────
    if update_baseline:
        new_expected = dict(expected)
        new_expected["baseline_date"] = time.strftime("%Y-%m-%d")

        # scalars: preserve existing tols/notes, update expected values
        new_scalars = {}
        for k, v in scalars.items():
            old = expected.get("scalars", {}).get(k, {})
            new_scalars[k] = {
                "expected": v,
                "tol":  old.get("tol", abs(v) * 0.01 or 1e-9),
                "note": old.get("note", ""),
            }
        new_expected["scalars"] = new_scalars

        # ans section
        new_ans = dict(expected.get("ans", {}))
        old_stats = expected.get("ans", {}).get("A_stats", {})
        new_A_stats = {}
        for k, v in ans_data["A_stats"].items():
            old_s = old_stats.get(k, {})
            new_A_stats[k] = {
                "expected": v,
                "tol": old_s.get("tol", abs(v) * 0.01 or 1e-9),
                "note": old_s.get("note", ""),
            }
        new_ans["A_stats"] = new_A_stats
        old_bv = expected.get("ans", {}).get("block_values", {})
        new_ans["block_values"] = {
            "expected": ans_data["block_values"],
            "tol": old_bv.get("tol", 1e-6),
            "note": old_bv.get("note", ""),
        }
        new_expected["ans"] = new_ans

        expected_json.write_text(json.dumps(new_expected, indent=2))
        print(f"  Baseline updated: {expected_json}")
        return True

    # ── compare scalars ───────────────────────────────────────────────────────
    checks = []

    for key, spec in expected.get("scalars", {}).items():
        if key not in scalars:
            checks.append(CheckResult(key, None, spec["expected"], spec["tol"],
                                      False, f"key missing from results.txt"))
            continue
        checks.append(check_tol(key, scalars[key], spec["expected"], spec["tol"],
                                 spec.get("note", "")))

    # ── compare .ans features ─────────────────────────────────────────────────
    ans_spec = expected.get("ans", {})

    for stat_name, spec in ans_spec.get("A_stats", {}).items():
        checks.append(check_tol(f"ans.A_{stat_name}",
                                 ans_data["A_stats"][stat_name],
                                 spec["expected"], spec["tol"],
                                 spec.get("note", "")))

    bv_spec = ans_spec.get("block_values", {})
    if bv_spec:
        actual_bv  = ans_data["block_values"]
        expected_bv = bv_spec["expected"]
        tol_bv     = bv_spec["tol"]
        if len(actual_bv) != len(expected_bv):
            checks.append(CheckResult("ans.block_values[count]",
                                       len(actual_bv), len(expected_bv), None, False,
                                       "block count mismatch"))
        else:
            for i, (a, e) in enumerate(zip(actual_bv, expected_bv)):
                checks.append(check_tol(f"ans.block_values[{i}]", a, e, tol_bv,
                                         bv_spec.get("note", "")))

    # ── report ────────────────────────────────────────────────────────────────
    failures = [c for c in checks if not c.passed]
    if verbose or failures:
        for c in checks:
            if verbose or not c.passed:
                print(str(c))

    n_pass = sum(1 for c in checks if c.passed)
    n_fail = len(failures)
    print(f"\n  {n_pass} passed, {n_fail} failed  ({len(checks)} total checks)")

    return n_fail == 0


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="FEMM regression test runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("test_dirs", nargs="*",
                        help="Test directories to run (default: all under tests/)")
    parser.add_argument("--flake", metavar="PATH",
                        help="Path to Nix flake (default: auto-detect)")
    parser.add_argument("--femm-exe", metavar="PATH",
                        help="Path to a locally-built femm.exe; uses nix run .#femm-dev "
                             "instead of the pre-built installer")
    parser.add_argument("--update-baseline", action="store_true",
                        help="Update expected.json from current simulation output")
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="Launch FEMM with the window visible for manual inspection (skips result checking)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show all checks, not just failures")
    args = parser.parse_args()

    runner_dir = pathlib.Path(__file__).parent.resolve()

    # auto-discover tests
    if args.test_dirs:
        test_dirs = [pathlib.Path(d) for d in args.test_dirs]
    else:
        test_dirs = sorted(
            d for d in runner_dir.iterdir()
            if d.is_dir() and (d / "sim.lua").exists()
        )

    if not test_dirs:
        print("No tests found.")
        sys.exit(0)

    # find flake
    if args.flake:
        flake_dir = pathlib.Path(args.flake).resolve()
    else:
        try:
            flake_dir = find_flake(runner_dir)
        except FileNotFoundError as e:
            print(f"ERROR: {e}")
            sys.exit(1)

    femm_exe = pathlib.Path(args.femm_exe).resolve() if args.femm_exe else None

    print(f"Flake:  {flake_dir}")
    if femm_exe:
        print(f"Binary: {femm_exe} (built)")
    print(f"Tests:  {[str(d) for d in test_dirs]}")
    if args.update_baseline:
        print("Mode:   UPDATE BASELINE")

    if args.interactive and len(test_dirs) != 1:
        print("ERROR: --interactive requires exactly one test directory.")
        sys.exit(1)

    results = {}
    for test_dir in test_dirs:
        passed = run_test(
            test_dir,
            flake_dir,
            verbose=args.verbose,
            update_baseline=args.update_baseline,
            interactive=args.interactive,
            femm_exe=femm_exe,
        )
        results[test_dir.name] = passed

    # summary
    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {status}  {name}")

    if all(results.values()):
        print("\nAll tests passed.")
        sys.exit(0)
    else:
        n_fail = sum(1 for p in results.values() if not p)
        print(f"\n{n_fail} test(s) FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    main()
