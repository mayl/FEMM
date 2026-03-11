# justfile — common tasks for the FEMM Nix/Wine project
# Run with: just <recipe>   (install just via `nix shell nixpkgs#just`)

# List available recipes
default:
    @just --list

# ── FEMM GUI ────────────────────────────────────────────────────────────────

# Launch FEMM interactively (opens the GUI)
femm *args:
    nix run .#femm -- {{args}}

# Launch FEMM with a Lua script but leave the window open for inspection.
# Usage: just femm-script path/to/script.lua
femm-script script:
    #!/usr/bin/env bash
    wine_path="Z:$(realpath {{script}} | tr '/' '\\' | tr '[:upper:]' '[:lower:]')"
    nix run .#femm -- "/lua-script=$wine_path"

# ── Regression tests ────────────────────────────────────────────────────────

# Run all regression tests (exit 0 on pass, 1 on failure)
test:
    nix run .#test

# Run tests and show all 29 checks, not just failures
test-verbose:
    nix run .#test -- --verbose

# Re-run simulations and update expected.json baselines.
# Use this after intentional geometry/material/solver changes to accept
# new values as the new ground truth.
test-update:
    nix run .#test -- --update-baseline

# Run a single named test, e.g.: just test-one inductance
test-one name:
    nix run .#test -- tests/{{name}}

# Run a single test verbosely
test-one-verbose name:
    nix run .#test -- --verbose tests/{{name}}

# ── Incremental source build (run inside: nix develop .#build) ───────────────
#
# Workflow:
#   nix develop .#build        # enter build shell (once per terminal)
#   just build-init            # first time: rsync + patch + cmake configure
#   <edit source files>
#   just sync-build            # rsync edits to build/src + ninja (inner loop)
#   just build-target fkn      # build a single target instead

# One-time setup: rsync source → build/src, apply patches, cmake configure
build-init:
    bash scripts/build-init.sh

# Sync source edits to build/src then build (typical iteration loop)
sync-build:
    rsync -a --delete \
        --exclude='/build/' --exclude='/.git/' \
        --exclude='/.msvc-bin/' --exclude='/result' \
        . build/src/
    cd build/src && python3 ../../scripts/patch-sources.py
    ninja -C build

# Build without syncing (safe if only existing files were edited)
build:
    ninja -C build

# Build a specific target, e.g.: just build-target fkn
build-target target:
    ninja -C build {{target}}

# Remove build tree (forces full reconfigure on next build-init)
build-clean:
    rm -rf build .msvc-bin
