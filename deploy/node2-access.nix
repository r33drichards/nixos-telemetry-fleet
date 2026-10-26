# Access foundation only: no deployment controller or optional application stack.
{ lib, ... }: {
  lab.enable = false;
  lab.hardwareApproved = false;
  lab.networkApproved = false;
  lab.telemetryCapacityApproved = false;
  services.openssh.enable = lib.mkForce true;
  services.openssh.openFirewall = lib.mkForce false;
  users.users.operator.isNormalUser = true;
  networking.firewall.extraCommands = ''
    ip6tables -w -C nixos-fw -s ::/0 -p tcp --dport 22 -j ACCEPT || \
      ip6tables -w -I nixos-fw 1 -s ::/0 -p tcp --dport 22 -j ACCEPT
  '';
  systemd.tmpfiles.rules = [ "d /var/lib/fleet-access 0755 root root -" ];
}
