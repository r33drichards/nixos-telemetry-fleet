{
  description = "Two-node Azure fleet with retained inactive node1 template: IPv6, WireGuard, Comin and private node metrics";
  inputs.common.url = "path:./common";
  outputs = { self, common }: {
    packages.x86_64-linux.azure-node2 = import ./images/azure.nix {
      nixpkgs = common.inputs.nixpkgs; comin = common.inputs.comin;
      system = "x86_64-linux"; hostname = "node2"; revision = self.rev or null;
    };
    packages.aarch64-linux.azure-node3 = (import ./images/azure.nix {
      nixpkgs = common.inputs.nixpkgs; comin = common.inputs.comin;
      system = "aarch64-linux"; hostname = "node3"; revision = self.rev or null;
    }).overrideAttrs (_: { requiredSystemFeatures = []; });
    checks.x86_64-linux.boot-ssh-comin = import ./tests/boot-ssh-comin.nix {
      pkgs = common.inputs.nixpkgs.legacyPackages.x86_64-linux;
      comin = common.inputs.comin;
    };
    legacyPackages.x86_64-linux.boot-overlay-wasm = import ./tests/boot-overlay-wasm.nix {
      pkgs = common.inputs.nixpkgs.legacyPackages.x86_64-linux;
      inherit common;
      comin = common.inputs.comin;
    };
    legacyPackages.x86_64-linux.boot-overlay-wasm-1gib = import ./tests/boot-overlay-wasm.nix {
      pkgs = common.inputs.nixpkgs.legacyPackages.x86_64-linux;
      inherit common;
      comin = common.inputs.comin;
      memoryMiB = 1024;
      qualifyTelemetry = true;
    };
    nixosConfigurations = {
      node1 = common.lib.mkNode { revision = self.rev or null; system = "x86_64-linux"; name = "node1"; extraModules = [ ./nodes/node1/deployment.nix ]; address = "fd42:6e69:7800::1"; };
      node2 = common.lib.mkNode { revision = self.rev or null; system = "x86_64-linux"; name = "node2"; extraModules = [ ./nodes/node2/deployment.nix ]; address = "fd42:6e69:7800::2"; telemetry = false; };
      node3 = common.lib.mkNode { revision = self.rev or null; system = "aarch64-linux"; name = "node3"; extraModules = [ ./nodes/node3/deployment.nix ]; address = "fd42:6e69:7800::3"; };
    };
  };
}
