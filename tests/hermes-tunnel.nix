# Transport/gating fixture. The separate contract builds the actual Azure/Hermes
# closure; this VM test deliberately does not authenticate to a model provider.
{ pkgs, comin }:
pkgs.testers.runNixOSTest {
  name = "hermes-restricted-reverse-tunnel";
  nodes.server = { lib, ... }: {
    imports = [ comin.nixosModules.comin ../common/modules/base.nix
      ../common/modules/telemetry.nix ../common/modules/wasm.nix
      ../deploy/node2-hermes.nix ];
    lab.overlayIPv6 = "fd42::1";
    fleet.hermes.package = pkgs.writeShellScriptBin "hermes" "exit 77";
    networking.interfaces.eth1.ipv6.addresses = [{ address = "fd00:1::1"; prefixLength = 64; }];
    environment.systemPackages = [ pkgs.openssh pkgs.curl ];
    systemd.tmpfiles.rules = [
      "d /var/lib/fleet-bootstrap 0755 root root -"
      "d /var/lib/cloud/scripts/per-boot 0755 root root -"
      "C /var/lib/fleet-bootstrap/check-ssh-policy.sh 0700 root root - ${../candidates/hermes/bootstrap/check-ssh-policy.sh}"
      "C /var/lib/cloud/scripts/per-boot/fleet-ssh6 0700 root root - ${../candidates/hermes/bootstrap/ssh6-per-boot.sh}"
    ];
    systemd.services.fixture-cloud-per-boot = {
      wantedBy = [ "multi-user.target" ];
      after = [ "sshd.service" "firewall.service" "systemd-tmpfiles-setup.service" ];
      unitConfig.ConditionPathExists = "/var/lib/fleet-access/hermes-tunnel-authorized_keys";
      path = [ pkgs.cloud-init pkgs.openssh pkgs.coreutils pkgs.gawk pkgs.gnugrep pkgs.systemd ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${pkgs.cloud-init}/bin/cloud-init single --name scripts-per-boot --frequency always";
      };
    };
    virtualisation.memorySize = 1024;
  };
  nodes.client = { ... }: {
    networking.interfaces.eth1.ipv6.addresses = [{ address = "fd00:1::2"; prefixLength = 64; }];
    environment.systemPackages = [ pkgs.openssh pkgs.python3 ];
    systemd.services.echo-fixture = {
      wantedBy = [ "multi-user.target" ];
      serviceConfig.ExecStart = "${pkgs.python3}/bin/python -m http.server 6667 --bind 127.0.0.1 --directory /tmp";
    };
    virtualisation.memorySize = 512;
  };
  testScript = ''
    start_all()
    server.wait_for_unit("sshd.service")
    client.wait_for_unit("echo-fixture.service")
    client.succeed("ssh-keygen -q -t ed25519 -N \"\" -f /root/operator; ssh-keygen -q -t ed25519 -N \"\" -f /root/tunnel")
    for name, filename in [("operator", "authorized_keys"), ("tunnel", "hermes-tunnel-authorized_keys")]:
        public = client.succeed("cat /root/" + name + ".pub").strip()
        server.succeed("printf '%s\\n' '" + public + "' > /var/lib/fleet-access/" + filename + "; chmod 644 /var/lib/fleet-access/" + filename)
    server.succeed("systemctl start fixture-cloud-per-boot.service")
    hostkey = server.succeed("cat /etc/ssh/ssh_host_ed25519_key.pub").strip()
    client.succeed("printf '%s\\n' 'fd00:1::1 " + hostkey + "' > /root/known_hosts; echo transport-ok > /tmp/probe")
    common = "ssh -6 -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/root/known_hosts -o ConnectTimeout=3 "
    operator = common + "-i /root/operator operator@fd00:1::1 "
    tunnel = common + "-i /root/tunnel "
    client.wait_until_succeeds(operator + "true")
    client.fail(tunnel + "hermes-tunnel@fd00:1::1 true")
    client.fail(tunnel + "-tt hermes-tunnel@fd00:1::1 true")
    # -W requires a local/direct-tcpip channel, forbidden even when SSH auth succeeds.
    client.fail(tunnel + "-W 127.0.0.1:22 hermes-tunnel@fd00:1::1")
    for listen in ["0.0.0.0:16667", "127.0.0.1:16668"]:
        client.fail(tunnel + "-o ExitOnForwardFailure=yes -N -R " + listen + ":127.0.0.1:6667 hermes-tunnel@fd00:1::1")
    forward = tunnel + "-o ExitOnForwardFailure=yes -fN -R 127.0.0.1:16667:127.0.0.1:6667 hermes-tunnel@fd00:1::1"
    client.succeed(forward)
    server.wait_until_succeeds("curl --fail --max-time 3 http://127.0.0.1:16667/probe | grep -Fx transport-ok")
    server.succeed("ss -lnt '( sport = :16667 )' | grep -F 127.0.0.1:16667")
    server.fail("ss -lnt '( sport = :16667 )' | grep -E '(0.0.0.0|\\[::\\]|\\*):16667'")
    server.fail("systemctl is-active hermes-irc")
    server.fail("systemctl is-active comin")
    server.fail("systemctl is-active cachix-agent")
    server.shutdown()
    server.start()
    server.wait_for_unit("sshd.service")
    client.wait_until_succeeds(operator + "true")
    client.succeed(forward)
    server.wait_until_succeeds("curl --fail --max-time 3 http://127.0.0.1:16667/probe | grep -Fx transport-ok")
    server.fail("systemctl is-active hermes-irc")
    server.fail("systemctl is-active comin")
  '';
}
