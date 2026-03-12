#!/usr/bin/env python3
"""Download MFC headers and import libraries from Visual Studio 2022 manifest.

Fetches Microsoft.VC.14.*.MFC.Headers.base and Microsoft.VC.14.*.MFC.X64.base
VSIX packages (the latest version) from the VS2022 channel manifest and
extracts them to:
  <outdir>/atlmfc/include/   - MFC/ATL headers
  <outdir>/atlmfc/lib/x64/   - MFC/ATL x64 import libraries

Usage: python3 get-mfc-sdk.py <output-dir>
"""

import json
import os
import pathlib
import re
import shutil
import sys
import urllib.request
import zipfile

CHANNEL_URL = "https://aka.ms/vs/17/release/channel"

# Patterns for the ".base" payload packages that contain actual files.
# (The non-.base entries are tiny redirector VSIXs with no content.)
HEADERS_PATTERN = re.compile(
    r"^Microsoft\.VC\.(\d+\.\d+\.\d+\.\d+)\.MFC\.Headers\.base$"
)
X64_PATTERN = re.compile(
    r"^Microsoft\.VC\.(\d+\.\d+\.\d+\.\d+)\.MFC\.X64\.base$"
)
ATL_HEADERS_PATTERN = re.compile(
    r"^Microsoft\.VC\.(\d+\.\d+\.\d+\.\d+)\.ATL\.Headers\.base$"
)
ATL_X64_PATTERN = re.compile(
    r"^Microsoft\.VC\.(\d+\.\d+\.\d+\.\d+)\.ATL\.X64\.base$"
)


