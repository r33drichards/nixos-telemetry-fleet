{
  description = "Three minimal NixOS nodes: IPv6, WireGuard, Comin and private node metrics";
  inputs.common.url = "path:./common";
  outputs = { self, common }: {
    checks.x86_64-linux.boot-overlay-wasm = import ./tests/boot-overlay-wasm.nix {
      pkgs = common.inputs.nixpkgs.legacyPackages.x86_64-linux;
      inherit common;
      comin = common.inputs.comin;
    };
    nixosConfigurations = {
      node1 = common.lib.mkNode { revision = self.rev or null; system = "x86_64-linux"; name = "node1"; extraModules = [ ./nodes/node1/deployment.nix ]; address = "fd42:6e69:7800::1"; };
      node2 = common.lib.mkNode { revision = self.rev or null; system = "x86_64-linux"; name = "node2"; extraModules = [ ./nodes/node2/deployment.nix ]; address = "fd42:6e69:7800::2"; telemetry = true; };
      node3 = common.lib.mkNode { revision = self.rev or null; system = "aarch64-linux"; name = "node3"; extraModules = [ ./nodes/node3/deployment.nix ]; address = "fd42:6e69:7800::3"; };
    };
  };
}
