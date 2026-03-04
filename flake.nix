{
  description = "FEMM - Finite Element Method Magnetics";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };

      wine = pkgs.wineWow64Packages.full;

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
    in
    {
      packages.${system} = {
        inherit femm;
        default = femm;
      };

      apps.${system}.test = {
        type = "app";
        program = pkgs.lib.getExe (pkgs.writeShellApplication {
          name = "femm-test";
          runtimeInputs = [ pkgs.python3 ];
          text = ''
            exec python3 ${self}/tests/runner.py \
              --flake ${self} \
              "$@"
          '';
        });
      };

      devShells.${system}.default = pkgs.mkShell {
        packages = [ pkgs.just ];
      };
    };
}
