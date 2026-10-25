# Keep the pinned upstream Azure Gen2 boot/hardware contract across Comin switches.
# Importing this module evaluates the image builder but does not build/upload an image.
{ config, lib, modulesPath, ... }: {
  imports = [ "${modulesPath}/virtualisation/azure-image.nix" ];
  virtualisation.azureImage.vmGeneration = "v2";
  # azure-common enables SSH/root-key login; preserve our approval gate and policy.
  services.openssh.enable = lib.mkOverride 90 config.lab.enable;
  services.openssh.openFirewall = lib.mkForce false;
  services.openssh.settings.PermitRootLogin = lib.mkForce "no";
  systemd.services.comin = lib.mkIf config.services.comin.enable {
    unitConfig.ConditionPathExists = "/var/lib/fleet-access/bootstrap-approved";
  };
}
