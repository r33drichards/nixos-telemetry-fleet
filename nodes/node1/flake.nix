{
  description = "Minimal node1: IPv6, WireGuard and Comin";
  inputs.common.url = "path:../../common";
  outputs = { self, common }: {
    nixosConfigurations.node1 = common.lib.mkNode {
      revision = self.rev or null;
      system = "x86_64-linux";
      name = "node1";
      extraModules = [ ./deployment.nix ];
      address = "fd42:6e69:7800::1";
      telemetry = false;
    };
  };
}
