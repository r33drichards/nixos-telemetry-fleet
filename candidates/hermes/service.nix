# Draft, not imported by node2. No tunnel, firewall, credentials or agent start.
{ config, lib, pkgs, ... }:
let cfg = config.fleet.hermes; in {
  options.fleet.hermes = {
    enable = lib.mkEnableOption "qualified hosted-model Hermes IRC gateway";
    package = lib.mkOption { type = lib.types.package; };
  };
  config = lib.mkIf cfg.enable {
    assertions = [{ assertion = !config.services.comin.enable; message = "Hermes candidate requires Comin disabled."; }];
    users.groups.hermes = {};
    users.users.hermes = {
      isSystemUser = true;
      group = "hermes";
      home = "/var/lib/hermes";
    };
    systemd.services.hermes-irc = {
      description = "Hosted-model Hermes IRC gateway";
      wantedBy = [ "multi-user.target" ];
      wants = [ "network-online.target" ];
      after = [ "network-online.target" ];
      unitConfig = {
        ConditionPathExists = [ "/var/lib/fleet-access/hermes-irc-policy-qualified" "/var/lib/fleet-access/hermes-approved" "/var/lib/fleet-access/hermes.env" "/var/lib/fleet-access/hermes-config.json" ];
        StartLimitIntervalSec = 300;
        StartLimitBurst = 3;
      };
      environment = {
        HOME = "/var/lib/hermes";
        HERMES_HOME = "/var/lib/hermes/.hermes";
        HERMES_MANAGED = "true";
      };
      preStart = ''
        ${pkgs.python3}/bin/python ${./validate-config.py} "$CREDENTIALS_DIRECTORY/config"
        install -d -m 0700 /var/lib/hermes/.hermes
        install -m 0600 "$CREDENTIALS_DIRECTORY/config" /var/lib/hermes/.hermes/config.yaml
      '';
      serviceConfig = {
        User = "hermes";
        Group = "hermes";
        StateDirectory = "hermes";
        StateDirectoryMode = "0700";
        WorkingDirectory = "/var/lib/hermes";
        EnvironmentFile = "/var/lib/fleet-access/hermes.env";
        LoadCredential = [ "config:/var/lib/fleet-access/hermes-config.json" ];
        ExecStart = "${cfg.package}/bin/hermes gateway run";
        Restart = "on-failure";
        RestartSec = "30s";
        TimeoutStopSec = "30s";
        MemoryHigh = "384M";
        MemoryMax = "512M";
        MemorySwapMax = 0;
        CPUQuota = "50%";
        TasksMax = 96;
        UMask = "0077";
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateTmp = true;
        PrivateDevices = true;
        ProtectKernelTunables = true;
        ProtectKernelModules = true;
        ProtectControlGroups = true;
        RestrictSUIDSGID = true;
        CapabilityBoundingSet = "";
        RestrictAddressFamilies = [ "AF_UNIX" "AF_INET" "AF_INET6" ];
        InaccessiblePaths = [ "/var/lib/fleet-access" ];
      };
    };
  };
}
