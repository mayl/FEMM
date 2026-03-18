{
  description = "FEMM - Finite Element Method Magnetics";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.claude-code-nix.url = "github:sadjow/claude-code-nix";
  inputs.llm-agents.url = "github:numtide/llm-agents.nix";
  outputs = { self, nixpkgs, ... }@inputs:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };

      wine = pkgs.wineWow64Packages.full;

      # -----------------------------------------------------------------------
      # Pre-built FEMM (existing Wine-wrapped installer)
      # -----------------------------------------------------------------------

      femmInstaller = pkgs.fetchurl {
        url = "https://www.femm.info/wiki/Files/files.xml?action=download&file=femm42bin_x64_21Apr2019.exe";
        name = "femm42bin_x64.exe";
        sha256 = "0hr0jlpcmnni3hahrcs9drmjc6h9xyv7a7zgzz45wc5nj24lwf0p";
      };

      vcredist2008x64 = pkgs.fetchurl {
        url = "https://download.microsoft.com/download/5/D/8/5D8C65CB-C849-4025-8E95-C3966CAFD8AE/vcredist_x64.exe";
        name = "vcredist_x64_2008sp1.exe";
        sha256 = "0m46hfk78l7s725gkivnvgd5vx5235vlgiwi3r3xbd3al6j77qn5";
      };

      femm-files = pkgs.stdenv.mkDerivation {
        name = "femm-4.2";
        src = femmInstaller;
        nativeBuildInputs = [ pkgs.innoextract ];
        unpackPhase = "true";
        buildPhase = ''
          innoextract -d extracted ${femmInstaller}
        '';
        installPhase = ''
          cp -r extracted/app $out
        '';
      };

      # Extract the 64-bit MFC DLLs from the redistributable at build time
      mfc2008x64 = pkgs.stdenv.mkDerivation {
        name = "mfc2008-x64";
        src = vcredist2008x64;
        nativeBuildInputs = [ pkgs.cabextract ];
        unpackPhase = "true";
        buildPhase = ''
          cabextract -F 'vc_red.cab' ${vcredist2008x64}
          cabextract -F '*_VC90_MFC_x64*' vc_red.cab
        '';
        installPhase = ''
          mkdir -p $out
          for f in *.Microsoft_VC90_MFC_x64*; do
            # strip the version+arch suffix, keep just the dll name
            target=$(echo "$f" | sed 's/\.[0-9].*$//')
            cp "$f" "$out/$target"
          done
        '';
      };

      femm = pkgs.buildFHSEnv {
        name = "femm";
        targetPkgs = _: [ wine ];
        runScript = pkgs.writeShellScript "femm-run" ''
          export WINEPREFIX="''${XDG_DATA_HOME:-$HOME/.local/share}/femm/wine"
          mkdir -p "$WINEPREFIX/drive_c/windows/system32"
          if [ ! -f "$WINEPREFIX/.initialized" ]; then
            cp ${mfc2008x64}/*.dll "$WINEPREFIX/drive_c/windows/system32/"
            touch "$WINEPREFIX/.initialized"
          fi
          exec wine "${femm-files}/bin/femm.exe" "$@"
        '';
      };

      # Wine wrapper that accepts a femm.exe path as its first argument.
      # Usage: nix run .#femm-dev -- /path/to/femm.exe /windowhide /lua-script=...
      femm-dev = pkgs.buildFHSEnv {
        name = "femm-dev";
        targetPkgs = _: [ wine ];
        runScript = pkgs.writeShellScript "femm-dev-run" ''
          export WINEPREFIX="''${XDG_DATA_HOME:-$HOME/.local/share}/femm/wine"
          mkdir -p "$WINEPREFIX/drive_c/windows/system32"
          if [ ! -f "$WINEPREFIX/.initialized" ]; then
            cp ${mfc2008x64}/*.dll "$WINEPREFIX/drive_c/windows/system32/"
            touch "$WINEPREFIX/.initialized"
          fi
          exe="$1"; shift
          exec wine "$exe" "$@"
        '';
      };

      # -----------------------------------------------------------------------
      # Build from source: clang-cl + xwin Windows SDK + VS2022 MFC SDK
      # -----------------------------------------------------------------------

      llvmPkgs = pkgs.llvmPackages_latest;

      # Windows CRT + SDK headers/libs via xwin (fixed-output derivation)
      # Run `nix build .#femm-built` once to get the correct hash, then
      # replace pkgs.lib.fakeHash with the printed sha256-... value.
      windows-sdk = pkgs.stdenv.mkDerivation {
        name = "windows-sdk";
        outputHash = "sha256-C6lv6HS87LOu/gaA/bdcOKrTW+fkb9vWnVRRqpZHSUM=";
        outputHashMode = "recursive";
        nativeBuildInputs = [ pkgs.xwin pkgs.cacert ];
        phases = [ "buildPhase" ];
        buildPhase = ''
          export SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt
          xwin --accept-license \
               --arch x86_64 \
               --cache-dir $TMPDIR/xwin-cache \
               splat --output $out --copy
        '';
      };

      # VS2022 MFC headers + x64 import libs (fixed-output derivation)
      # Run `nix build .#femm-built` once; replace fakeHash with the printed value.
      mfc-sdk = pkgs.stdenv.mkDerivation {
        name = "mfc-sdk";
        outputHash = "sha256-fzdjfVaojLiPVzaOe8bgoHYydrlz8IxBWd5sc+UHoK4=";
        outputHashMode = "recursive";
        nativeBuildInputs = [ pkgs.python3 pkgs.cacert pkgs.unzip ];
        phases = [ "buildPhase" ];
        buildPhase = ''
          export SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt
          python3 ${./scripts/get-mfc-sdk.py} $out
        '';
      };

      # CMake cross-compilation toolchain file, generated with baked-in Nix
      # store paths.  CMake variables like ''${WINSDK_VER} are escaped so that
      # Nix does NOT interpolate them; CMake evaluates them at configure time.
      toolchain-file = pkgs.writeText "toolchain-windows-clangcl.cmake" ''
        # Cross-compile to Windows x64 using clang-cl + lld-link + xwin SDK
        # All tool and SDK paths are baked in by Nix at eval time.

        set(CMAKE_SYSTEM_NAME    Windows)
        set(CMAKE_SYSTEM_PROCESSOR AMD64)

        # Prevent CMake from trying to run test executables during configure
        set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)

        # Compiler / linker / archiver / resource compiler / manifest tool
        set(CMAKE_C_COMPILER   "${llvmPkgs.clang-unwrapped}/bin/clang-cl")
        set(CMAKE_CXX_COMPILER "${llvmPkgs.clang-unwrapped}/bin/clang-cl")
        set(CMAKE_LINKER       "${llvmPkgs.lld}/bin/lld-link")
        set(CMAKE_AR           "${llvmPkgs.llvm}/bin/llvm-lib")
        set(CMAKE_RC_COMPILER  "${llvmPkgs.llvm}/bin/llvm-rc")
        set(CMAKE_MT           "${llvmPkgs.llvm}/bin/llvm-mt")

        # Cross-compilation target triple
        set(CMAKE_C_COMPILER_TARGET   x86_64-pc-windows-msvc)
        set(CMAKE_CXX_COMPILER_TARGET x86_64-pc-windows-msvc)

        # find_* mode: never search host programs; only search sysroots for
        # libraries and headers
        set(CMAKE_FIND_ROOT_PATH "${windows-sdk}" "${mfc-sdk}")
        set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
        set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
        set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)

        # Discover the Windows SDK version at configure time (e.g. 10.0.26100.0)
        file(GLOB _sdk_subdirs
          LIST_DIRECTORIES true
          "${windows-sdk}/sdk/include/10.*"
        )
        if(NOT _sdk_subdirs)
          message(FATAL_ERROR
            "No Windows SDK 10.x directory found under ${windows-sdk}/sdk/include/")
        endif()
        list(SORT _sdk_subdirs COMPARE NATURAL ORDER DESCENDING)
        list(GET _sdk_subdirs 0 _sdk_ver_dir)
        get_filename_component(WINSDK_VER "''${_sdk_ver_dir}" NAME)
        message(STATUS "Windows SDK version detected: ''${WINSDK_VER}")

        # Include paths: /imsvc adds a system-level include path in clang-cl,
        # bypassing nixpkgs clang's nostdlibinc patch without rebuilding clang.
        string(CONCAT _compile_flags
          " /imsvc ${windows-sdk}/crt/include"
          " /imsvc ${windows-sdk}/sdk/include/''${WINSDK_VER}/ucrt"
          " /imsvc ${windows-sdk}/sdk/include/''${WINSDK_VER}/shared"
          " /imsvc ${windows-sdk}/sdk/include/''${WINSDK_VER}/um"
          " /imsvc ${mfc-sdk}/atlmfc/include"
          " /D_AFXDLL"
          " /DUNICODE /D_UNICODE"
        )
        set(CMAKE_C_FLAGS_INIT   "''${_compile_flags}")
        set(CMAKE_CXX_FLAGS_INIT "''${_compile_flags}")

        # RC compiler include paths (llvm-rc uses /I like MSVC rc.exe)
        string(CONCAT _rc_flags
          " /I ${windows-sdk}/sdk/include/''${WINSDK_VER}/um"
          " /I ${windows-sdk}/sdk/include/''${WINSDK_VER}/shared"
          " /I ${mfc-sdk}/atlmfc/include"
        )
        set(CMAKE_RC_FLAGS_INIT "''${_rc_flags}")

        # Linker library paths passed via /LIBPATH: (lld-link syntax)
        string(CONCAT _link_flags
          " /LIBPATH:${windows-sdk}/crt/lib/x86_64"
          " /LIBPATH:${windows-sdk}/sdk/lib/''${WINSDK_VER}/ucrt/x86_64"
          " /LIBPATH:${windows-sdk}/sdk/lib/''${WINSDK_VER}/um/x86_64"
          " /LIBPATH:${mfc-sdk}/atlmfc/lib/x64"
        )
        set(CMAKE_EXE_LINKER_FLAGS_INIT    "''${_link_flags}")
        set(CMAKE_SHARED_LINKER_FLAGS_INIT "''${_link_flags}")
        set(CMAKE_MODULE_LINKER_FLAGS_INIT "''${_link_flags}")

        # Pre-seed the MFC detection cache variable so find_package(MFC REQUIRED)
        # succeeds without a try_compile (which would fail cross-compiling).
        set(MFC_HAVE_MFC 1 CACHE INTERNAL "MFC headers present" FORCE)
        set(MFC_FOUND TRUE CACHE BOOL "MFC found via toolchain" FORCE)
      '';

      # Build FEMM from source using clang-cl cross-compilation.
      #
      # Incremental build strategy (run nix build with overrides to test phases):
      #   Phase 1 (current): triangle64 only — validates toolchain, no MFC
      #   Phase 2: add liblua, then fkn (thin MFC: CString, CArray, dialogs)
      #   Phase 3: add remaining solvers (belasolv, csolv, hsolv)
      #   Phase 4: add femm GUI (157 cpp files, heaviest MFC usage)
      #
      # To enable a phase, change the corresponding SKIP_* flag below to OFF.
      femm-built = pkgs.stdenv.mkDerivation {
        name = "femm-built";
        src = pkgs.lib.cleanSourceWith {
          src = ./.;
          name = "femm-source";
          # Only include files needed to compile — excludes tests/, scripts/,
          # .beads/, examples/, docs, and other non-build content so that
          # changes to those files don't trigger a full recompile.
          filter = path: _type:
            let
              rel = pkgs.lib.removePrefix (toString ./. + "/") path;
            in
            rel == "CMakeLists.txt" ||
            builtins.any
              (d: rel == d || pkgs.lib.hasPrefix (d + "/") rel)
              [
                "femm" "fkn" "belasolv" "csolv" "hsolv"
                "triangle" "triangle64" "liblua" "ResizableLib"
                "femmplot" "scifemm" "libfemm" "mathfemm"
                "bin"
              ];
        };
        nativeBuildInputs = [
          pkgs.cmake
          pkgs.ninja
          pkgs.python3
          llvmPkgs.clang-unwrapped
          llvmPkgs.lld
          llvmPkgs.llvm
        ];

        configurePhase = ''
          # Make lld-link discoverable as 'link' so clang-cl finds it when
          # targeting MSVC on a non-Windows host.
          mkdir -p $TMPDIR/msvc-bin
          ln -s ${llvmPkgs.lld}/bin/lld-link $TMPDIR/msvc-bin/link
          export PATH="$TMPDIR/msvc-bin:$PATH"

          # Apply source patches: fix case-mismatched #includes, RC files,
          # Unicode string literals, CString/fopen fixes, etc.
          # (Script shared with dev workflow: scripts/patch-sources.py)
          python3 ${./scripts/patch-sources.py}

          # Detect Windows SDK version for the -DWINSDK_VER hint
          WINSDK_VER=$(ls ${windows-sdk}/sdk/include/ \
            | grep '^10\.' | sort -V | tail -1)
          echo "Windows SDK version: $WINSDK_VER"

          # Forwarding stubs for MFC headers that exist only as lowercase in the
          # VS2022 SDK but are #include'd with uppercase names in afxocc.h.
          # The forwarding headers use angle-bracket includes so clang-cl
          # resolves them via /imsvc atlmfc/include where the lowercase originals live.
          mkdir -p $TMPDIR/win-stubs
          printf '#pragma once\n#include <olebind.h>\n'  > $TMPDIR/win-stubs/OLEBIND.H
          printf '#pragma once\n#include <ocdbid.h>\n'   > $TMPDIR/win-stubs/OCDBID.H
          printf '#pragma once\n#include <ocdb.h>\n'     > $TMPDIR/win-stubs/OCDB.H

          # Wrapper toolchain: include original (which sets FLAGS_INIT), then
          # prepend stub dir to FLAGS_INIT so it doesn't lose SDK paths.
          # Using unquoted heredoc so bash expands $TMPDIR at build time;
          # ${toolchain-file} is already a literal store path after Nix eval.
          cat > $TMPDIR/toolchain.cmake << ENDTOOLCHAIN
include("${toolchain-file}")
string(PREPEND CMAKE_C_FLAGS_INIT "/imsvc $TMPDIR/win-stubs ")
string(PREPEND CMAKE_CXX_FLAGS_INIT "/imsvc $TMPDIR/win-stubs ")
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

          cmake -G Ninja \
            -DCMAKE_TOOLCHAIN_FILE=$TMPDIR/toolchain.cmake \
            -DCMAKE_BUILD_TYPE=Release \
            -DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded \
            "-DCMAKE_C_FLAGS_RELEASE=/MT /O2 /Ob2 /DNDEBUG" \
            "-DCMAKE_CXX_FLAGS_RELEASE=/MT /O2 /Ob2 /DNDEBUG" \
            -DWINSDK_VER="$WINSDK_VER" \
            -DINSTALL_BIN_DIR="$out/bin" \
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

        '';
        buildPhase = "ninja -C build";
        installPhase = ''
          mkdir -p $out/bin
          ninja -C build install
          cp bin/*.dat $out/bin/
        '';
      };

      # ── Test runner helper ─────────────────────────────────────────────────
      # mkTestRunner femm_exe_arg: returns a shell application that invokes
      # tests/runner.py with an optional --femm-exe pre-filled.
      # Pass "" to omit --femm-exe (uses the downloaded installer binary).
      mkTestRunner = { name, femmeExeArg ? "" }:
        pkgs.writeShellApplication {
          inherit name;
          runtimeInputs = [ pkgs.python3 ];
          text = ''
            exec python3 ${self}/tests/runner.py \
              --flake ${self} \
              ${pkgs.lib.optionalString (femmeExeArg != "") "--femm-exe ${femmeExeArg}"} \
              "$@"
          '';
        };

    in
    {
      packages.${system} = {
        inherit femm femm-built femm-dev;
        default = femm;
      };

      apps.${system} = {
        femm-dev = {
          type = "app";
          program = pkgs.lib.getExe femm-dev;
        };
        test = {
          type = "app";
          program = pkgs.lib.getExe (mkTestRunner { name = "femm-test"; });
        };
        # Run regression tests against the from-source build in one shot:
        #   nix run .#test-femm-built
        #   nix run .#test-femm-built -- --interactive tests/inductance
        test-femm-built = {
          type = "app";
          program = pkgs.lib.getExe (mkTestRunner {
            name = "femm-test-built";
            femmeExeArg = "${femm-built}/bin/femm.exe";
          });
        };
      };

      devShells.${system} = {
        default = pkgs.mkShell {
          packages = [
            pkgs.just
            inputs.llm-agents.packages.${system}.beads
            inputs.claude-code-nix.packages.${system}.default
          ];
        };

        # ── Incremental build shell ─────────────────────────────────────────
        # Usage:  nix develop .#build
        # Then:   just build-init   (once, applies patches + cmake configure)
        #         just build        (incremental ninja rebuild)
        build = pkgs.mkShell {
          packages = [
            pkgs.cmake
            pkgs.ninja
            pkgs.python3
            llvmPkgs.clang-unwrapped
            llvmPkgs.lld
            llvmPkgs.llvm
            pkgs.just
            inputs.llm-agents.packages.${system}.beads
            inputs.claude-code-nix.packages.${system}.default
          ];
          shellHook = ''
            # Make lld-link discoverable as 'link' (clang-cl linker name on non-Windows)
            MSVC_BIN="$PWD/.msvc-bin"
            mkdir -p "$MSVC_BIN"
            ln -sf ${llvmPkgs.lld}/bin/lld-link "$MSVC_BIN/link"
            export PATH="$MSVC_BIN:$PATH"

            # Expose Nix store paths so scripts/build-init.sh can reference them
            export FEMM_TOOLCHAIN_FILE="${toolchain-file}"
            export FEMM_WINDOWS_SDK="${windows-sdk}"
            export FEMM_MFC_SDK="${mfc-sdk}"

            echo "FEMM build shell ready."
            echo "  Run: just build-init   (first time, patches sources + cmake configure)"
            echo "  Run: just build        (incremental ninja build)"
          '';
        };
      };
    };
}
