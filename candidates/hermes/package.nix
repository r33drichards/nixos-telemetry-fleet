{ pkgs, hermes }:
let
  base = hermes.packages.${pkgs.stdenv.hostPlatform.system}.minimal;
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
