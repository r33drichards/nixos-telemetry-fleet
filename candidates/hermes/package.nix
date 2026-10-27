{ pkgs, hermes }:
let
  # Upstream uv.lock pins the official SDK and all transitive dependencies.
  # Add only Modal; do not enable other optional groups or change tool policy.
  base = hermes.packages.${pkgs.stdenv.hostPlatform.system}.minimal.override {
    extraDependencyGroups = [ "modal" ];
    # Patch only the Python source passed to the pinned upstream venv builder.
    callPackage = path: args: pkgs.callPackage path (args //
      pkgs.lib.optionalAttrs (toString path == toString (hermes + "/nix/python.nix")) {
        pythonSrc = pkgs.applyPatches {
          name = "hermes-modal-timeout-source";
          src = args.pythonSrc;
          patches = [ ./modal-timeout.patch ];
        };
      });
  };
  plugins = pkgs.runCommand "hermes-fleet-irc-plugins" { nativeBuildInputs = [ pkgs.git pkgs.python3 ]; } ''
    mkdir -p work/plugins
    cp -R ${hermes}/plugins/. work/plugins/
    chmod -R u+w work
    cd work
    git apply --unidiff-zero ${./irc-channel-policy.patch}
    python3 ${./test_irc_policy.py} --patched plugins/platforms/irc/adapter.py
    cp -R plugins "$out"
  '';
  inputs = pkgs.runCommand "hermes-fleet-agent-inputs.json" { nativeBuildInputs = [ pkgs.python3 ]; } ''
    python3 - ${base.agentInputsFile} ${plugins} "$out" <<'PY'
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
assert data['placement'] == 'references'
assert data['repo'] == 'share/hermes-agent'
data['resources']['plugins'] = sys.argv[2]
with open(sys.argv[3], 'w') as f:
    json.dump(data, f)
PY
  '';
in base.overrideAttrs (old: {
  # Replace the native assembler input; an outer environment wrapper could be
  # overwritten by the upstream launcher. Preserve its dependency graph.
  installPhase = assert pkgs.lib.hasInfix (builtins.unsafeDiscardStringContext (toString base.agentInputsFile)) old.installPhase;
    builtins.replaceStrings [ (toString base.agentInputsFile) ] [ (toString inputs) ] old.installPhase;
  passthru = (old.passthru or {}) // { fleetPlugins = plugins; fleetAgentInputs = inputs; };
})
