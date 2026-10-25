{
  description = "Minimal node3: IPv6, WireGuard and Comin";
  inputs.common.url = "path:../../common";
  outputs = { self, common }: {
    nixosConfigurations.node3 = common.lib.mkNode {
      system = "aarch64-linux";
      name = "node3";
      extraModules = [ ./deployment.nix ];
      address = "fd42:6e69:7800::3";
      telemetry = false;
    };
  };
}
