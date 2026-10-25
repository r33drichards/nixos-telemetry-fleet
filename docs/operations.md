# Bootstrap, update and recovery

## Network and secrets

Use a separately approved initial access path. This configuration does not enable SSH or generate keys. Store each node's WireGuard configuration at `/var/lib/fleet-secrets/wg0.conf`, and the telemetry host's Grafana files at `/var/lib/fleet-secrets/grafana-admin-password` and `/var/lib/fleet-secrets/grafana-secret-key`. The directory is root-owned mode 0700; deliver files root-owned mode 0600. No plaintext or encrypted secret payload belongs in Git, including sops/agenix files. Do not use Nix path literals or `builtins.readFile` for secrets.

The files persist on the host disk across reboots. systemd waits for their backing mounts and loads private runtime credentials before starting WireGuard or Grafana; missing files fail service startup. If initial delivery occurs after a service has exhausted its startup retries, reset that failed unit after installing the files, then start it and verify health. No network secret service or boot-time generation is configured. WireGuard's upstream module copies its runtime credential into a systemd-private temporary directory. This is not full disk encryption: disk snapshots and administrator access can expose the source files.

After host selection, the smallest delivery decision is approval to install these files once through the approved administrative access path (for example an authenticated SSH session with verified host keys), with secure stdin/file transfer rather than command arguments, shell history or logs. No delivery or credential creation is performed by this repository. An external secret manager is a future option, not a dependency or selected service.

Back up secret files separately from Git using an owner-approved protected backup location. Keep the Grafana database and its encryption key recoverable together, restrict backup access, and test a restore before unattended operation. No backup destination is selected yet. Restore the persistent files before service startup after host replacement. Comin updates configuration, not these files.

Rotate by installing a new file atomically in the same protected directory, preserving root ownership and mode 0600, then deliberately restarting the consuming service. WireGuard private-key changes require coordinated peer public-key updates and a recovery path. Grafana's admin password file initializes a new database; existing accounts require Grafana's supported password-reset procedure. Its encryption key is not an ordinary password: use the supported key migration procedure or a coordinated database/key restore, never blindly replace it. Old backups may contain retired keys and must follow the approved retention policy.

The uplink uses DHCPv4 and accepts IPv6 router advertisements; approved static IPv6 addresses can be set through `lab.publicIPv6Addresses`. Validate the actual cloud route and DHCP behavior before switching. Azure dual-stack NIC setup is not created by this repository. WireGuard transports IPv6 between nodes; private `/128` peer routes expose only the intended overlay addresses. No default-route tunnel or NAT is assumed. MTU, endpoint reachability and cross-region egress remain deployment decisions.

Prometheus connects to `[fd42:6e69:7800::1]:9100`, `::2`, and `::3`. Change overlay addresses in root and leaf entrypoints and `lab.scrapeTargets` together. Node exporters require the WireGuard service; they cannot fall back to a public bind. Verify a handshake and `curl -g http://[<peer-overlay-ip>]:9100/metrics` from the telemetry node after approval. No public exporter endpoint should answer.

## Grafana access deferred

Grafana listens only on `127.0.0.1:3000`, Prometheus on `127.0.0.1:9090`. There is no public reverse proxy, hostname, DNS or TLS setup and no TCP 80/443 opening. Anonymous access and signup remain disabled. Any later tunnel or public access needs a separate decision. This metrics-only profile has no OTLP receiver.

## Comin rollout

The upstream Comin module and package are pinned together. The repository's `main` branch is the mutable desired-state pointer; Nixpkgs and Comin dependencies remain immutable until a reviewed lock update. `branches.testing.name = ""` disables the default `testing-<hostname>` branch. Debug logging is off. No GitHub token or deploy key is required for the public repository.

Before the first automatic update, keep a cloud console or another recovery path and record a working NixOS generation. Evaluate/build the changed node flake, test on one canary, then merge a small change. Confirm the Comin deployment status, WireGuard handshakes, all three `up{job="nodes"}` values and local Grafana health. Avoid simultaneous network/firewall changes across all nodes. A merge can trigger all enabled nodes; node-specific deployment flags support staged enabling, not a distributed rollout controller.

Comin retries builds twice and retains five successful boot entries. Build or activation success is not application/network-health success. The configuration deliberately makes no automatic rollback claim. For a bad revision, stop Comin from the recovery console, switch to a known-good generation (`nixos-rebuild switch --rollback` when appropriate), revert/fix the bad commit through the reviewed branch process, verify the desired configuration, then restart Comin. Inspect available generations before choosing a rollback target. Retain access until a reboot is verified.

## Capacity qualification

On a 1 GiB host, the OS, filesystem cache, node-exporter, Comin, Grafana and Prometheus share limited memory. Per-service limits are ceilings, not reservations, and their sum can exceed RAM. A 512 MiB Comin evaluation concurrent with both 256 MiB telemetry services can exceed capacity. Prefer prebuilt, trusted outputs and measure evaluation overhead before enabling unattended updates; no new cache credentials or signing keys are configured here.

Collect idle/loaded `systemd-cgtop`, RSS, swap, `memory.events`, OOM logs, Prometheus head-series count/WAL size, disk growth, scrape duration and Grafana latency over at least a full retention window. Include a compaction and a Comin update. Do not declare the host viable from a short idle test. If it cannot fit, keep the capacity gate closed and choose an approved free alternative or a lighter design.
