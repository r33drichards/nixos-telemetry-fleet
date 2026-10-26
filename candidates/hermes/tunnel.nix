# Proposed dedicated reverse-forward account; disabled and not imported by node2.
{ config, lib, pkgs, ... }:
let cfg = config.fleet.hermesTunnel; in {
  options.fleet.hermesTunnel = {
    enable = lib.mkEnableOption "approved Hermes-only reverse SSH listener";
    # Public material only. Null means deliver the key outside the store at
    # bootstrap; building the closure never requires a credential or live key.
    publicKey = lib.mkOption {
      default = null;
      type = lib.types.nullOr (lib.types.addCheck lib.types.str
        (key: builtins.match "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI[A-P][A-Za-z0-9+/]{42}" key != null));
      description = "One bare Ed25519 public key, without options/comment/newline; null for host-local delivery.";
    };
  };
  config = lib.mkIf cfg.enable {
    users.groups.hermes-tunnel = {};
    users.users.hermes-tunnel = {
      isSystemUser = true;
      group = "hermes-tunnel";
      home = "/var/empty";
      # A valid shell is needed for sshd account checks; MaxSessions prevents
      # shell, command and subsystem sessions for this account.
      shell = pkgs.bashInteractive;
    };
    systemd.tmpfiles.rules = [ "d /var/lib/fleet-access 0755 root root -" ]
      ++ lib.optional (cfg.publicKey != null)
        "C /var/lib/fleet-access/hermes-tunnel-authorized_keys 0644 root root - ${pkgs.writeText "hermes-tunnel-public-key" (cfg.publicKey + "\n")}";
    services.openssh.settings.AllowUsers = [ "hermes-tunnel" ];
    services.openssh.extraConfig = ''
      Match User hermes-tunnel
        AuthenticationMethods publickey
        PasswordAuthentication no
        KbdInteractiveAuthentication no
        AuthorizedKeysFile /var/lib/fleet-access/hermes-tunnel-authorized_keys
        AllowTcpForwarding remote
        PermitListen 127.0.0.1:16667
        PermitOpen none
        GatewayPorts no
        MaxSessions 0
        PermitTTY no
        AllowAgentForwarding no
        X11Forwarding no
        AllowStreamLocalForwarding no
        PermitTunnel no
      Match all
    '';
  };
}
