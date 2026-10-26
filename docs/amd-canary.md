# IPv6 SSH B1s Denmark boot canary

The separate `terraform/amd-canary` root prepares one free-eligible Standard_B1s in Denmark East (`denmarkeast`) and a 64-GiB Premium_LRS (P6) OS disk from the verified x64 gallery image. It is disabled by default. The owner approved unsigned standard Gen2 with Secure Boot/vTPM off and TCP22 from every IPv6 address (`::/0`), with all other inbound denied, for first-boot qualification. The NSG rule alone does not establish usable SSH. The custom-data bootstrap below handles the guest firewall and custom AuthorizedKeysFile; live Azure delivery remains unqualified and Comin remains paused. The selected Robert public key is supplied privately as `ssh_public_key`; password authentication is disabled in Terraform and the image disables root, password and keyboard-interactive login.

The owner selected Denmark East after usable B1s quota was found. B1s has one vCPU and 1 GiB RAM; AMD CPU vendor is not guaranteed. The legacy `amd-canary` root and operation names identify this single x64 test host, not an additional AMD VM. Current availability, one remaining family/regional vCPU quota, Premium IO support, free compute/P6 evidence and completed image replication in the selected region are required. The existing West US 3 image alone does not establish Denmark readiness. No paid SKU or region fallback is automatic. A zero quota or an empty/unreadable quota response fails closed. A quota-support case is separate from deployment.

## Workflow contract

Use protected main-only `cloud.yml` operations `amd-plan` and `amd-apply`, existing fleet-plan/fleet-apply OIDC identities and unchanged trust. Set the separate `AMD_CANARY_ENABLED=explicitly-approved` only after bootstrap readiness. Environment secrets `AMD_BACKEND_CONFIG` and `AMD_TOPOLOGY_JSON` hold private backend/topology values. Missing AMD values do not fall back to legacy fleet values. Existing `PLAN_STORAGE_ACCOUNT`/`PLAN_CONTAINER` identify approved private saved-plan storage. Plan files are never public artifacts.

Backend: private `tfstate` container in the existing fleet storage account, exact key **`fleet/amd-canary/terraform.tfstate`**, OIDC plus Azure AD auth and native blob-lease locking. Do not use `fleet/terraform.tfstate` for this independent root. Bootstrap owner creates/authorizes the container; workflows never grant themselves access or obtain account keys. Scope state access to the container, including lease-compatible write access. Keep exact inventory/public-key values outside Git.

`amd-plan` saves the binary plan, main revision, Terraform root and checksum privately under its run ID. `amd-apply` requires the plan-run ID and reviewed SHA256, verifies both main revision and root, and repeats live SKU/quota checks. Both stages reject delete/replacement actions for the canary. Apply-role scope is create/read/write/join plus instance/boot diagnostics where approved; no delete/lifecycle/extension/RunCommand/IAM-management permissions are assumed. A changed main revision requires a fresh plan. No enabled gate or boolean attestation replaces actual saved-plan review.

Canary state operations serialize separately from image import, allowing independent preparation while ARM import proceeds. This does not authorize concurrent identity edits. Existing gallery versions, staging disks and image source blobs are outside this root.

## Network and acceptance

Proposed dual-stack VNet/subnet use private IPv4 and IPv6. Public addressing is IPv6 only; default outbound IPv4 access is explicitly disabled. No public IPv4, paid NAT, load balancer or peering. The NIC’s NSG allows only TCP22 from `::/0` at priority1000 and denies all remaining inbound at priority4096, before the VM is created. IPv4 SSH is not allowed. `approval.public_ipv6_ssh` must explicitly be true; an old closed-network attestation cannot activate this rule. Managed boot diagnostics are enabled for first-boot evidence; their storage cost belongs in the ancillary estimate and any returned access URLs must stay private.

The initial supplied public key is a private Terraform input, not a new generated credential. No source CIDRs or second key are invented. Azure key delivery into the image's custom AuthorizedKeysFile, IPv6 acquisition/egress, full SSH and Comin activation/reboot still need qualification. VM running state alone does not prove those behaviors.

Total image setup allowance remains $2 across all attempts; monthly ancillary ceiling is $3 including gallery/state/diagnostics. VM and OS disk must remain covered by verified free benefits. Tests and mock plans do not prove entitlement or live capacity.

## Guest SSH bootstrap

The existing pinned Azure image enables cloud-init. Terraform supplies non-secret `custom_data` as cloud-config: it writes the selected public key directly to `/var/lib/fleet-access/authorized_keys` (root-owned 0644), and a root-only per-boot hook. It does not rely on Azure's default home-directory key path. No private key, password, Comin marker, package download, extension or RunCommand is used.

The hook verifies effective sshd policy before allowing access. It installs a runtime systemd firewall drop-in that admits only IPv6 TCP22 and survives firewall restart/reload. Cloud-init recreates the runtime drop-in at every boot; Nix-managed `/etc/systemd/system` is not edited. Comin remains paused. A future NixOS generation must adopt or retire this bootstrap explicitly.

The NixOS `cloud-init-ssh6` test supplies the write-files result and invokes the real cloud-init per-boot runner, then tests key-only SSH, wrong-key/root rejection, firewall restart/reload and reboot. It does not emulate Azure OVF metadata delivery; live cloud-init completion and actual IPv6 reachability still require cloud qualification. Azure VM-ready status does not imply cloud-init success.

Sources: [pinned cloud-init module](https://github.com/NixOS/nixpkgs/blob/da6dc0e7b26060f2f71ce3ef7088fb56ee44fa36/nixos/modules/services/system/cloud-init.nix), [Azure custom data](https://learn.microsoft.com/en-us/azure/virtual-machines/custom-data).

## Bounded saved-plan review output

For the initial canary only, `review-canary-plan.py` rejects anything other than the eight expected create-only resource addresses and the approved B1s/Denmark/P6/IPv6 policy. It validates the exact cloud-init object and bootstrap file without printing either. Cloud-config is emitted as JSON (a YAML-compatible representation) to allow standard-library parsing, avoiding a new runner dependency. No key or secret value is added to Git.

After private binary-plan storage succeeds, the plan job prints only fixed resource facts, the public-key fingerprint, binary SHA256, main revision, run ID and Terraform root/state-key binding. No raw inventory, public key, custom data, outputs or Terraform diagnostics are logged. A rejected summary produces a constant failure message. Apply repeats this contract check against the downloaded saved plan in addition to existing root/revision/hash checks. This is an initial-create review contract: update/no-op/replacement plans are intentionally rejected for separate review. It grants no permissions and does not automatically apply. Changed main requires a new plan; an earlier revision's plan is unusable.

Read-only preflight errors now expose only fixed categories: SKU/usage timeout, read-denied, read-failed, invalid-response, validation or internal failure. SKU enumeration has a bounded 240-second timeout; usage remains 60 seconds. A timeout still prevents planning. This does not establish the cause of the earlier generic preflight failure and does not expand permissions.

Native independent reads measured SKU enumeration at 124.45 seconds and returned quota values as decimal strings. The preflight normalizes only nonnegative integers or ASCII decimal digit strings; booleans, floats, negatives, whitespace and malformed values fail closed. These reads do not prove the GitHub identity has the same query permissions.

The review gate accepts exactly one Ed25519 key record (optional single-line comment; CR/LF rejected before trimming). It validates the planned VM/NIC/NSG/subnet/public-IP graph using exact known IDs and Terraform configuration references plus unknown-value markers for computed IDs. Missing/foreign references or a missing NSG-association dependency fail closed.
