{ pkgs, comin }:
pkgs.testers.runNixOSTest {
  name = "bare-boot-ssh-comin";
  nodes.server = { config, lib, ... }: {
    imports = [ comin.nixosModules.comin ../common/modules/base.nix ];
    lab = { enable = true; hardwareApproved = true; networkApproved = true; overlayIPv6 = "fd42::1"; sshSourceCIDRs = [ "fd00:1::2/128" ]; publicInterface = "eth1"; repoURL = "file:///var/lib/comin-test-repo"; };
    systemd.network.networks."10-uplink".enable = lib.mkForce false;
    networking.useDHCP = lib.mkForce false;
    networking.interfaces.eth1.ipv6.addresses = [{ address = "fd00:1::1"; prefixLength = 64; }];
    services.comin.repositorySubdir = lib.mkForce ".";
    services.comin.remotes = lib.mkForce [{ name = "origin"; url = "file:///var/lib/comin-test-repo"; branches.main = { name = "main"; operation = "switch"; }; branches.testing.name = ""; poller.period = 5; }];
    environment.systemPackages = [ pkgs.git pkgs.openssh ];
    environment.etc."fleet-generation".text = lib.mkDefault "initial";
    specialisation.updated.configuration.environment.etc."fleet-generation".text = lib.mkForce "updated";
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
              builder = "${pkgs.coreutils}/bin/ln";
              args = [ "-s" "${updated}" (builtins.placeholder "out") ];
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
    client.succeed("umask 077; ssh-keygen -q -t ed25519 -N \"\" -f /root/test-key; ssh-keygen -q -t ed25519 -N \"\" -f /root/wrong-key")
    pub = client.succeed("cat /root/test-key.pub").strip()
    server.succeed("install -d -m 755 /var/lib/fleet-access; printf '%s\\n' '" + pub + "' > /var/lib/fleet-access/authorized_keys; chmod 644 /var/lib/fleet-access/authorized_keys")
    hostkey = server.succeed("cat /etc/ssh/ssh_host_ed25519_key.pub").strip()
    client.succeed("printf '%s\\n' 'fd00:1::1 " + hostkey + "' > /root/known_hosts")
    ssh = "ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/root/known_hosts -o ConnectTimeout=5 -i /root/test-key "
    client.wait_until_succeeds(ssh + "operator@fd00:1::1 'id -un' | grep -qx operator", timeout=60)
    client.fail(ssh + "root@fd00:1::1 true")
    client.fail(ssh.replace('/root/test-key', '/root/wrong-key') + "operator@fd00:1::1 true")
    server.succeed("sshd -T -f /etc/ssh/sshd_config > /tmp/effective-sshd; grep -qx 'passwordauthentication no' /tmp/effective-sshd && grep -qx 'kbdinteractiveauthentication no' /tmp/effective-sshd")
    client.succeed("ip -6 addr add fd00:1::99/64 dev eth1")
    client.fail(ssh + "-b fd00:1::99 operator@fd00:1::1 true")
    unwanted = ["wasm-http", "grafana", "prometheus", "prometheus-node-exporter", "k3s", "wg-quick-wg0"]
    for unit in unwanted:
        server.fail("systemctl is-active " + unit)
    server.succeed("git init -b main /var/lib/comin-test-repo; cd /var/lib/comin-test-repo; git config user.name Test; git config user.email test@example.invalid; echo initial > marker; git add marker; git commit -m initial")
    server.succeed("systemctl restart comin")
    server.wait_for_unit("comin.service")
    # Main advances to a real NixOS generation. Comin evaluates the flake,
    # invokes nix build to wrap the real prebuilt generation, and switches.
    # This tests activation/reboot, not source compilation within the 1-GiB guest.
    server.succeed("cp ${fixture} /var/lib/comin-test-repo/flake.nix; cd /var/lib/comin-test-repo; git add flake.nix; git commit -m update")
    server.wait_until_succeeds("grep -qx updated /etc/fleet-generation", timeout=300)
    server.succeed("test $(readlink -f /run/current-system) = ${updated}")
    client.succeed(ssh + "operator@fd00:1::1 'cat /etc/fleet-generation' | grep -qx updated")
    server.shutdown()
    server.start()
    server.wait_for_unit("comin.service")
    server.wait_for_unit("sshd.service")
    server.succeed("grep -qx updated /etc/fleet-generation")
    client.wait_until_succeeds(ssh + "operator@fd00:1::1 'cat /etc/fleet-generation' | grep -qx updated", timeout=60)
    for unit in unwanted:
        server.fail("systemctl is-active " + unit)
  '';
}
