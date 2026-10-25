{
  description = "Minimal node2: IPv6, WireGuard and Comin";
  inputs.common.url = "path:../../common";
  outputs = { self, common }: {
    nixosConfigurations.node2 = common.lib.mkNode {
      system = "x86_64-linux";
      name = "node2";
      extraModules = [ ./deployment.nix ];
      address = "fd42:6e69:7800::2";
      telemetry = true;
    };
  };
}
