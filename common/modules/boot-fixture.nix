# Evaluation only: replace with a tested cloud hardware/image module before deployment.
{ lib, ... }: {
  boot.loader.systemd-boot.enable = lib.mkDefault true;
  fileSystems."/" = lib.mkDefault { device = "/dev/disk/by-label/nixos"; fsType = "ext4"; };
  fileSystems."/boot" = lib.mkDefault { device = "/dev/disk/by-label/ESP"; fsType = "vfat"; };
}
