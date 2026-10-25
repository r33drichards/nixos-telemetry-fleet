{ config, lib, pkgs, ... }:
let cfg = config.lab; in {
  options.lab = {
    enable = lib.mkEnableOption "approved node services and network";
    wireguard = lib.mkEnableOption "optional WireGuard overlay";
    nodeExporter = lib.mkEnableOption "optional node metrics";
    sshSourceCIDRs = lib.mkOption { type = lib.types.listOf lib.types.str; default = []; };
    networkApproved = lib.mkOption { type = lib.types.bool; default = false; };
    hardwareApproved = lib.mkOption { type = lib.types.bool; default = false; };
    publicInterface = lib.mkOption { type = lib.types.str; default = "eth0"; };
    publicIPv6Addresses = lib.mkOption { type = lib.types.listOf lib.types.str; default = []; };
    overlayIPv6 = lib.mkOption { type = lib.types.str; };
    wireguardConfigFile = lib.mkOption { type = lib.types.str; default = "/var/lib/fleet-secrets/wg0.conf"; };
    repoURL = lib.mkOption { type = lib.types.str; default = "https://github.com/r33drichards/nixos-telemetry-fleet.git"; };
  };
  config = {
    system.stateVersion = "26.05";
    networking.enableIPv6 = true;
    networking.firewall.enable = true;
    nix.settings = { experimental-features = [ "nix-command" "flakes" ]; max-jobs = 1; cores = 1; };
    nix.gc.automatic = false; # Retain known-good boot generations during bootstrap.
    assertions = [
      { assertion = !cfg.enable || (cfg.networkApproved && cfg.hardwareApproved); message = "Approve hardware/boot/recovery and exact network before enabling nodes."; }
      { assertion = !cfg.enable || cfg.sshSourceCIDRs != []; message = "Approve explicit SSH source CIDRs before enabling the host."; }
      { assertion = !cfg.nodeExporter || cfg.wireguard; message = "Optional exporter requires the private overlay."; }
      { assertion = lib.hasPrefix "/run/" cfg.wireguardConfigFile || lib.hasPrefix "/var/lib/" cfg.wireguardConfigFile; message = "WireGuard config must remain outside the Nix store."; }
    ];
    environment.systemPackages = lib.mkIf cfg.enable ([ pkgs.curl ] ++ lib.optional cfg.wireguard pkgs.wireguard-tools);
    networking.useNetworkd = lib.mkIf cfg.enable true;
    networking.useDHCP = lib.mkIf cfg.enable false;
    systemd.network.enable = cfg.enable;
    systemd.network.networks."10-uplink" = lib.mkIf cfg.enable {
      matchConfig.Name = cfg.publicInterface;
      networkConfig = { DHCP = "ipv4"; IPv6AcceptRA = true; };
      address = cfg.publicIPv6Addresses;
    };
    # Only the directory is created declaratively; secret contents arrive out of band.
    systemd.tmpfiles.rules = lib.mkIf cfg.enable [ "d /var/lib/fleet-secrets 0700 root root -" "d /var/lib/fleet-access 0755 root root -" ];
    systemd.services.wg-quick-wg0 = lib.mkIf (cfg.enable && cfg.wireguard) {
      unitConfig.RequiresMountsFor = [ cfg.wireguardConfigFile ];
      serviceConfig.LoadCredential = [ "wg0.conf:${cfg.wireguardConfigFile}" ];
    };
    networking.wg-quick.interfaces.wg0 = lib.mkIf (cfg.enable && cfg.wireguard) {
      configFile = "/run/credentials/wg-quick-wg0.service/wg0.conf";
      autostart = true;
    };
    networking.firewall.interfaces = lib.mkIf (cfg.enable && cfg.wireguard) {
      "${cfg.publicInterface}".allowedUDPPorts = [ 51820 ];
      wg0.allowedTCPPorts = [ 9100 ];
    };
    services.prometheus.exporters.node = {
      enable = cfg.enable && cfg.nodeExporter;
      listenAddress = "[${cfg.overlayIPv6}]";
      port = 9100;
      openFirewall = false;
      enabledCollectors = [ "systemd" ];
    };
    systemd.services.prometheus-node-exporter = lib.mkIf (cfg.enable && cfg.nodeExporter) {
      after = [ "wg-quick-wg0.service" ];
      requires = [ "wg-quick-wg0.service" ];
      serviceConfig = { MemoryMax = "48M"; CPUQuota = "10%"; };
    };
    services.openssh = {
      enable = cfg.enable;
      openFirewall = false;
      settings = {
        PermitRootLogin = "no";
        PasswordAuthentication = false;
        KbdInteractiveAuthentication = false;
        AllowUsers = [ "operator" ];
        AuthorizedKeysFile = "/var/lib/fleet-access/authorized_keys";
      };
    };
    users.users.operator = lib.mkIf cfg.enable { isNormalUser = true; };
    networking.firewall.extraCommands = lib.mkIf cfg.enable (lib.concatMapStringsSep "\n" (source:
      "${if lib.hasInfix ":" source then "ip6tables" else "iptables"} -A nixos-fw -s ${lib.escapeShellArg source} -p tcp --dport 22 -j ACCEPT"
    ) cfg.sshSourceCIDRs);
    services.comin = {
      enable = cfg.enable;
      debug = false;
      repositorySubdir = "nodes/${config.networking.hostName}";
      exporter = { listen_address = "127.0.0.1"; openFirewall = false; };
      retention = { deployment_boot_entry_capacity = 5; deployment_successful_capacity = 5; deployment_any_capacity = 8; };
      buildAttemptsLimit = 2;
      evalTimeout = 600;
      buildTimeout = 1800;
      remotes = [{
        name = "origin";
        url = cfg.repoURL;
        branches.main = { name = "main"; operation = "switch"; };
        branches.testing.name = "";
        poller.period = 60;
      }];
    };
    systemd.services.comin = lib.mkIf cfg.enable {
      serviceConfig = { MemoryHigh = "256M"; MemoryMax = "512M"; CPUQuota = "50%"; Nice = 10; };
    };
  };
}
