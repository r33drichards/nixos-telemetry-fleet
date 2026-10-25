# nixos-telemetry-fleet

Current scope: **two bare Azure NixOS hosts, one AMD and one ARM, with SSH and Comin updates from `main`.** No Wasm/Spin, Kubernetes, Grafana, Prometheus, exporter or WireGuard service is required or enabled by the active profile. Earlier modules and tests are retained as optional source only. The repository keeps its existing name.

**Nothing is deployed by these defaults.** Host, network and hardware approvals remain false. No secrets belong in Git, even encrypted payloads. No private keys, cloud credentials or Terraform state are committed.

| Entrypoint | Architecture | Proposed host |
|---|---|---|
| `nodes/node2` | x86_64-linux | Standard_B2ats_v2, candidate westus3/Phoenix |
| `nodes/node3` | aarch64-linux | Standard_B2pts_v2, candidate westus3/Phoenix |
| `nodes/node1` | x86_64-linux | Inactive retained template |

Azure is the only provider. Each selected SKU needs its own verified remaining free allowance. Two identical continuously running instances cannot each claim the same 750-hour meter. Two P6 disks may fit the allowance; image/state/network costs remain unverified. ARM standard boot versus Trusted Launch is still an explicit decision: the current Terraform module does not silently disable Secure Boot/vTPM.

Use Nix 2.30+ with flakes, Python 3 and Terraform 1.14.0:

```sh
make check                 # local guard tests
make eval profile-check    # pinned fleet and bare profile evaluation
make vm-e2e                # real boot/SSH/Comin update/reboot test
make tf-check              # disabled-default Terraform validation/mock tests
```

SSH accepts public-key authentication for `operator` only. Root login, passwords and keyboard-interactive authentication are disabled. Supply approved source CIDRs in `lab.sshSourceCIDRs`; no global port-22 opening is assumed. The Azure NSG/access route must be separately approved. Deliver authorized public keys outside Git to root-owned `/var/lib/fleet-access/authorized_keys`, mode 0644, parent mode 0755. These are public keys, not private credentials. Client private keys stay outside the hosts/repository. Verify host keys through the approved provisioning/recovery channel. No passwordless sudo privilege is added.

Comin reads the public HTTPS repository without a token, selects the host's leaf flake, tracks only `main`, polls every 60 seconds and switches successful builds. Testing branches are disabled; debug logging is off. Retained generations permit operator recovery but do not provide automatic network-health rollback. Evaluate/build memory is capped; actual 1-GiB rebuild capacity still needs qualification. A trusted prebuilt closure can reduce host build load.

The VM test uses disposable runtime SSH keys and a local Git remote. It advances `main` to a real NixOS generation, exercises Comin evaluation/build/switch using a CI-prebuilt closure, then verifies persistence through a bootloader reboot. It does not claim a full in-guest source build, Azure/ARM boot, or live GitHub delivery has been tested. Earlier telemetry/Wasm results do not qualify this new scope.

GitHub Actions offers protected plan/apply, live SSH E2E, and a separate read-only `oidc-check`. The Reader-only bootstrap identity cannot deploy VMs. Exact deployment roles, state, images, network and saved-plan approval must follow separately. See [orchestration](docs/orchestration.md) and [OIDC proposal](docs/azure-oidc.md). The assigned OIDC worker owns setup; no duplicate grants are created here.

## Host-specific Azure images

`nix build .#packages.x86_64-linux.azure-node2` and `nix build .#packages.aarch64-linux.azure-node3` use the pinned official NixOS Azure fixed-VHD builder, Gen2/GPT/UEFI, and the matching host architecture. Each image fixes its hostname, public repository and `nodes/<hostname>` Comin flake path while intentionally following `main`. Build inputs stay locked. These unsigned upstream images are **not Trusted Launch qualified**; creating them does not select or approve standard boot for deployment.

Image SSH ingress has no approved source rule or baked authorized key. Comin requires `/var/lib/fleet-access/bootstrap-approved` before activation; create that marker only after the correct bare host configuration has landed on main and access/recovery is approved. This avoids switching a new image to an older or still-disabled main profile. Runtime public-key delivery, source CIDRs and platform provisioning integration must be qualified before upload/host creation. No private credentials are in the image.

The image workflow builds both architectures and validates actual fixed-VHD footer/checksum/alignment, GPT, EFI architecture filename, host-specific configuration and absence of baked SSH host private keys. It uses native public runners; ARM image construction uses QEMU TCG where KVM is unavailable. VHDs remain ephemeral runner outputs pending an approved durable destination: no Azure upload or paid artifact storage is configured. A format check is not an Azure boot test.
