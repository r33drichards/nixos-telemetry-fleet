{
  description = "Shared pinned IPv6/WireGuard/Comin node modules";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/da6dc0e7b26060f2f71ce3ef7088fb56ee44fa36";
  inputs.comin.url = "github:nlewo/comin/1399adecc682e557bc3ee914d929f8e20391a148";
  inputs.comin.inputs.nixpkgs.follows = "nixpkgs";
  outputs = { self, nixpkgs, comin }: {
    lib.mkNode = { system, name, address, telemetry ? false, extraModules ? [], revision ? null, azure ? builtins.elem name [ "node2" "node3" ] }: nixpkgs.lib.nixosSystem {
      inherit system;
      modules = [
        comin.nixosModules.comin ./modules/base.nix ./modules/telemetry.nix ./modules/wasm.nix
        ({ ... }: {
          networking.hostName = name;
          system.configurationRevision = revision;
          lab.overlayIPv6 = address;
          lab.telemetry = telemetry;
          services.comin.package = comin.packages.${system}.comin;
        })
      ] ++ [ (if azure then ./modules/azure-runtime.nix else ./modules/boot-fixture.nix) ] ++ extraModules;
    };
  };
}
