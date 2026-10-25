# Bootstrap, update and recovery

## Network and secrets

Use a separately approved initial access path. This minimal configuration does not enable SSH or generate keys. WireGuard runs from `/run/secrets/wg0.conf`, including its private key and peers, so secret values never enter the Nix store. Use mode 0600 and a root-owned parent directory. Ensure boot-time delivery completes before `wg-quick-wg0.service` starts; configure that dependency in the approved hardware/secret module. A missing secret must fail closed.

The uplink uses DHCPv4 and accepts IPv6 router advertisements; approved static IPv6 addresses can be set through `lab.publicIPv6Addresses`. Validate the actual cloud route and DHCP behavior before switching. Azure dual-stack NIC setup is not created by this repository. WireGuard transports IPv6 between nodes; private `/128` peer routes expose only the intended overlay addresses. No default-route tunnel or NAT is assumed. MTU, endpoint reachability and cross-region egress remain deployment decisions.

Prometheus connects to `[fd42:6e69:7800::1]:9100`, `::2`, and `::3`. Change overlay addresses in root and leaf entrypoints and `lab.scrapeTargets` together. Node exporters require the WireGuard service; they cannot fall back to a public bind. Verify a handshake and `curl -g http://[<peer-overlay-ip>]:9100/metrics` from the telemetry node after approval. No public exporter endpoint should answer.

Keep Grafana's separate encryption key persistent across reboots and restores; back it up with the Grafana database through an approved secret process. It is delivered from `/run/secrets/grafana-secret-key` using a second systemd credential. Do not regenerate it on every boot.

Grafana gets its password through systemd credentials from the root-owned configured runtime path. The file expansion points into `/run/credentials/grafana.service/`; the Nix store contains only the path. Grafana uses the password for initial database setup. Later password rotation needs an explicit Grafana account procedure; changing the file alone is not guaranteed to rotate an existing user's password.

## Public HTTPS Grafana

Select the hostname first; the intended URL is `https://<hostname>/`. Approve DNS AAAA, TCP 80/443 on the telemetry host and provider firewall, certificate issuance, and any IPv4 compatibility decision. Caddy provisions TLS and redirects HTTP to HTTPS. IPv6-only publication will not serve IPv4-only clients unless an approved bridge/proxy is added. No paid public IPv4 or DNS service is assumed.

Keep Grafana, Prometheus and node-exporter ports closed on the uplink. Test public access without credentials: dashboards and data must require login. Test the configured account, then inspect logs and disk use. Do not expose OTLP ports; this metrics-only profile has no OTLP receiver.

## Comin rollout

The upstream Comin module and package are pinned together. The repository's `main` branch is the mutable desired-state pointer; Nixpkgs and Comin dependencies remain immutable until a reviewed lock update. `branches.testing.name = ""` disables the default `testing-<hostname>` branch. Debug logging is off. No GitHub token or deploy key is required for the public repository.

Before the first automatic update, keep a cloud console or another recovery path and record a working NixOS generation. Evaluate/build the changed node flake, test on one canary, then merge a small change. Confirm the Comin deployment status, WireGuard handshakes, all three `up{job="nodes"}` values and Grafana login. Avoid simultaneous network/firewall changes across all nodes. A merge can trigger all enabled nodes; node-specific deployment flags support staged enabling, not a distributed rollout controller.

Comin retries builds twice and retains five successful boot entries. Build or activation success is not application/network-health success. The configuration deliberately makes no automatic rollback claim. For a bad revision, stop Comin from the recovery console, switch to a known-good generation (`nixos-rebuild switch --rollback` when appropriate), revert/fix the bad commit through the reviewed branch process, verify the desired configuration, then restart Comin. Inspect available generations before choosing a rollback target. Retain access until a reboot is verified.

## Capacity qualification

On a 1 GiB host, the OS, filesystem cache, Caddy, node-exporter, Comin, Grafana and Prometheus share limited memory. Per-service limits are ceilings, not reservations, and their sum can exceed RAM. A 512 MiB Comin evaluation concurrent with both 256 MiB telemetry services can exceed capacity. Prefer prebuilt, trusted outputs and measure evaluation overhead before enabling unattended updates; no new cache credentials or signing keys are configured here.

Collect idle/loaded `systemd-cgtop`, RSS, swap, `memory.events`, OOM logs, Prometheus head-series count/WAL size, disk growth, scrape duration and Grafana latency over at least a full retention window. Include a compaction and a Comin update. Do not declare the host viable from a short idle test. If it cannot fit, keep the capacity gate closed and choose an approved free alternative or a lighter design.
