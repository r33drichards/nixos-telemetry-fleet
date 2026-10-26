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
    start_all()
    server.wait_for_unit("sshd.service")
    client.wait_for_unit("multi-user.target")
    client.succeed("ssh-keygen -q -t ed25519 -N \"\" -f /root/key; ssh-keygen -q -t ed25519 -N \"\" -f /root/wrong")
    pub = client.succeed("cat /root/key.pub").strip()
    server.succeed("printf '%s\\n' '" + pub + "' > /var/lib/fleet-access/authorized_keys; chmod 644 /var/lib/fleet-access/authorized_keys")
    hostkey = server.succeed("cat /etc/ssh/ssh_host_ed25519_key.pub").strip()
    client.succeed("printf '%s\\n' 'fd00:1::1 " + hostkey + "' > /root/known_hosts")
    ssh = "ssh -6 -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/root/known_hosts -o ConnectTimeout=3 -i /root/key "
    client.fail(ssh + "operator@fd00:1::1 true")
    server.succeed("systemctl start fixture-cloud-per-boot.service")
    client.wait_until_succeeds(ssh + "operator@fd00:1::1 true", timeout=60)
    client.fail(ssh + "root@fd00:1::1 true")
    client.fail(ssh.replace('/root/key', '/root/wrong') + "operator@fd00:1::1 true")
    for operation in ["restart", "reload"]:
        server.succeed("systemctl " + operation + " firewall")
        client.succeed(ssh + "operator@fd00:1::1 true")
    server.shutdown()
    server.start()
    server.wait_for_unit("sshd.service")
    client.wait_until_succeeds(ssh + "operator@fd00:1::1 true", timeout=60)
    server.succeed("test ! -e /var/lib/fleet-access/bootstrap-approved")
    server.fail("systemctl is-active comin")
  '';
}
