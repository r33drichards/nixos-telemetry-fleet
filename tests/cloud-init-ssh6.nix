{ pkgs, comin }:
pkgs.testers.runNixOSTest {
  name = "cloud-init-ssh6-bootstrap";
  nodes.server = { lib, ... }: {
    imports = [ comin.nixosModules.comin ../common/modules/base.nix ];
    lab = { enable = false; overlayIPv6 = "fd42::1"; };
    services.openssh.enable = lib.mkForce true;
    users.users.operator.isNormalUser = true;
    networking.useDHCP = lib.mkForce false;
    systemd.network.networks."10-uplink".enable = lib.mkForce false;
    networking.interfaces.eth1.ipv6.addresses = [{ address = "fd00:1::1"; prefixLength = 64; }];
    environment.systemPackages = [ pkgs.openssh ];
    systemd.tmpfiles.rules = [
      "d /var/lib/fleet-access 0755 root root -"
      "d /var/lib/cloud/scripts/per-boot 0755 root root -"
      "C /var/lib/cloud/scripts/per-boot/fleet-ssh6 0700 root root - ${../terraform/amd-canary/bootstrap/ssh6-per-boot.sh}"
    ];
    # Exercise cloud-init's real per-boot runner without pretending to emulate
    # the Azure datasource/OVF transport. The test supplies write-files output.
    systemd.services.fixture-cloud-per-boot = {
      wantedBy = [ "multi-user.target" ];
      after = [ "sshd.service" "firewall.service" "systemd-tmpfiles-setup.service" ];
      unitConfig.ConditionPathExists = "/var/lib/fleet-access/authorized_keys";
      path = [ pkgs.cloud-init pkgs.openssh pkgs.coreutils pkgs.gnugrep pkgs.systemd ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${pkgs.cloud-init}/bin/cloud-init single --name scripts-per-boot --frequency always";
      };
    };
    virtualisation.memorySize = 1024;
  };
  nodes.client = { ... }: {
    networking.interfaces.eth1.ipv6.addresses = [{ address = "fd00:1::2"; prefixLength = 64; }];
    environment.systemPackages = [ pkgs.openssh ];
    virtualisation.memorySize = 512;
  };
  testScript = ''
    def check_ssh(command, expected_status):
        # ConnectTimeout bounds the handshake only. Bound the complete client
        # and driver capture, and never count a timeout as a negative-test pass.
        status, output = client.execute(command, timeout=40)
        if status != expected_status:
            print(output)
            print(client.succeed("tail -n 80 /tmp/fixture-ssh.log", timeout=10))
            print(server.succeed("journalctl -u sshd -n 80 --no-pager", timeout=10))
        assert status == expected_status, (status, expected_status, output)

    start_all()
    server.wait_for_unit("sshd.service")
    client.wait_for_unit("multi-user.target")
    client.succeed("ssh-keygen -q -t ed25519 -N \"\" -f /root/key; ssh-keygen -q -t ed25519 -N \"\" -f /root/wrong")
    pub = client.succeed("cat /root/key.pub").strip()
    server.succeed("printf '%s\\n' '" + pub + "' > /var/lib/fleet-access/authorized_keys; chmod 644 /var/lib/fleet-access/authorized_keys")
    hostkey = server.succeed("cat /etc/ssh/ssh_host_ed25519_key.pub").strip()
    client.succeed("printf '%s\\n' 'fd00:1::1 " + hostkey + "' > /root/known_hosts")
    # This noninteractive probe must not consume the test-driver shell stdin.
    ssh = "timeout --kill-after=5s 30s ssh -n -vv -E /tmp/fixture-ssh.log -6 -o ServerAliveInterval=5 -o ServerAliveCountMax=3 -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/root/known_hosts -o ConnectTimeout=3 -i /root/key "
    check_ssh(ssh + "operator@fd00:1::1 true", 255)
    print(server.succeed("sshd -T -f /etc/ssh/sshd_config | grep -Ei '^(permitrootlogin|passwordauthentication|kbdinteractiveauthentication|allowusers|authorizedkeysfile) '"))
    server.succeed("systemctl start fixture-cloud-per-boot.service")
    client.wait_until_succeeds(ssh + "operator@fd00:1::1 true", timeout=60)
    check_ssh(ssh + "root@fd00:1::1 true", 255)
    check_ssh(ssh.replace('/root/key', '/root/wrong') + "operator@fd00:1::1 true", 255)
    for operation in ["restart", "reload"]:
        server.succeed("systemctl " + operation + " firewall")
        check_ssh(ssh + "operator@fd00:1::1 true", 0)
    server.shutdown()
    server.start()
    server.wait_for_unit("sshd.service")
    client.wait_until_succeeds(ssh + "operator@fd00:1::1 true", timeout=60)
    server.succeed("test ! -e /var/lib/fleet-access/bootstrap-approved")
    server.fail("systemctl is-active comin")
  '';
}
