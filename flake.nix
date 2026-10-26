{
  description = "Two-node Azure fleet with retained inactive node1 template: IPv6, WireGuard, Comin and private node metrics";
  inputs.common.url = "path:./common";
  inputs.hermes.url = "github:NousResearch/hermes-agent/05d7b5af1c42d524762c7ffce991c1fe1aa2adb1";
  outputs = { self, common, hermes }:
  let
    pkgs = common.inputs.nixpkgs.legacyPackages.x86_64-linux;
    hermesPackage = import ./candidates/hermes/package.nix {
      pkgs = hermes.inputs.nixpkgs.legacyPackages.x86_64-linux;
      inherit hermes;
    };
    sshPolicy = pkgs.writeShellScriptBin "fleet-check-ssh-policy"
      (builtins.readFile ./candidates/hermes/bootstrap/check-ssh-policy.sh);
    hermesHealth = pkgs.writeShellApplication {
      name = "node2-health";
      runtimeInputs = [ pkgs.systemd pkgs.openssh pkgs.gnugrep pkgs.gawk pkgs.coreutils pkgs.iproute2 sshPolicy ];
      text = builtins.readFile ./deploy/node2-hermes-health.sh;
    };
    mkHermesNode = { tunnelPublicKey ? null }: common.lib.mkNode {
      revision = self.rev or null;
      system = "x86_64-linux"; name = "node2"; address = "fd42:6e69:7800::2";
      extraModules = [ ./deploy/node2-hermes.nix ({ ... }: {
        fleet.hermes.package = hermesPackage;
        fleet.hermesTunnel.publicKey = tunnelPublicKey;
      }) ];
    };
  in {
    lib.mkNode2Hermes = mkHermesNode;
    nixosConfigurations.node2-hermes = mkHermesNode {};
    checks.x86_64-linux.hermes-tunnel = import ./tests/hermes-tunnel.nix {
      inherit pkgs;
      comin = common.inputs.comin;
    };
    checks.x86_64-linux.node2-hermes-contract = import ./tests/hermes-contract.nix {
      inherit pkgs;
      candidate = self.nixosConfigurations.node2-hermes.config;
    };
    packages.x86_64-linux.node2-hermes-deploy = pkgs.writeText "deploy.json" (builtins.toJSON {
      agents.node2 = "${self.nixosConfigurations.node2-hermes.config.system.build.toplevel}";
      rollbackScript.x86_64-linux = "${hermesHealth}/bin/node2-health";
    });
    packages.x86_64-linux.node2-hermes-bootstrap = pkgs.runCommand "node2-hermes-bootstrap-assets" {} ''
      mkdir -p "$out"
      cp ${./candidates/hermes/bootstrap/check-ssh-policy.sh} "$out/check-ssh-policy.sh"
      cp ${./candidates/hermes/bootstrap/ssh6-per-boot.sh} "$out/fleet-ssh6"
      ln -s ${hermesHealth}/bin/node2-health "$out/health"
    '';

    nixosConfigurations.node2-cachix = common.lib.mkNode {
      revision = self.rev or null;
      system = "x86_64-linux";
      name = "node2";
      address = "fd42:6e69:7800::2";
      extraModules = [ ./deploy/node2-access.nix ./deploy/cachix-node2.nix ];
    };
    checks.x86_64-linux.node2-cachix-contract = import ./tests/cachix-contract.nix {
      pkgs = common.inputs.nixpkgs.legacyPackages.x86_64-linux;
      candidate = self.nixosConfigurations.node2-cachix.config;
    };
    packages.x86_64-linux.node2-deploy = let
      pkgs = common.inputs.nixpkgs.legacyPackages.x86_64-linux;
      health = pkgs.writeShellApplication {
        name = "node2-health";
        runtimeInputs = [ pkgs.systemd pkgs.openssh pkgs.gnugrep pkgs.iproute2 ];
        text = builtins.readFile ./deploy/node2-health.sh;
      };
    in pkgs.writeText "deploy.json" (builtins.toJSON {
      agents.node2 = "${self.nixosConfigurations.node2-cachix.config.system.build.toplevel}";
      rollbackScript.x86_64-linux = "${health}/bin/node2-health";
    });
    packages.x86_64-linux.azure-node2 = import ./images/azure.nix {
      nixpkgs = common.inputs.nixpkgs; comin = common.inputs.comin;
      system = "x86_64-linux"; hostname = "node2"; revision = self.rev or null;
    };
    packages.aarch64-linux.azure-node3 = common.inputs.nixpkgs.lib.overrideDerivation (import ./images/azure.nix {
      nixpkgs = common.inputs.nixpkgs; comin = common.inputs.comin;
      system = "aarch64-linux"; hostname = "node3"; revision = self.rev or null;
    }) (_: { requiredSystemFeatures = []; });
    checks.x86_64-linux.cloud-init-ssh6 = import ./tests/cloud-init-ssh6.nix {
      pkgs = common.inputs.nixpkgs.legacyPackages.x86_64-linux;
      comin = common.inputs.comin;
    };
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
