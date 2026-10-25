{ pkgs, common, comin }:
let
  node = name: address: { lib, ... }: {
    imports = [ comin.nixosModules.comin ../common/modules/base.nix ../common/modules/telemetry.nix ../common/modules/wasm.nix ];
    networking.hostName = name;
    boot.loader.systemd-boot.enable = lib.mkForce false;
    lab = { enable = true; hardwareApproved = true; networkApproved = true; overlayIPv6 = address; publicInterface = "eth1"; };
    # No external Git access in the VM test. Comin switching is a separate live check.
    services.comin.enable = lib.mkForce false;
    systemd.network.networks."10-uplink".enable = lib.mkForce false;
    networking.useDHCP = lib.mkForce false;
    networking.interfaces.eth1.ipv6.addresses = [{ address = if name == "server" then "fd00:1::1" else "fd00:1::2"; prefixLength = 64; }];
    environment.systemPackages = [ pkgs.wireguard-tools pkgs.curl ];
    virtualisation.memorySize = 1536;
  };
in pkgs.testers.runNixOSTest {
  name = "boot-overlay-wasm";
  nodes.server = { ... }: {
    imports = [ (node "server" "fd42:6e69:7800::1") ];
    lab.wasm.enable = true;
  };
  nodes.client = node "client" "fd42:6e69:7800::2";
  testScript = ''
    start_all()
    for machine in [server, client]:
        machine.wait_for_unit("multi-user.target")
        machine.succeed("grep -q '^ID=nixos' /etc/os-release")
        machine.succeed("install -d -m 700 /var/lib/fleet-secrets; umask 077; wg genkey > /var/lib/fleet-secrets/key")
    pubs = [m.succeed("wg pubkey < /var/lib/fleet-secrets/key").strip() for m in [server, client]]
    for i, machine in enumerate([server, client]):
        peer = 1 - i
        config = "[Interface]\\nAddress = fd42:6e69:7800::%d/128\\nListenPort = 51820\\nPrivateKey = " % (i + 1)
        suffix = "\\n[Peer]\\nPublicKey = %s\\nAllowedIPs = fd42:6e69:7800::%d/128\\nEndpoint = [fd00:1::%d]:51820\\n" % (pubs[peer], peer + 1, peer + 1)
        machine.succeed("(printf '" + config + "'; cat /var/lib/fleet-secrets/key; printf '" + suffix + "') > /var/lib/fleet-secrets/wg0.conf; chmod 600 /var/lib/fleet-secrets/wg0.conf")
        machine.succeed("systemctl restart wg-quick-wg0 prometheus-node-exporter")
    server.succeed("systemctl restart wasm-http")
    server.wait_for_unit("wasm-http.service")
    client.wait_until_succeeds("curl -g --noproxy '*' --max-time 5 -fsS 'http://[fd42:6e69:7800::1]:8080/' | grep -qx 'hello from wasm'", timeout=180)
    client.succeed("curl -g --noproxy '*' --max-time 5 -fsS 'http://[fd42:6e69:7800::1]:9100/metrics' | grep '^node_uname_info{' > /dev/null")
    client.fail("curl -g --noproxy '*' --connect-timeout 3 -fsS 'http://[fd00:1::1]:8080/'")
    server.succeed("test $(stat -c %a /var/lib/fleet-secrets/wg0.conf) = 600")
    server.shutdown()
    server.start()
    server.wait_for_unit("wasm-http.service")
    client.wait_until_succeeds("curl -g --noproxy '*' --max-time 5 -fsS 'http://[fd42:6e69:7800::1]:8080/' | grep -qx 'hello from wasm'", timeout=180)
  '';
}
