# Closed B1s Denmark boot canary

The separate `terraform/amd-canary` root prepares one free-eligible Standard_B1s in Denmark East (`denmarkeast`) and a 64-GiB Premium_LRS (P6) OS disk from the verified x64 gallery image. It is disabled by default. The owner approved unsigned standard Gen2 with Secure Boot/vTPM off and deny-all inbound for first-boot qualification. This is not yet usable SSH or active Comin: the existing image's guest access and Comin marker remain closed/absent.

The owner selected Denmark East after usable B1s quota was found. B1s has one vCPU and 1 GiB RAM; AMD CPU vendor is not guaranteed. The legacy `amd-canary` root and operation names identify this single x64 test host, not an additional AMD VM. Current availability, one remaining family/regional vCPU quota, Premium IO support, free compute/P6 evidence and completed image replication in the selected region are required. The existing West US 3 image alone does not establish Denmark readiness. No paid SKU or region fallback is automatic. A zero quota or an empty/unreadable quota response fails closed. A quota-support case is separate from deployment.

## Workflow contract

Use protected main-only `cloud.yml` operations `amd-plan` and `amd-apply`, existing fleet-plan/fleet-apply OIDC identities and unchanged trust. Set the separate `AMD_CANARY_ENABLED=explicitly-approved` only after bootstrap readiness. Environment secrets `AMD_BACKEND_CONFIG` and `AMD_TOPOLOGY_JSON` hold private backend/topology values. Missing AMD values do not fall back to legacy fleet values. Existing `PLAN_STORAGE_ACCOUNT`/`PLAN_CONTAINER` identify approved private saved-plan storage. Plan files are never public artifacts.

Backend: private `tfstate` container in the existing fleet storage account, exact key **`fleet/amd-canary/terraform.tfstate`**, OIDC plus Azure AD auth and native blob-lease locking. Do not use `fleet/terraform.tfstate` for this independent root. Bootstrap owner creates/authorizes the container; workflows never grant themselves access or obtain account keys. Scope state access to the container, including lease-compatible write access. Keep exact inventory/public-key values outside Git.

`amd-plan` saves the binary plan, main revision, Terraform root and checksum privately under its run ID. `amd-apply` requires the plan-run ID and reviewed SHA256, verifies both main revision and root, and repeats live SKU/quota checks. Both stages reject delete/replacement actions for the canary. Apply-role scope is create/read/write/join plus instance/boot diagnostics where approved; no delete/lifecycle/extension/RunCommand/IAM-management permissions are assumed. A changed main revision requires a fresh plan. No enabled gate or boolean attestation replaces actual saved-plan review.

Canary state operations serialize separately from image import, allowing independent preparation while ARM import proceeds. This does not authorize concurrent identity edits. Existing gallery versions, staging disks and image source blobs are outside this root.

## Network and acceptance

Proposed dual-stack VNet/subnet use private IPv4 and IPv6. Public addressing is IPv6 only; default outbound IPv4 access is explicitly disabled. No public IPv4, paid NAT, load balancer or peering. The NIC's NSG denies all inbound at priority4096 before the VM is created. Managed boot diagnostics are enabled for first-boot evidence; their storage cost belongs in the ancillary estimate and any returned access URLs must stay private.

The initial supplied public key is a private Terraform input, not a new generated credential. No source CIDRs or second key are invented. Azure key delivery into the image's custom AuthorizedKeysFile, IPv6 acquisition/egress, full SSH and Comin activation/reboot still need qualification. VM running state alone does not prove those behaviors.

Total image setup allowance remains $2 across all attempts; monthly ancillary ceiling is $3 including gallery/state/diagnostics. VM and OS disk must remain covered by verified free benefits. Tests and mock plans do not prove entitlement or live capacity.
