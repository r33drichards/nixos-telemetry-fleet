# Bare Azure canary: preserve access and Comin across image -> leaf activation.
# The root-owned marker is a separate privileged activation gate, not in Git.
{ lib, ... }: {
  lab.enable = false; # Do not activate the older aggregate/optional profile.
  lab.hardwareApproved = false;
  lab.networkApproved = false;
  lab.telemetryCapacityApproved = false;

  services.openssh.enable = lib.mkForce true;
  services.openssh.openFirewall = lib.mkForce false;
  users.users.operator.isNormalUser = true;
  # base.nix retains operator-only public-key auth and the host-local key file.
  networking.firewall.extraCommands = ''
    ip6tables -w -C nixos-fw -s ::/0 -p tcp --dport 22 -j ACCEPT || \
      ip6tables -w -I nixos-fw 1 -s ::/0 -p tcp --dport 22 -j ACCEPT
  '';
  services.comin.enable = lib.mkForce true;
  # azure-runtime.nix keeps the existing GRUB/Hyper-V/filesystem contract and
  # ConditionPathExists=/var/lib/fleet-access/bootstrap-approved.
  systemd.services.comin.serviceConfig = {
    MemoryHigh = "256M";
    MemoryMax = "512M";
    CPUQuota = "50%";
    Nice = 10;
  };
  systemd.tmpfiles.rules = [ "d /var/lib/fleet-access 0755 root root -" ];
}
