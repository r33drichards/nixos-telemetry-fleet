# Separate integration candidate, not the existing node2-cachix deploy target.
{ lib, ... }: {
  imports = [
    ./node2-access.nix
    ./cachix-node2.nix
    ../candidates/hermes/service.nix
    ../candidates/hermes/tunnel.nix
  ];
  fleet.hermes.enable = true;
  fleet.hermesTunnel.enable = true;
  # Enable describes the closure; runtime approval/config/auth gates still
  # prevent Hermes from starting before fresh provider consent.
  services.comin.enable = lib.mkForce false;
  systemd.services.comin.enable = lib.mkForce false;
}
