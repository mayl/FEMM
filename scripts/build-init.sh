#!/usr/bin/env bash
# build-init.sh — one-time setup for incremental dev builds.
#
# Run inside:  nix develop .#build
# Then:        just build-init
#
# Source tree is kept pristine. This script:
#   1. Rsyncs source → build/src/ (excluded: build/, .git/)
#   2. Applies patches to build/src/ (not the main source tree)
#   3. Creates win-stubs forwarding headers
#   4. Generates build/toolchain.cmake
#   5. Runs cmake -G Ninja -S build/src -B build
#
# After this, iterate with:
#   just sync-build          # rsync edits + ninja (typical inner loop)
#   just build               # ninja only (if no new files added)
#   just build-target fkn    # build one target

set -euo pipefail
REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
cd "$REPO_ROOT"

# ── Validate environment ──────────────────────────────────────────────────────
for var in FEMM_TOOLCHAIN_FILE FEMM_WINDOWS_SDK FEMM_MFC_SDK; do
    if [[ -z "${!var:-}" ]]; then
        echo "ERROR: $var is not set." >&2
        echo "Run this script inside:  nix develop .#build" >&2
        exit 1
    fi
done

# ── 1. Rsync source into build/src (preserves main source tree) ──────────────
echo "==> Syncing source → build/src/ ..."
mkdir -p build/src
rsync -a --delete \
    --exclude='/build/' \
    --exclude='/.git/' \
    --exclude='/.msvc-bin/' \
    --exclude='/result' \
    . build/src/

# ── 2. Apply source patches to build/src (not the main tree) ─────────────────
echo "==> Patching build/src/ ..."
(cd build/src && python3 "$REPO_ROOT/scripts/patch-sources.py")

# ── 3. Detect Windows SDK version ────────────────────────────────────────────
WINSDK_VER=$(ls "$FEMM_WINDOWS_SDK/sdk/include/" | grep '^10\.' | sort -V | tail -1)
echo "==> Windows SDK version: $WINSDK_VER"

# ── 4. Win-stubs forwarding headers ──────────────────────────────────────────
# afxocc.h uses uppercase includes (OLEBIND.H etc.) that only exist lowercase
# in the VS2022 MFC SDK. Forwarding stubs resolve them via angle-bracket includes.
WIN_STUBS="$REPO_ROOT/build/win-stubs"
mkdir -p "$WIN_STUBS"
printf '#pragma once\n#include <olebind.h>\n' > "$WIN_STUBS/OLEBIND.H"
printf '#pragma once\n#include <ocdbid.h>\n'  > "$WIN_STUBS/OCDBID.H"
printf '#pragma once\n#include <ocdb.h>\n'    > "$WIN_STUBS/OCDB.H"

# ── 5. Generate wrapper toolchain.cmake ──────────────────────────────────────
cat > build/toolchain.cmake << ENDTOOLCHAIN
include("$FEMM_TOOLCHAIN_FILE")
string(PREPEND CMAKE_C_FLAGS_INIT "/imsvc $WIN_STUBS ")
string(PREPEND CMAKE_CXX_FLAGS_INIT "/imsvc $WIN_STUBS ")
# Use static MFC (mfcs140u.lib) instead of the shared DLL (mfc140u.dll).
# This makes femm.exe self-contained under Wine — no VC++ 2022 redist needed.
# Undefine _AFXDLL (set by the base toolchain) to switch MFC headers to static mode.
# Must also switch from /MD (dynamic CRT) to /MT (static CRT): afx.h enforces
# that /MD implies _AFXDLL, and /MT allows static MFC.
string(APPEND CMAKE_C_FLAGS_INIT " /U_AFXDLL /MT")
string(APPEND CMAKE_CXX_FLAGS_INIT " /U_AFXDLL /MT")
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded" CACHE STRING "MSVC Runtime" FORCE)
# Also patch the Release-config flags that CMake initialises with /MD
set(CMAKE_C_FLAGS_RELEASE_INIT   "/O2 /Ob2 /DNDEBUG")
set(CMAKE_CXX_FLAGS_RELEASE_INIT "/O2 /Ob2 /DNDEBUG")
# Skip afxres.rc cursor/bitmap resources — in static MFC mode the backslash
# paths like "res\\help.cur" still can't be resolved by llvm-rc on Linux.
string(APPEND CMAKE_RC_FLAGS_INIT " /D_AFX_INTL_RESOURCES")
# FEMM source has duplicate sqr() definitions across translation units.
# /FORCE:MULTIPLE tells lld-link to pick the first definition (MSVC default behaviour).
string(APPEND CMAKE_EXE_LINKER_FLAGS_INIT " /FORCE:MULTIPLE")
ENDTOOLCHAIN

# ── 6. CMake configure ────────────────────────────────────────────────────────
echo "==> Running cmake configure..."
cmake -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE="$REPO_ROOT/build/toolchain.cmake" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded \
    "-DCMAKE_C_FLAGS_RELEASE=/MT /O2 /Ob2 /DNDEBUG" \
    "-DCMAKE_CXX_FLAGS_RELEASE=/MT /O2 /Ob2 /DNDEBUG" \
    -DWINSDK_VER="$WINSDK_VER" \
    -DINSTALL_BIN_DIR="$REPO_ROOT/bin" \
    -DSKIP_belasolv=OFF \
    -DSKIP_csolv=OFF \
    -DSKIP_liblua=OFF \
    -DSKIP_ResizableLib=OFF \
    -DSKIP_femm=OFF \
    -DSKIP_femmplot=ON \
    -DSKIP_fkn=OFF \
    -DSKIP_hsolv=OFF \
    -DSKIP_scifemm=ON \
    -DSKIP_triangle=OFF \
    -B build -S build/src

echo ""
echo "Done! Build configured. Now run:"
echo "  just sync-build         # rsync edits + build (typical loop)"
echo "  just build              # build only (no sync)"
echo "  just build-target fkn   # build one target"
