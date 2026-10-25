# Validation record

Cloud workspace, 2026-10-25. No machine, network, account, credential, DNS record or cloud resource was created or modified.

- PASS: root fleet flake and each of the three standalone node flakes evaluated with Nix 2.30.2, using generated lockfiles. The three configurations cover x86_64 and aarch64.
- PASS: four Python structural checks: consistent external pins, disabled deployment defaults, provisioned dashboard structure, and no tracked secret/state files.
- PASS: enabled-profile checks (`make profile-check`). These evaluate all enabled nodes and the public HTTPS variant without activation, test approval failure, inspect private binds, runtime credential references and disabled testing branches.
- Nix evaluation caught the NixOS 26.05 requirement for a Grafana database-encryption key. The configuration now uses a second runtime systemd credential and documents persistent delivery/backup.
- A temporary validation-container inode limit interrupted an earlier run. Only disposable artifacts from this task were cleaned before retrying.

Not run: full system closure builds; NixOS boots; actual WireGuard handshakes/routing/MTU; cross-architecture execution; Comin fetch/build/switch on a live node; sustained telemetry resource measurements; provider entitlement or image verification; public DNS/ACME/HTTPS; Grafana account creation/login; real three-host scrape/dashboard tests.

The resource ceilings are experimental configuration, not proof that Grafana/Prometheus plus Comin fits a 1 GiB machine. The capacity gate remains false. No benchmark or fit claim is made.

The archived Knative branch had separate Terraform, Nix, and local Wasm tests. Those results do not validate this telemetry deployment and are not used as evidence here.

Evaluated package versions: Grafana 13.0.11, Prometheus 3.12.0, node-exporter 1.11.1. Evaluation includes enabled x86/ARM nodes, an HTTPS variant with documentation-only hostname, and the standalone leaf configurations. No certificate request is made by evaluation.
