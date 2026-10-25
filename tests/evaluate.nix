let
  root = "git+file://" + toString ../.;
  fleet = builtins.getFlake root;
  lib = fleet.inputs.common.inputs.nixpkgs.lib;
  enable = name: extra: (fleet.nixosConfigurations.${name}.extendModules {
    modules = [ ({ lib, ... }: {
      lab.enable = lib.mkForce true;
      lab.hardwareApproved = lib.mkForce true;
      lab.networkApproved = lib.mkForce true;
      lab.telemetryCapacityApproved = lib.mkForce true;
    }) extra ];
  }).config;
  n1 = enable "node1" {};
  n2 = enable "node2" {};
  n3 = enable "node3" {};
  web = enable "node2" ({ lib, ... }: {
    lab.publicGrafana = lib.mkForce true;
    lab.grafanaHostname = lib.mkForce "grafana.example.invalid";
    lab.acmeEmail = lib.mkForce "operator@example.invalid";
  });
  blocked = (fleet.nixosConfigurations.node1.extendModules {
    modules = [ ({ lib, ... }: { lab.enable = lib.mkForce true; }) ];
  }).config;
in
assert lib.all (n: !n.config.services.comin.enable && !n.config.services.prometheus.exporters.node.enable) (builtins.attrValues fleet.nixosConfigurations);
assert lib.any (a: !a.assertion) blocked.assertions;
assert n1.services.prometheus.exporters.node.listenAddress == "[fd42:6e69:7800::1]";
assert fleet.nixosConfigurations.node3.pkgs.stdenv.hostPlatform.system == "aarch64-linux";
assert n2.services.prometheus.listenAddress == "127.0.0.1";
assert n2.services.grafana.settings.server.http_addr == "127.0.0.1";
assert !n2.services.grafana.settings."auth.anonymous".enabled;
assert !n2.services.caddy.enable;
assert (builtins.head n2.services.comin.remotes).branches.testing.name == "";
assert (builtins.head n2.services.comin.remotes).branches.main.operation == "switch";
assert builtins.length n2.systemd.services.grafana.serviceConfig.LoadCredential == 2;
assert web.services.caddy.enable;
assert web.services.grafana.settings.security.cookie_secure;
assert lib.all (port: !(builtins.elem port web.networking.firewall.allowedTCPPorts)) [ 3000 9090 9100 4317 4318 ];
{
  node1 = n1.system.build.toplevel.drvPath;
  node2 = n2.system.build.toplevel.drvPath;
  node3 = n3.system.build.toplevel.drvPath;
  publicHTTPS = web.system.build.toplevel.drvPath;
  leafConfigurations = builtins.listToAttrs (map (name: { inherit name; value = (builtins.getFlake (root + "?dir=nodes/" + name)).nixosConfigurations.${name}.config.system.build.toplevel.drvPath; }) [ "node1" "node2" "node3" ]);
  versions = {
    grafana = n2.services.grafana.package.version;
    prometheus = n2.services.prometheus.package.version;
    nodeExporter = fleet.nixosConfigurations.node2.pkgs.prometheus-node-exporter.version;
  };
}
