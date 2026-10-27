{
  description = "Unactivated Hermes IRC candidate; upstream native Nix package";
  inputs.hermes.url = "github:NousResearch/hermes-agent/05d7b5af1c42d524762c7ffce991c1fe1aa2adb1";
  outputs = { self, hermes }:
    let
      system = "x86_64-linux";
      pkgs = hermes.inputs.nixpkgs.legacyPackages.${system};
      package = import ./package.nix { inherit pkgs hermes; };
    in {
      packages.${system}.default = package;
      checks.${system}.packaged-modal-sdk = pkgs.runCommand "hermes-packaged-modal-sdk" {} ''
        export HOME="$TMPDIR/home"
        export HERMES_HOME="$HOME/.hermes"
        mkdir -p "$HERMES_HOME"
        ${package.hermesVenv}/bin/python3 ${./test_modal_sdk.py}
        touch "$out"
      '';
      checks.${system}.packaged-irc-policy = pkgs.runCommand "hermes-packaged-irc-policy" {
        nativeBuildInputs = [ pkgs.python3 ];
      } ''
        test "$(readlink ${package}/share/hermes-agent/plugins)" = "${package.fleetPlugins}"
        python3 ${./test_irc_policy.py} --patched ${package}/share/hermes-agent/plugins/platforms/irc/adapter.py
        python3 - ${package}/command-map.json ${package} <<'PY'
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
assert data['env']['HERMES_BUNDLED_PLUGINS'] == sys.argv[2] + '/share/hermes-agent/plugins'
PY
        touch "$out"
      '';
      nixosModules.default = { pkgs, ... }: {
        imports = [ ./service.nix ];
        fleet.hermes.package = import ./package.nix { inherit pkgs hermes; };
      };
    };
}
