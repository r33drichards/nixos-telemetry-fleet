{ pkgs, candidate }:
let c = candidate; in
assert c.networking.hostName == "node2";
assert c.services.openssh.enable && c.users.users.operator.isNormalUser;
assert c.services.openssh.settings.PermitRootLogin == "no";
assert !c.services.openssh.settings.PasswordAuthentication;
assert !c.services.openssh.settings.KbdInteractiveAuthentication;
assert c.services.openssh.settings.AuthorizedKeysFile == "/var/lib/fleet-access/authorized_keys";
assert !c.services.comin.enable && !c.systemd.services.comin.enable;
assert c.services.cachix-agent.enable && c.services.cachix-agent.name == "node2";
assert c.services.cachix-agent.credentialsFile == "/var/lib/fleet-access/cachix-agent.env";
assert builtins.elem "/var/lib/fleet-access/cachix-approved" c.systemd.services.cachix-agent.unitConfig.ConditionPathExists;
assert c.nix.settings.max-jobs == 0 && !c.nix.settings.fallback && c.nix.settings.require-sigs;
assert builtins.elem "https://r33drichards-nixos-fleet.cachix.org" c.nix.settings.extra-substituters;
assert builtins.elem "r33drichards-nixos-fleet.cachix.org-1:olHCUKLC5yhwGhf0y+ZI8LbfQ6L/ZQwtN2vsjIAgV9M=" c.nix.settings.extra-trusted-public-keys;
assert c.boot.loader.grub.enable && c.boot.loader.grub.efiSupport;
assert !c.boot.loader.systemd-boot.enable;
assert c.fileSystems."/".device == "/dev/disk/by-label/nixos";
assert c.fileSystems."/boot".device == "/dev/disk/by-label/ESP";
assert c.networking.useNetworkd;
assert !c.lab.enable && !c.lab.wireguard && !c.lab.wasm.enable;
assert !c.services.prometheus.enable && !c.services.grafana.enable;
# Building this check builds the REAL Azure candidate closure; no QEMU hardware
# override or inherited forced SSH fixture. It is not proof of Azure boot.
pkgs.runCommand "node2-cachix-contract" {} ''
  test -x ${c.system.build.toplevel}/bin/switch-to-configuration
  touch "$out"
''
