let
  root = "git+file://" + toString ../.;
  fleet = builtins.getFlake root;
  lib = fleet.inputs.common.inputs.nixpkgs.lib;
  enable = name: (fleet.nixosConfigurations.${name}.extendModules {
    modules = [ ({ lib, ... }: {
      lab.enable = lib.mkForce true;
      lab.hardwareApproved = lib.mkForce true;
      lab.networkApproved = lib.mkForce true;
      lab.sshSourceCIDRs = [ "2001:db8::1/128" ];
    }) ];
  }).config;
  profiles = map enable [ "node2" "node3" ];
  azureBoot = n: n.virtualisation.azureImage.vmGeneration == "v2"
    && n.boot.loader.grub.enable && n.boot.loader.grub.efiSupport
    && n.boot.loader.grub.efiInstallAsRemovable && !n.boot.loader.systemd-boot.enable
    && n.fileSystems."/".device == "/dev/disk/by-label/nixos"
    && n.fileSystems."/boot".device == "/dev/disk/by-label/ESP"
    && lib.all (m: builtins.elem m n.boot.initrd.kernelModules)
      [ "hv_vmbus" "hv_netvsc" "hv_utils" "hv_storvsc" ]
    && n.services.cloud-init.enable && n.services.waagent.enable;
  bare = n: n.services.openssh.enable && n.services.comin.enable
    && !n.services.prometheus.enable && !n.services.grafana.enable
    && !n.services.prometheus.exporters.node.enable && !n.lab.wasm.enable
    && !n.lab.wireguard && n.services.openssh.settings.PermitRootLogin == "no"
    && !n.services.openssh.settings.PasswordAuthentication;
in
assert lib.all bare profiles;
# These are the actual targets Comin evaluates, not the VM boot fixture.
assert lib.all azureBoot profiles;
assert lib.all (n: n.systemd.services.comin.unitConfig.ConditionPathExists == "/var/lib/fleet-access/bootstrap-approved") profiles;
assert lib.all (name: azureBoot fleet.nixosConfigurations.${name}.config) [ "node2" "node3" ];
assert lib.all (n: (builtins.head n.services.comin.remotes).branches.main.name == "main" && (builtins.head n.services.comin.remotes).branches.testing.name == "") profiles;
assert lib.all (name: let n = fleet.nixosConfigurations.${name}; in !n.config.services.comin.enable && !n.config.services.openssh.enable) [ "node1" "node2" "node3" ];
assert !fleet.nixosConfigurations.node2-cachix.config.services.comin.enable;
assert fleet.nixosConfigurations.node2-cachix.config.services.openssh.enable;
assert fleet.nixosConfigurations.node2-cachix.config.services.cachix-agent.enable;
assert builtins.elem "/var/lib/fleet-access/cachix-approved" fleet.nixosConfigurations.node2-cachix.config.systemd.services.cachix-agent.unitConfig.ConditionPathExists;
{ bareProfiles = map (n: n.system.build.toplevel.drvPath) profiles; }
