#!/usr/bin/env bash
# build-init.sh — one-time setup for incremental dev builds.
#
# Run inside:  nix develop .#build
# Then:        just build-init
#
# What it does:
#   1. Applies source patches (scripts/patch-sources.py) — idempotent
#   2. Creates win-stubs forwarding headers (for afxocc.h uppercase includes)
#   3. Generates build/toolchain.cmake wrapping the Nix-baked toolchain file
#   4. Runs cmake -G Ninja to configure the build tree
#
# After this, iterate with:  ninja -C build [target]
# or:                         just build [target]

set -euo pipefail
cd "$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"

# ── Validate environment ──────────────────────────────────────────────────────
for var in FEMM_TOOLCHAIN_FILE FEMM_WINDOWS_SDK FEMM_MFC_SDK; do
    if [[ -z "${!var:-}" ]]; then
        echo "ERROR: $var is not set." >&2
        echo "Run this script inside:  nix develop .#build" >&2
        exit 1
    fi
done

# ── 1. Apply source patches ───────────────────────────────────────────────────
echo "==> Patching sources..."
python3 scripts/patch-sources.py

# ── 2. Detect Windows SDK version ────────────────────────────────────────────
WINSDK_VER=$(ls "$FEMM_WINDOWS_SDK/sdk/include/" | grep '^10\.' | sort -V | tail -1)
echo "==> Windows SDK version: $WINSDK_VER"

# ── 3. Win-stubs forwarding headers ──────────────────────────────────────────
# afxocc.h uses uppercase includes (OLEBIND.H etc.) that only exist lowercase
# in the VS2022 MFC SDK. Forwarding stubs resolve them via angle-bracket includes.
WIN_STUBS="$PWD/build/win-stubs"
mkdir -p "$WIN_STUBS"
printf '#pragma once\n#include <olebind.h>\n' > "$WIN_STUBS/OLEBIND.H"
printf '#pragma once\n#include <ocdbid.h>\n'  > "$WIN_STUBS/OCDBID.H"
printf '#pragma once\n#include <ocdb.h>\n'    > "$WIN_STUBS/OCDB.H"

# ── 4. Generate wrapper toolchain.cmake ──────────────────────────────────────
mkdir -p build
cat > build/toolchain.cmake << ENDTOOLCHAIN
include("$FEMM_TOOLCHAIN_FILE")
string(PREPEND CMAKE_C_FLAGS_INIT "/imsvc $WIN_STUBS ")
string(PREPEND CMAKE_CXX_FLAGS_INIT "/imsvc $WIN_STUBS ")
ENDTOOLCHAIN

# ── 5. CMake configure ────────────────────────────────────────────────────────
echo "==> Running cmake configure..."
cmake -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE="$PWD/build/toolchain.cmake" \
    -DCMAKE_BUILD_TYPE=Release \
    -DWINSDK_VER="$WINSDK_VER" \
    -DINSTALL_BIN_DIR="$PWD/bin" \
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
    -B build -S .

echo ""
echo "Done! Build configured. Now run:"
echo "  just build              # full build"
echo "  just build-target fkn   # build one target"