def fetch_json(url):
    print(f"[get-mfc-sdk] Fetching {url}", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_file(url, dest):
    print(f"[get-mfc-sdk] Downloading {url}", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def find_catalog_url(channel):
    """Return the VS catalog manifest URL (.vsman) from the channel JSON."""
    for item in channel.get("channelItems", []):
        if item.get("type") == "Manifest":
            payloads = item.get("payloads", [])
            if payloads:
                return payloads[0]["url"]
    raise RuntimeError(
        f"No Manifest item found in channel. Keys: {list(channel.keys())}"
    )


def ver_tuple(s):
    return tuple(int(x) for x in s.split("."))


def find_mfc_packages(catalog):
    """Return packages for the highest-versioned MFC + ATL .base packages."""
    bests = {
        "MFC.Headers": (None, None),
        "MFC.X64":     (None, None),
        "ATL.Headers": (None, None),
        "ATL.X64":     (None, None),
    }
    patterns = {
        "MFC.Headers": HEADERS_PATTERN,
        "MFC.X64":     X64_PATTERN,
        "ATL.Headers": ATL_HEADERS_PATTERN,
        "ATL.X64":     ATL_X64_PATTERN,
    }

    for pkg in catalog.get("packages", []):
        pid = pkg.get("id", "")
        lang = pkg.get("language", "neutral")
        if lang not in ("neutral", None, ""):
            continue
        if not pkg.get("payloads"):
            continue
        for label, pattern in patterns.items():
            m = pattern.match(pid)
            if m:
                ver = ver_tuple(m.group(1))
                if bests[label][0] is None or ver > bests[label][0]:
                    bests[label] = (ver, pkg)

    pkgs = []
    for label, (_, pkg) in bests.items():
        if pkg is None:
            print(f"[get-mfc-sdk] ERROR: no {label}.base found", file=sys.stderr)
        else:
            print(f"[get-mfc-sdk] Selected: {pkg['id']}", file=sys.stderr)
            pkgs.append(pkg)

    return pkgs


def extract_vsix(vsix_path, outdir):
    """Extract atlmfc/ tree from a .base VSIX into outdir/atlmfc/."""
    print(f"[get-mfc-sdk] Extracting {vsix_path.name}", file=sys.stderr)
    with zipfile.ZipFile(str(vsix_path), "r") as zf:
        names = zf.namelist()
        # Files live at: Contents/VC/Tools/MSVC/<ver>/atlmfc/{include,lib/x64}/...
        # Find the prefix up to and including "atlmfc/"
        prefix = None
        for n in names:
            m = re.match(r"^(Contents/VC/Tools/MSVC/[^/]+/atlmfc)/", n)
            if m:
                prefix = m.group(1) + "/"
                break
        if prefix is None:
            print(
                f"[get-mfc-sdk] WARNING: no atlmfc/ path found in {vsix_path.name}",
                file=sys.stderr,
            )
            print("[get-mfc-sdk] First 20 entries:", file=sys.stderr)
            for n in names[:20]:
                print(f"  {n}", file=sys.stderr)
            return

        print(f"[get-mfc-sdk] atlmfc prefix: {prefix}", file=sys.stderr)
        count = 0
        for name in names:
            if not name.startswith(prefix):
                continue
            rel = name[len(prefix):]  # e.g. "include/afxwin.h"
            if not rel or rel.endswith("/"):
                continue
            dest = outdir / "atlmfc" / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(name) as src, open(dest, "wb") as dst:
                shutil.copyfileobj(src, dst)
            count += 1

    print(f"[get-mfc-sdk] Extracted {count} files from {vsix_path.name}", file=sys.stderr)


def _fix_rc_paths(include_dir):
    """Fix backslash resource paths in MFC SDK .rc files for llvm-rc on Linux.

    Files like afxres.rc use "res\\\\help.cur" (two backslashes = Windows path
    separator).  llvm-rc on Linux does not treat '\\' as a path separator, so
    the file cannot be found.  Replace every \\\\ (double backslash) with /
    in all .rc files under include_dir.
    """
    include_dir = pathlib.Path(include_dir)
    if not include_dir.exists():
        return
    double_bs = re.compile(r"\\\\")
    count = 0
    for rc in include_dir.rglob("*.rc"):
        text = rc.read_text(encoding="utf-8", errors="replace")
        new_text = double_bs.sub("/", text)
        if new_text != text:
            rc.write_text(new_text, encoding="utf-8")
            count += 1
    if count:
        print(f"[get-mfc-sdk] Fixed backslash paths in {count} RC file(s)", file=sys.stderr)


def _patch_afxmsg(include_dir):
    """Patch afxmsg_.h so message-map macros work with clang-cl.

    MSVC accepts non-static member function names without & in casts
    (e.g. static_cast<AFX_PMSG>(memberFxn)), but clang-cl requires the
    explicit address-of operator.  Replace cast arguments (memberFxn) with
    (&memberFxn), but skip #define lines to avoid corrupting macro parameter
    lists (e.g. #define ON_COMMAND(id, memberFxn) must not be changed).
    """
    afxmsg = pathlib.Path(include_dir) / "afxmsg_.h"
    if not afxmsg.exists():
        print("[get-mfc-sdk] WARNING: afxmsg_.h not found; skipping patch", file=sys.stderr)
        return
    define_re = re.compile(r"^\s*#\s*define\b")
    lines = afxmsg.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    count = 0
    patched = []
    for line in lines:
        if not define_re.match(line):
            new_line = re.sub(r"\(memberFxn\)", "(&memberFxn)", line)
            count += line.count("(memberFxn)") - new_line.count("(memberFxn)")
            line = new_line
        patched.append(line)
    afxmsg.write_text("".join(patched), encoding="utf-8")
    print(f"[get-mfc-sdk] Patched afxmsg_.h: {count} memberFxn → &memberFxn", file=sys.stderr)


def _convert_utf16_rc(include_dir):
    """Convert UTF-16 encoded .rc files to UTF-8 for llvm-rc compatibility."""
    include_dir = pathlib.Path(include_dir)
    if not include_dir.exists():
        return
    for rc in include_dir.rglob("*.rc"):
        data = rc.read_bytes()
        if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
            encoding = "utf-16-le" if data[:2] == b"\xff\xfe" else "utf-16-be"
            text = data[2:].decode(encoding)
            rc.write_text(text, encoding="utf-8")
            print(f"[get-mfc-sdk] Converted {rc.name} from UTF-16 to UTF-8", file=sys.stderr)


def add_lowercase_symlinks(directory):
    """Recursively add lowercase symlinks for mixed-case filenames."""
    directory = pathlib.Path(directory)
    if not directory.exists():
        return
    for entry in list(directory.iterdir()):
        if entry.is_dir():
            add_lowercase_symlinks(entry)
        elif entry.is_file():
            lower = entry.name.lower()
            if lower != entry.name and not (directory / lower).exists():
                (directory / lower).symlink_to(entry.name)


def create_sdk_forwarding_headers(atlmfc_include_dir):
    """Create forwarding headers for mixed-case Windows SDK #includes.

    ATL/MFC headers use Windows-convention mixed-case #include directives,
    both quoted ("OAIdl.h") and angle-bracket (<OleAuto.h>).  On a
    case-sensitive filesystem these fail when xwin only provides lowercase
    filenames.  For each missing mixed-case name, create a stub that redirects
    to the lowercase angle-bracket form, resolved via the /imsvc SDK paths.

    Must be called AFTER add_lowercase_symlinks so atlmfc files already have
    their lowercase symlinks before we check for missing names.
    """
    include_dir = pathlib.Path(atlmfc_include_dir)
    if not include_dir.exists():
        return

    # Match both quoted and angle-bracket #include directives
    include_re = re.compile(r'#\s*include\s+[<"]([^"<>/\\]+\.h)[">]')
    wanted = {}  # orig_name -> lowercase_name

    for h in include_dir.rglob("*.h"):
        try:
            content = h.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for m in include_re.finditer(content):
            name = m.group(1)
            lc = name.lower()
            if name == lc:
                continue  # already lowercase; xwin symlinks cover it
            if (include_dir / name).exists():
                continue  # already present (original or lowercase symlink)
            wanted[name] = lc

    count = 0
    for orig, lc in sorted(wanted.items()):
        fwd = include_dir / orig
        if not fwd.exists():
            fwd.write_text(f"#include <{lc}>\n", encoding="utf-8")
            count += 1

    if count:
        print(
            f"[get-mfc-sdk] Created {count} SDK forwarding headers in atlmfc/include/",
            file=sys.stderr,
        )


def main():
    if len(sys.argv) < 2:
        print("Usage: get-mfc-sdk.py <output-dir>", file=sys.stderr)
        sys.exit(1)

    outdir = pathlib.Path(sys.argv[1])
    outdir.mkdir(parents=True, exist_ok=True)

    workdir = pathlib.Path(os.environ.get("TMPDIR", "/tmp")) / "mfc-sdk-work"
    workdir.mkdir(parents=True, exist_ok=True)

    # 1. Fetch VS2022 channel manifest
    channel = fetch_json(CHANNEL_URL)

    # 2. Fetch catalog
    catalog_url = find_catalog_url(channel)
    catalog = fetch_json(catalog_url)

    # 3. Find latest MFC .base packages
    mfc_pkgs = find_mfc_packages(catalog)
    if not mfc_pkgs:
        sys.exit(1)

    # 4. Download and extract each VSIX payload
    for pkg in mfc_pkgs:
        for payload in pkg.get("payloads", []):
            fname = payload.get("fileName", "payload.vsix")
            url = payload["url"]
            dest = workdir / fname
            if not dest.exists():
                fetch_file(url, str(dest))
            extract_vsix(dest, outdir)

    # 4b. Create non-unicode → unicode compat symlinks for VS2022 which only
    #     ships unicode MFC variants (mfc140u.lib, mfcs140u.lib).  Non-unicode
    #     apps (those without _UNICODE) still request mfc140.lib via
    #     #pragma comment(lib, ...) in afx.h; we redirect to the unicode import
    #     lib, which exports all the same CStringA/CStringW symbols.
    lib_dir = outdir / "atlmfc" / "lib" / "x64"
    for u_name, ansi_name in [
        ("mfc140u.lib",  "mfc140.lib"),
        ("mfcs140u.lib", "mfcs140.lib"),
    ]:
        u_path = lib_dir / u_name
        ansi_path = lib_dir / ansi_name
        if u_path.exists() and not ansi_path.exists():
            ansi_path.symlink_to(u_name)
            print(f"[get-mfc-sdk] Symlink: {ansi_name} → {u_name}", file=sys.stderr)

    # 5a. Fix backslash resource paths in atlmfc RC files for llvm-rc on Linux.
    #     afxres.rc contains "res\\help.cur" etc.; llvm-rc on Linux does not
    #     treat '\' as a path separator, so convert \\ → /.
    _fix_rc_paths(outdir / "atlmfc" / "include")

    # 5b. Patch afxmsg_.h: MSVC accepts member-function names without & in casts,
    #    but clang-cl requires explicit &.  Change (memberFxn) → (&memberFxn).
    _patch_afxmsg(outdir / "atlmfc" / "include")

    # 6. Convert any UTF-16 encoded .rc files to UTF-8 (llvm-rc only accepts UTF-8)
    _convert_utf16_rc(outdir / "atlmfc" / "include")

    # 6. Add lowercase symlinks for case-insensitive #include compatibility
    add_lowercase_symlinks(outdir / "atlmfc" / "include")

    # 7. Create forwarding headers for mixed-case Windows SDK #includes
    #    (e.g. atliface.h does #include "OAIdl.h" but xwin provides oaidl.h)
    create_sdk_forwarding_headers(outdir / "atlmfc" / "include")

    # Verify output
    include_dir = outdir / "atlmfc" / "include"
    lib_dir = outdir / "atlmfc" / "lib" / "x64"
    errors = 0
    for label, d in [("atlmfc/include", include_dir), ("atlmfc/lib/x64", lib_dir)]:
        if not d.exists():
            print(f"[get-mfc-sdk] ERROR: {label}/ not created", file=sys.stderr)
            errors += 1
    if errors:
        sys.exit(1)

    n_headers = sum(1 for _ in include_dir.rglob("*.h"))
    n_libs = sum(1 for _ in lib_dir.glob("*.lib"))
    print(
        f"[get-mfc-sdk] Done: {n_headers} headers, {n_libs} import libs → {outdir}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
