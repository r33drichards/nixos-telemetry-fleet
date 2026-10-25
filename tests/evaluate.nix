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
  bare = n: n.services.openssh.enable && n.services.comin.enable
    && !n.services.prometheus.enable && !n.services.grafana.enable
    && !n.services.prometheus.exporters.node.enable && !n.lab.wasm.enable
    && !n.lab.wireguard && n.services.openssh.settings.PermitRootLogin == "no"
    && !n.services.openssh.settings.PasswordAuthentication;
in
assert lib.all bare profiles;
assert lib.all (n: (builtins.head n.services.comin.remotes).branches.main.name == "main" && (builtins.head n.services.comin.remotes).branches.testing.name == "") profiles;
assert lib.all (n: !n.config.services.comin.enable && !n.config.services.openssh.enable) (builtins.attrValues fleet.nixosConfigurations);
{ bareProfiles = map (n: n.system.build.toplevel.drvPath) profiles; }
