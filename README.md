# nixos-telemetry-fleet

Three minimal NixOS node flakes with IPv6, WireGuard, Comin updates from `main`, and private node-exporter metrics. Node 2 collects metrics with Prometheus and provisions a Grafana dashboard. Grafana access is deferred: it remains loopback-only with no public proxy or ingress.

**Nothing is deployed.** Node services, network changes, and public ingress are disabled until hardware, access, network and telemetry-capacity approvals are recorded. No secrets belong in Git, including encrypted payloads (sops/agenix). No live IP inventory, WireGuard keys, Grafana password, cloud credentials or state is in this repository.

| Flake | Architecture | Candidate role |
|---|---|---|
| `nodes/node1` | x86_64-linux | Node exporter; possible B1s worker |
| `nodes/node2` | x86_64-linux | Prometheus + Grafana + node exporter; possible B2ats_v2 |
| `nodes/node3` | aarch64-linux | Node exporter; possible B2pts_v2 |

These Azure assignments are candidates, not capacity reservations or verified free entitlements. Change `system` in both the leaf flake and root fleet entrypoint if the approved placement differs. The three node flakes share `common/`; clone the whole repository, not a single subdirectory.

## Local validation

Use Nix 2.30 or newer with flakes and Python 3. The newer Nix version supports the relative shared flake inputs used here. Every external input is commit/hash pinned in the four lockfiles.

```sh
make check       # local structural tests; no cloud access
make eval        # root + all three leaf flakes, no build or activation
make profile-check # enabled profiles, approval gates, private binds and runtime credentials
nix eval ./nodes/node2#nixosConfigurations.node2.config.services.comin.remotes --json
nix build ./nodes/node1#nixosConfigurations.node1.config.system.build.toplevel --no-link
```

Builds can download packages and use substantial local RAM/disk. No `nixos-rebuild switch`, SSH, cloud API, Terraform apply, or credential creation is part of these commands. See [validation](docs/validation.md) for completed checks and limitations.

## Before deployment

1. Confirm each host's free compute/disk/network entitlement, architecture and region. Supply a tested hardware module; current EFI/root-label settings are evaluation fixtures. Azure ARM boot and Secure Boot are unresolved; do not disable Secure Boot implicitly.
2. Approve the uplink interface, IPv6 address/routing, IPv4 download reachability, WireGuard peers/UDP port/MTU, private overlay addresses, access recovery, and bandwidth costs. The `fd42:6e69:7800::/64` addresses are example private addresses, not live inventory.
3. Deliver root-only WireGuard configuration to `/var/lib/fleet-secrets/wg0.conf` out of band. It must contain the matching node overlay IPv6, listen port 51820, approved IPv6 peer endpoints, private key, and each peer's `/128` AllowedIPs. Use durable root-owned files, mode 0600, in the mode-0700 directory. systemd loads private runtime copies after the backing filesystem mounts on each boot. Nothing reads this file during Nix evaluation.
4. For node 2, deliver the Grafana admin password to `/var/lib/fleet-secrets/grafana-admin-password` and a persistent encryption key to `/var/lib/fleet-secrets/grafana-secret-key` through an approved secret channel. systemd `LoadCredential` gives Grafana a private runtime copy. The initial admin login is `admin`; the password is never generated or embedded here.
5. Review and test the metrics resource experiment. Set node-specific `deployment.nix` approval flags only after approval. Keep deployment intent tracked so Comin's next update does not undo private one-off overrides. Runtime peer addresses and keys stay outside Git.
6. Manually bootstrap one canary over an approved recovery-capable access path. Check its WireGuard handshake, metrics, reboot, and Comin before enabling the other nodes. See [operations](docs/operations.md).

Grafana anonymous access and signup are disabled. Grafana/Prometheus are loopback-only; exporters listen only on their WireGuard IPv6 addresses. Public Grafana access, DNS and TLS are deferred. Exporter, Prometheus and Grafana backend ports are not opened publicly. WireGuard peer possession is the access boundary for metrics.

The dashboard **Three NixOS nodes** shows exporter health, CPU, available memory and root filesystem space. Its instance selector discovers all three scrape targets. Prometheus scrapes each node every 60 seconds and keeps at most 24 hours/256 MB of samples, whichever limit applies first; WAL and other data can exceed the retention-size setting.

## Updates and resource limits

Comin uses public HTTPS without a token, polls `main` every 60 seconds, selects the matching leaf flake/hostname, and applies successful builds with `switch`. Testing branches are disabled. It tracks all changes to `main`, so protect the branch and require review/checks; it cannot distinguish a merge from a direct push. No GitHub branch protection has been installed automatically.

Five successful boot generations are retained. This provides manual rollback, **not automatic network-health rollback**. A broken network update can still lock out a host. Read the [canary and recovery procedure](docs/operations.md) before enabling automatic updates.

Grafana and Prometheus each have a 256 MiB hard limit and 160 MiB soft limit; node-exporter has a 48 MiB hard limit. Comin's evaluation/build budget is capped at 512 MiB. Limits can kill workloads and do not prove the combined system fits 1 GiB. Sustained ingestion, compaction, dashboard queries and concurrent Nix evaluation still need testing on the selected host. Metrics-only replaces full LGTM by agreement; Loki, Tempo and Pyroscope are not included.

The previous Kubernetes/Knative/Wasm prototype is preserved on local branch `archive/knative-prototype`; it is outside the current deliverable. Terraform host modules, protected manual cloud workflows, and a real NixOS/Wasm VM E2E are now under development; see [orchestration and approval bundle](docs/orchestration.md). Public repository: [r33drichards/nixos-telemetry-fleet](https://github.com/r33drichards/nixos-telemetry-fleet). Pi created the repository through the authorized #wchat workflow.

## Host orchestration and Wasm qualification

Run `nix build -L .#checks.x86_64-linux.boot-overlay-wasm` on a KVM-capable Linux builder. This tests real NixOS guests and private Wasm HTTP; it does not deploy a cloud cluster. Terraform defaults to zero hosts, and the manual cloud workflow needs separately approved identity, private state storage and a reviewed saved plan. No Kubernetes, Knative or MCPJS service is enabled by this change.
