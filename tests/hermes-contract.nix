{ pkgs, candidate }:
let c = candidate; in
assert c.networking.hostName == "node2";
assert c.services.openssh.enable && c.users.users.operator.isNormalUser;
assert pkgs.lib.sort builtins.lessThan c.services.openssh.settings.AllowUsers == [ "hermes-tunnel" "operator" ];
assert c.services.openssh.settings.PermitRootLogin == "no";
assert !c.services.openssh.settings.PasswordAuthentication && !c.services.openssh.settings.KbdInteractiveAuthentication;
assert c.services.openssh.settings.AuthorizedKeysFile == "/var/lib/fleet-access/authorized_keys";
assert !c.services.comin.enable && !c.systemd.services.comin.enable;
assert c.fleet.hermes.enable && c.fleet.hermesTunnel.enable;
assert c.fleet.hermesTunnel.publicKey == null;
assert c.users.users.hermes-tunnel.extraGroups == [];
assert c.systemd.services.hermes-irc.serviceConfig.User == "hermes";
assert c.systemd.services.hermes-irc.serviceConfig.NoNewPrivileges;
assert builtins.elem "/var/lib/hermes/.hermes/auth.json" c.systemd.services.hermes-irc.unitConfig.ConditionPathExists;
assert builtins.elem "/var/lib/fleet-access/hermes-approved" c.systemd.services.hermes-irc.unitConfig.ConditionPathExists;
assert c.nix.settings.max-jobs == 0 && !c.nix.settings.fallback && c.nix.settings.require-sigs;
assert c.boot.loader.grub.enable && c.boot.loader.grub.efiSupport;
assert c.fileSystems."/".device == "/dev/disk/by-label/nixos";
assert c.fileSystems."/boot".device == "/dev/disk/by-label/ESP";
assert c.networking.useNetworkd;
assert !c.lab.enable && !c.lab.wireguard && !c.lab.wasm.enable;
assert !c.services.prometheus.enable && !c.services.grafana.enable;
pkgs.runCommand "node2-hermes-contract" { nativeBuildInputs = [ pkgs.python3 pkgs.openssh ]; } ''
  test -x ${c.system.build.toplevel}/bin/switch-to-configuration
  cp -R ${../candidates/hermes} candidate
  chmod -R u+w candidate
  python3 candidate/bootstrap/test_policy.py
  touch "$out"
''
