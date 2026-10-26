{ pkgs, comin }:
pkgs.testers.runNixOSTest {
  name = "node2-image-to-comin-leaf";
  nodes.server = { config, lib, ... }: {
    imports = [ comin.nixosModules.comin ../common/modules/base.nix ];
    # Reproduce the installed image's bare service state, with the real leaf
    # imported only into the generation Comin will activate. Azure hardware is
    # evaluated separately; this QEMU fixture does not emulate Hyper-V.
    lab = { enable = false; overlayIPv6 = "fd42::1"; repoURL = "file:///var/lib/comin-test-repo"; };
    services.openssh.enable = lib.mkForce true;
    services.openssh.openFirewall = lib.mkForce false;
    users.users.operator.isNormalUser = true;
    services.comin.enable = lib.mkForce true;
    systemd.services.comin.unitConfig.ConditionPathExists = "/var/lib/fleet-access/bootstrap-approved";
    systemd.network.networks."10-uplink".enable = lib.mkForce false;
    networking.useDHCP = lib.mkForce false;
    networking.interfaces.eth1.ipv6.addresses = [{ address = "fd00:1::1"; prefixLength = 64; }];
    services.comin.repositorySubdir = lib.mkForce ".";
    services.comin.remotes = lib.mkForce [{ name = "origin"; url = "file:///var/lib/comin-test-repo"; branches.main = { name = "main"; operation = "switch"; }; branches.testing.name = ""; poller.period = 5; }];
    environment.systemPackages = [ pkgs.git pkgs.openssh ];
    # Offline fixture: all build inputs are supplied by the test closure.
    nix.settings.substituters = lib.mkForce [];
    environment.etc."fleet-generation".text = lib.mkDefault "initial";
    specialisation.updated.configuration = {
      imports = [ ../nodes/node2/deployment.nix ];
      environment.etc."fleet-generation".text = lib.mkForce "updated";
    };
    boot.loader.systemd-boot.enable = true;
    virtualisation = {
      memorySize = 1024;
      useBootLoader = true;
      useEFIBoot = true;
      diskSize = 4096;
      additionalPaths = [ config.specialisation.updated.configuration.system.build.toplevel pkgs.coreutils ];
    };
  };
  nodes.client = { ... }: {
    networking.interfaces.eth1.ipv6.addresses = [{ address = "fd00:1::2"; prefixLength = 64; }];
    environment.systemPackages = [ pkgs.openssh ];
    virtualisation.memorySize = 512;
  };
  testScript = { nodes, ... }: let
    updated = nodes.server.specialisation.updated.configuration.system.build.toplevel;
    fixture = pkgs.writeText "comin-test-flake.nix" ''
      {
        outputs = { self }: {
          nixosConfigurations.server.config = {
            services.comin.machineId = null;
            system.build.toplevel = builtins.derivation {
              name = "comin-prebuilt-generation";
              system = "x86_64-linux";
              builder = builtins.appendContext "${pkgs.coreutils}/bin/ln" { "${pkgs.coreutils}" = { path = true; }; };
              args = [ "-s" (builtins.appendContext "${updated}" { "${updated}" = { path = true; }; }) (builtins.placeholder "out") ];
            };
          };
        };
      }
    '';
  in ''
    start_all()
    server.wait_for_unit("sshd.service")
    client.wait_for_unit("multi-user.target")
    server.succeed("grep -qx initial /etc/fleet-generation")
    server.fail("systemctl is-active comin")
    server.succeed("test ! -e /var/lib/fleet-access/bootstrap-approved")
    client.succeed("umask 077; ssh-keygen -q -t ed25519 -N \"\" -f /root/test-key; ssh-keygen -q -t ed25519 -N \"\" -f /root/wrong-key")
    pub = client.succeed("cat /root/test-key.pub").strip()
    server.succeed("install -d -m 755 /var/lib/fleet-access; printf '%s\\n' '" + pub + "' > /var/lib/fleet-access/authorized_keys; chmod 644 /var/lib/fleet-access/authorized_keys")
    server.copy_from_host("${../terraform/amd-canary/bootstrap/ssh6-per-boot.sh}", "/tmp/fleet-ssh6")
    server.succeed("sh /tmp/fleet-ssh6")
    hostkey = server.succeed("cat /etc/ssh/ssh_host_ed25519_key.pub").strip()
    client.succeed("printf '%s\\n' 'fd00:1::1 " + hostkey + "' > /root/known_hosts")
    ssh = "ssh -6 -b fd00:1::2 -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/root/known_hosts -o ConnectTimeout=5 -i /root/test-key "
    client.wait_until_succeeds(ssh + "operator@fd00:1::1 'id -un' | grep -qx operator", timeout=60)
    client.fail(ssh + "root@fd00:1::1 true")
    client.fail(ssh.replace('/root/test-key', '/root/wrong-key') + "operator@fd00:1::1 true")
    effective = server.succeed("sshd -T -f /etc/ssh/sshd_config")
    auth = {key.lower(): value for key, value in (line.split(None, 1) for line in effective.splitlines() if len(line.split(None, 1)) == 2)}
    print({key: auth.get(key) for key in ["passwordauthentication", "kbdinteractiveauthentication"]})
    assert auth.get("passwordauthentication") == "no", "Password authentication must be disabled"
    assert auth.get("kbdinteractiveauthentication") == "no", "Keyboard-interactive authentication must be disabled"
    # Public IPv6 SSH is the approved scope; no IPv4 or other services.
    client.succeed(ssh + "operator@fd00:1::1 'test ! -w /var/lib/fleet-access'")
    client.fail(ssh + "operator@fd00:1::1 'sudo -n true'")
    unwanted = ["wasm-http", "grafana", "prometheus", "prometheus-node-exporter", "k3s", "wg-quick-wg0"]
    for unit in unwanted:
        server.fail("systemctl is-active " + unit)
    server.succeed("git init -b main /var/lib/comin-test-repo; cd /var/lib/comin-test-repo; git config user.name Test; git config user.email test@example.invalid; echo initial > marker; git add marker; git commit -m initial")
    # This test-driver root action represents the separately approved bootstrap;
    # the unprivileged SSH user cannot create the gate itself.
    server.succeed("install -o root -g root -m 600 /dev/null /var/lib/fleet-access/bootstrap-approved; systemctl start comin")
    server.wait_for_unit("comin.service")
    # Main advances to a real NixOS generation. Comin evaluates the flake,
    # invokes nix build to wrap the real prebuilt generation, and switches.
    # This tests activation/reboot, not source compilation within the 1-GiB guest.
    # Retire the image's runtime firewall hook before reconciliation, proving
    # the leaf's declarative firewall survives activation/restart/reboot.
    server.succeed("rm /run/systemd/system/firewall.service.d/50-fleet-ssh6.conf; systemctl daemon-reload")
    server.copy_from_host("${fixture}", "/var/lib/comin-test-repo/flake.nix")
    server.succeed("cd /var/lib/comin-test-repo; git add flake.nix; git commit -m update")
    server.wait_until_succeeds("grep -qx updated /etc/fleet-generation", timeout=300)
    server.succeed("test $(readlink -f /run/current-system) = ${updated}")
    client.succeed(ssh + "operator@fd00:1::1 'cat /etc/fleet-generation' | grep -qx updated")
    server.succeed("systemctl restart firewall")
    client.succeed(ssh + "operator@fd00:1::1 true")
    server.shutdown()
    server.start()
    server.wait_for_unit("comin.service")
    server.wait_for_unit("sshd.service")
    server.succeed("grep -qx updated /etc/fleet-generation")
    for unit in unwanted:
        server.fail("systemctl is-active " + unit)
    client.fail(ssh + "root@fd00:1::1 true")
    client.fail(ssh.replace('/root/test-key', '/root/wrong-key') + "operator@fd00:1::1 true")
    client.wait_until_succeeds(ssh + "operator@fd00:1::1 'cat /etc/fleet-generation' | grep -qx updated", timeout=60)
    for unit in unwanted:
        server.fail("systemctl is-active " + unit)
  '';
}
