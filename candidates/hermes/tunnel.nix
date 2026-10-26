# Proposed dedicated reverse-forward account; disabled and not imported by node2.
{ config, lib, pkgs, ... }:
let cfg = config.fleet.hermesTunnel; in {
  options.fleet.hermesTunnel.enable = lib.mkEnableOption "approved Hermes-only reverse SSH listener";
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
