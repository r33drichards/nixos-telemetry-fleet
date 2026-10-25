{ config, lib, pkgs, ... }:
let
  cfg = config.lab;
  active = cfg.enable && cfg.telemetry;
in {
  options.lab = {
    telemetry = lib.mkOption { type = lib.types.bool; default = false; };
    telemetryCapacityApproved = lib.mkOption { type = lib.types.bool; default = false; };
    grafanaSecretKeyFile = lib.mkOption { type = lib.types.str; default = "/var/lib/fleet-secrets/grafana-secret-key"; };
    grafanaPasswordFile = lib.mkOption { type = lib.types.str; default = "/var/lib/fleet-secrets/grafana-admin-password"; };
    scrapeTargets = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ "[fd42:6e69:7800::2]:9100" "[fd42:6e69:7800::3]:9100" ];
    };
  };
  config = {
    assertions = [
      { assertion = !active || cfg.telemetryCapacityApproved; message = "Telemetry on 1 GiB is unmeasured; approve the resource experiment explicitly."; }
      { assertion = lib.hasPrefix "/run/" cfg.grafanaSecretKeyFile || lib.hasPrefix "/var/lib/" cfg.grafanaSecretKeyFile; message = "Grafana encryption key must remain outside the Nix store."; }
      { assertion = lib.hasPrefix "/run/" cfg.grafanaPasswordFile || lib.hasPrefix "/var/lib/" cfg.grafanaPasswordFile; message = "Grafana credential must be a runtime file outside the Nix store."; }
    ];
    services.prometheus = {
      enable = active;
      listenAddress = "127.0.0.1";
      port = 9090;
      retentionTime = "24h";
      extraFlags = [ "--storage.tsdb.retention.size=256MB" ];
      globalConfig = { scrape_interval = "60s"; evaluation_interval = "60s"; };
      scrapeConfigs = [{ job_name = "nodes"; scrape_timeout = "10s"; static_configs = [{ targets = cfg.scrapeTargets; }]; }];
    };
    services.grafana = {
      enable = active;
      settings = {
        server = { http_addr = "127.0.0.1"; http_port = 3000; domain = "localhost"; root_url = "http://localhost:3000/"; };
        security = { admin_user = "admin"; secret_key = "$__file{/run/credentials/grafana.service/secret-key}"; admin_password = "$__file{/run/credentials/grafana.service/admin-password}"; cookie_secure = false; cookie_samesite = "strict"; };
        "auth.anonymous".enabled = false;
        users.allow_sign_up = false;
        plugins.preinstall_disabled = true;
        analytics = { reporting_enabled = false; check_for_updates = false; };
      };
      provision = {
        enable = true;
        datasources.settings.datasources = [{ name = "Prometheus"; uid = "prometheus"; type = "prometheus"; access = "proxy"; url = "http://127.0.0.1:9090"; isDefault = true; editable = false; }];
        dashboards.settings.providers = [{ name = "nodes"; options.path = ./dashboards; }];
      };
    };
    systemd.services = lib.mkIf active {
      prometheus = { after = [ "wg-quick-wg0.service" ]; wants = [ "wg-quick-wg0.service" ]; serviceConfig = { MemoryHigh = "160M"; MemoryMax = "256M"; CPUQuota = "30%"; }; };
      grafana.unitConfig.RequiresMountsFor = [ cfg.grafanaPasswordFile cfg.grafanaSecretKeyFile ];
      grafana.serviceConfig = { LoadCredential = [ "admin-password:${cfg.grafanaPasswordFile}" "secret-key:${cfg.grafanaSecretKeyFile}" ]; MemoryHigh = "160M"; MemoryMax = "256M"; CPUQuota = "30%"; };
    };
  };
}
