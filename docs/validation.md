# Validation record

## Terraform and Wasm E2E development

Initial Actions run 40228914573 at commit `87361e05616d09c31afd33b79ab7db76c5adf00f` failed because `common/modules/wasm.nix` was absent. This establishes the red test before implementation. Terraform root/module validation and all three mock-provider tests pass locally; Actions Terraform run 40229114257 also passed. The real VM E2E implementation is being qualified in PR #1; do not infer a pass until the exact final head's run completes.

The cached Spin archive, extracted executable and upstream Wasm component were hash-verified and a fresh local loopback HTTP smoke test returned 200 and the exact `hello from wasm` body. This does not establish NixOS boot or cloud networking. Missing cloud inventory fails the live E2E script rather than skipping.

The cloud workspace lacks `/dev/kvm` and QEMU. Its cache.nixos.org request is denied by the proxy with HTTP 403 even on the host. GitHub HTTPS works with the host trust store, while the disposable Nix container reported an untrusted certificate chain despite readable CA files. These are separate network-policy and container-trust problems; certificate verification was never disabled, proxy routing was not bypassed, and no CA trust changes were made. The authorized GitHub runner successfully downloaded pinned inputs and has KVM, so VM qualification runs there.

## Earlier host-local secret revision

Public Grafana configuration was removed; access is deferred. Secret source defaults now use durable `/var/lib/fleet-secrets` files, loaded through systemd credentials for WireGuard and Grafana. Four structural tests and whitespace checks pass. Nix 2.30.2 parses all changed Nix files successfully. Full evaluation of this revision is BLOCKED: the container proxy rejected cache.nixos.org with HTTP 403 and the uncached GitHub source failed certificate verification. Available local source excerpts are incomplete and cannot replace the pinned inputs. Earlier evaluation results below apply only to the earlier snapshot; rerun `make eval profile-check` when the pinned inputs are accessible. No real credentials were created and no host was activated.

## Earlier published snapshot

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
