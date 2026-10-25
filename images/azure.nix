{ nixpkgs, comin, system, hostname, revision ? null }:
(nixpkgs.lib.nixosSystem {
  inherit system;
  modules = [
    comin.nixosModules.comin
    ../common/modules/base.nix
    ../common/modules/azure-runtime.nix
    ({ config, lib, pkgs, modulesPath, ... }: {
      networking.hostName = hostname;
      system.configurationRevision = revision;
      virtualisation.diskSize = 8192; # Build closure exceeded 4 GiB; no cloud disk is allocated here.
      lab.overlayIPv6 = if hostname == "node2" then "fd42:6e69:7800::2" else "fd42:6e69:7800::3";
      # Image preparation is not network/deployment approval. SSH ingress stays closed.
      lab.enable = false;
      services.openssh.enable = lib.mkForce true;
      services.openssh.openFirewall = lib.mkForce false;
      services.openssh.settings.PermitRootLogin = lib.mkForce "no";
      users.users.operator.isNormalUser = true;
      services.comin.enable = lib.mkForce true;
      services.comin.package = comin.packages.${system}.comin;
      # The exact leaf is fixed; main intentionally remains a moving update target.
      services.comin.repositorySubdir = lib.mkForce "nodes/${hostname}";
      systemd.services.comin.unitConfig.ConditionPathExists = "/var/lib/fleet-access/bootstrap-approved";
      systemd.tmpfiles.rules = [ "d /var/lib/fleet-access 0755 root root -" ];
      environment.etc."fleet-image.json".text = builtins.toJSON {
        inherit hostname system revision;
        repository = "https://github.com/r33drichards/nixos-telemetry-fleet.git";
        repositorySubdir = "nodes/${hostname}";
        branch = "main";
        imageBoot = "Gen2 UEFI, unsigned upstream boot chain; NOT Trusted Launch qualified";
        deploymentApproved = false;
      };
      # Native ARM hosted runners lack KVM. TCG is only for image construction.
      nixpkgs.overlays = lib.optional (system == "aarch64-linux") (final: prev: {
        vmTools = prev.vmTools.override {
          customQemu = "${prev.qemu}/bin/qemu-system-aarch64 -machine virt -cpu max -accel tcg";
        };
      });
    })
  ];
}).config.system.build.azureImage
