# Separate candidate; no agent starts until privileged bootstrap is approved.
{ lib, ... }: {
  # One deployment controller only, independently of the older Comin leaf.
  services.comin.enable = lib.mkForce false;
  systemd.services.comin.enable = lib.mkForce false;
  services.cachix-agent = {
    enable = true;
    name = "node2";
    verbose = false;
    credentialsFile = "/var/lib/fleet-access/cachix-agent.env";
  };
  systemd.services.cachix-agent.unitConfig.ConditionPathExists = [
    "/var/lib/fleet-access/cachix-approved"
    "/var/lib/fleet-access/cachix-agent.env"
  ];
  # Public cache trust is nonsecret; downloads need no read token.
  nix.settings = {
    extra-substituters = [ "https://r33drichards-nixos-fleet.cachix.org" ];
    extra-trusted-public-keys = [ "r33drichards-nixos-fleet.cachix.org-1:olHCUKLC5yhwGhf0y+ZI8LbfQ6L/ZQwtN2vsjIAgV9M=" ];
    max-jobs = 0;
    fallback = false;
    require-sigs = true;
  };
}
