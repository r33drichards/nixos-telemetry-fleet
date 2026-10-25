{ config, lib, pkgs, ... }:
let
  cfg = config.lab.wasm;
  spin = pkgs.stdenvNoCC.mkDerivation {
    pname = "fleet-spin";
    version = "4.1.0";
    src = pkgs.fetchurl {
      url = "https://github.com/spinframework/spin/releases/download/v4.1.0/spin-v4.1.0-linux-amd64.tar.gz";
      sha256 = "aeeb892f94cf861f5302546faa0bdaa82cc4be30539621299746a6dc011f3b5a";
    };
    nativeBuildInputs = [ pkgs.autoPatchelfHook ];
    buildInputs = [ pkgs.stdenv.cc.cc.lib ];
    sourceRoot = ".";
    installPhase = "install -Dm755 spin $out/bin/spin";
  };
  component = pkgs.fetchurl {
    url = "https://github.com/fermyon/spin-fileserver/releases/download/v0.1.0/spin_static_fs.wasm";
    sha256 = "96c76d9af86420b39eb6cd7be5550e3cb5d4cc4de572ce0fd1f6a29471536cb4";
  };
  app = pkgs.runCommand "fleet-wasm-http" {} ''
    mkdir -p $out/content
    cp ${../wasm/index.html} $out/content/index.html
    cat > $out/spin.toml <<MANIFEST
    spin_manifest_version = 2
    [application]
    name = "fleet-http-smoke"
    version = "0.1.0"
    [[trigger.http]]
    route = "/..."
    component = "files"
    [component.files]
    source = "${component}"
    files = [{ source = "content", destination = "/" }]
    MANIFEST
  '';
in {
  options.lab.wasm.enable = lib.mkEnableOption "private Spin Wasm HTTP qualification service";
  config = lib.mkIf cfg.enable {
    assertions = [
      { assertion = config.lab.enable; message = "Wasm requires the approved node network profile."; }
      { assertion = pkgs.stdenv.hostPlatform.system == "x86_64-linux"; message = "The pinned Spin host binary is qualified only for x86_64; ARM is not implemented."; }
    ];
    networking.firewall.interfaces.wg0.allowedTCPPorts = [ 8080 ];
    systemd.services.wasm-http = {
      description = "Private Wasm HTTP qualification service";
      wantedBy = [ "multi-user.target" ];
      requires = [ "wg-quick-wg0.service" ];
      after = [ "wg-quick-wg0.service" ];
      serviceConfig = {
        ExecStart = "${spin}/bin/spin up --listen [${config.lab.overlayIPv6}]:8080 --from ${app}/spin.toml";
        DynamicUser = true;
        StateDirectory = "wasm-http";
        WorkingDirectory = "/var/lib/wasm-http";
        Environment = "XDG_CACHE_HOME=/var/lib/wasm-http";
        Restart = "on-failure";
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateTmp = true;
        MemoryMax = "256M";
      };
    };
  };
}
