{ config, lib, pkgs, ... }:
let cfg = config.lab; in {
  options.lab = {
    enable = lib.mkEnableOption "approved node services and network";
    networkApproved = lib.mkOption { type = lib.types.bool; default = false; };
    hardwareApproved = lib.mkOption { type = lib.types.bool; default = false; };
    publicInterface = lib.mkOption { type = lib.types.str; default = "eth0"; };
    publicIPv6Addresses = lib.mkOption { type = lib.types.listOf lib.types.str; default = []; };
    overlayIPv6 = lib.mkOption { type = lib.types.str; };
    wireguardConfigFile = lib.mkOption { type = lib.types.str; default = "/run/secrets/wg0.conf"; };
    repoURL = lib.mkOption { type = lib.types.str; default = "https://github.com/r33drichards/nixos-telemetry-fleet.git"; };
  };
  config = {
    system.stateVersion = "26.05";
    # Evaluation fixture. Replace with tested hardware module before enabling.
    boot.loader.systemd-boot.enable = lib.mkDefault true;
    fileSystems."/" = lib.mkDefault { device = "/dev/disk/by-label/nixos"; fsType = "ext4"; };
    fileSystems."/boot" = lib.mkDefault { device = "/dev/disk/by-label/ESP"; fsType = "vfat"; };
    networking.enableIPv6 = true;
    networking.firewall.enable = true;
    nix.settings = { experimental-features = [ "nix-command" "flakes" ]; max-jobs = 1; cores = 1; };
    nix.gc.automatic = false; # Retain known-good boot generations during bootstrap.
    assertions = [
      { assertion = !cfg.enable || (cfg.networkApproved && cfg.hardwareApproved); message = "Approve hardware/boot/recovery and exact network before enabling nodes."; }
      { assertion = lib.hasPrefix "/run/" cfg.wireguardConfigFile || lib.hasPrefix "/var/lib/" cfg.wireguardConfigFile; message = "WireGuard config must remain outside the Nix store."; }
    ];
    networking.useNetworkd = lib.mkIf cfg.enable true;
    networking.useDHCP = lib.mkIf cfg.enable false;
    systemd.network.enable = cfg.enable;
    systemd.network.networks."10-uplink" = lib.mkIf cfg.enable {
      matchConfig.Name = cfg.publicInterface;
      networkConfig = { DHCP = "ipv4"; IPv6AcceptRA = true; };
      address = cfg.publicIPv6Addresses;
    };
    networking.wg-quick.interfaces.wg0 = lib.mkIf cfg.enable {
      configFile = cfg.wireguardConfigFile;
      autostart = true;
    };
    networking.firewall.interfaces = lib.mkIf cfg.enable {
      "${cfg.publicInterface}".allowedUDPPorts = [ 51820 ];
      wg0.allowedTCPPorts = [ 9100 ];
    };
    services.prometheus.exporters.node = {
      enable = cfg.enable;
      listenAddress = "[${cfg.overlayIPv6}]";
      port = 9100;
      openFirewall = false;
      enabledCollectors = [ "systemd" ];
    };
    systemd.services.prometheus-node-exporter = lib.mkIf cfg.enable {
      after = [ "wg-quick-wg0.service" ];
      requires = [ "wg-quick-wg0.service" ];
      serviceConfig = { MemoryMax = "48M"; CPUQuota = "10%"; };
    };
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
