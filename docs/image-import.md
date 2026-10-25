# Upload-first preparation

The verified source revision is `ba51125b3d367b8326b357023a5ad5812239b7a9`. At that revision, native AMD/ARM image inspection, Terraform checks and the 1-GiB x86 VM test passed. CI did not retain the VHDs. A new run must rebuild them: pinned source is reproducible input provenance, not a promise of byte-identical image timestamps, UUIDs or hashes. Hash the actual rebuilt files and preserve those hashes with the imported versions.

Each fixed VHD has an 8-GiB virtual disk and a 512-byte footer: **8,589,935,104 upload bytes**. The old 4-GiB build failed from insufficient space. Both temporary upload disks still fit Standard HDD S4's minimum tier; the OIDC owner's estimate for two disks lasting at most 24 hours is approximately $0.103 plus operations. Temporary private transport holds about 16 GiB total: this exceeds the account's 5-GiB free block-blob allowance while both files coexist, so include prorated blob storage/transactions and any download/egress in the setup estimate. No free-storage claim is made for that stage. Two full 8-GiB gallery replicas have an estimated upper occupied-storage cost around $0.80–0.86/month at the reviewed illustrative rate. Recheck actual region/account prices and remaining benefits before writes.

The owner's ceilings are **$1 initial upload/import and $3/month ancillary**. These are approval limits, not automatic Azure billing caps. VM compute and OS disks must remain within verified free benefits. No paid public IPv4, NAT, extra replicas or paid VM substitutions are selected.

## Stage 1: rebuild and private transport

The proposed `cloud.yml` operation `image-transport` preserves the existing main-only workflow/environment federation. It does not add trust for `images.yml`. It must first land on main under explicit approval; do not dispatch from the PR or expand federation to make it work.

The `fleet-apply` environment must have an approved private transport account/container, exact temporary roles, `IMAGE_TRANSPORT_ENABLED=explicitly-approved` and `IMAGE_TRANSPORT_PLAN_JSON`. The manual input is the SHA256 of that exact private JSON. The plan expires within 24 hours and names:

- `source_revision` (the verified revision above), `subscription_id`, `resource_group`;
- `storage_account`, `container`, unique `prefix`;
- `setup_estimate_usd`, `monthly_ancillary_estimate_usd`, `expires_at`, `approval_reference`.

Keep this inventory outside Git. The account must have shared-key access and anonymous blob access disabled, and the container must be private. The workflow does not change these settings or create the account/container. Identifier values in environment secrets are not shared client secrets. Login uses OIDC only.

Each native runner rebuilds its own architecture from the exact revision, validates the actual VHD and mounted filesystems, then performs the existing Reader scope check. Transport uses `az storage blob ... --auth-mode login`; it never calls listKeys, obtains a storage account key, prints a SAS, or uploads GitHub artifacts. Existing destination blobs are refused, and ambiguous results require a read-only inspection before retry. Blob metadata records source revision, node and rebuilt checksum; content length and metadata are read back. This is transport/provenance verification, not a claim of Azure guest boot or independent remote full-file hashing.

This stage only retains private source files. It **does not create managed disks, gallery versions or VMs**. Keep `FLEET_ENABLED` unset. Failed or completed transport requires an explicit tracked cleanup after successful gallery replication, within the approved setup time/cost envelope. There is no automatic deletion of evidence or rollback of uncertain writes.

## Stage 2: AAD managed-disk import recipe

`scripts/prepare-image-import.py PRIVATE_CONFIG PRIVATE_ARTIFACT_REPORTS PRIVATE_OUTPUT` prepares a mode-0600, hashable recipe; it never invokes Azure. Private configuration names exact subscription/RG, `location=westus3`, gallery, explicit version, distinct `image_definitions` and `staging_disks` for node2/node3, cost estimates/evidence and exact temporary permission approval reference. Reports must contain actual rebuilt `source_revision`, `system`, `virtual_bytes`, `file_bytes`, `sha256`, and successful artifact inspection evidence.

The recipe specifies per-architecture Gen2 managed upload disks with `data-access-auth-mode=AzureActiveDirectory`, Standard_LRS and exact file sizes. After approved short-lived upload access, AzCopy uses the existing Entra/Azure CLI session. Revoke upload access on success or failure. Do not print upload URLs or expose them through shell tracing. Import each disk directly using `az sig image-version create --os-snapshot DISK_ID`, one Full Standard_LRS replica in West US 3. Verify completed replication and persist private provenance before approved deletion of that staging disk and its transport blob. The native OIDC owner controls exact temporary disk/blob/gallery roles and their revocation. No import executor or live import has been run by this preparation.

Image import does **not** require SSH CIDRs, VM network roles, Terraform state or selecting host Secure Boot settings. It creates candidate Gen2 images only. It does require approval of exact temporary resource/role scopes, destinations, cost evidence and cleanup. Definition architecture/Gen2 settings must match the candidate; no public/community gallery is selected.

## Stage 3: VM plan and boot are separate

Use the imported immutable gallery version IDs in a private Terraform topology after boot/security and network/access decisions. The current Terraform Trusted Launch guard remains fail-closed: ARM reports `TrustedLaunchDisabled=True`; AMD support was absent/unverified in captured evidence. No standard-boot/vTPM-off switch was enabled by adding transport code.

Actual first SSH still needs approved source IPv6 CIDRs, a proven Azure public-key provisioning path and guest-firewall access before boot. The image's Comin marker remains absent until reviewed enabled main configuration and access/recovery are ready. No client or second cloud key is invented. State/backend roles, exact two-VM saved-plan hash and live canary tests follow those decisions; they are not prerequisites for private image import.

Official references: [AAD direct managed-disk upload](https://learn.microsoft.com/en-us/azure/virtual-machines/linux/disks-upload-vhd-to-managed-disk-cli), [gallery version CLI](https://learn.microsoft.com/en-us/cli/azure/sig/image-version?view=azure-cli-latest), [Compute Gallery](https://learn.microsoft.com/en-us/azure/virtual-machines/azure-compute-gallery).
