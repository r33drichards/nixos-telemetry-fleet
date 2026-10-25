# Terraform and E2E orchestration

This restores host IaC around the minimal fleet. Azure remains the original provider candidate; GCP was an optional free-worker fallback and Oracle was research only. No provider/account/region has been newly selected. Azure's observed two-disk allowance does not yet cover three boot disks; do not set the free-entitlement gate based on trial credits. The separate router resource group is outside this module and must not be targeted.

## What is tested

`nix build -L .#checks.x86_64-linux.boot-overlay-wasm` boots two real x86 NixOS QEMU guests in a private test network. It generates disposable test-only WireGuard keys in guest files at runtime, establishes an IPv6 tunnel, checks actual Spin/Wasm HTTP and exporter metrics over the tunnel, rejects underlay HTTP access, and verifies persistence after reboot. No key payload is in Git or the Nix store. Test guests have 1536 MiB RAM; this is not proof of the proposed 1 GiB hosts or ARM boot. Comin switching is deliberately outside this isolated test; the real-cloud check requires the Comin service active, not a proven update/rollback cycle.

The first Actions revision intentionally imported a missing Wasm module and failed. Keep the test assertions intact as implementation follows. The Spin 4.1.0 x86 host runtime and upstream static-fileserver Wasm component are SHA-256 pinned. This is a native Linux process running a Wasm component, not Kubernetes RuntimeClass, Knative, or MCPJS. No MCPJS repository, application or execution contract has been supplied. Earlier k3s/Knative work remains on local `archive/knative-prototype`; a supported free control plane is still unresolved.

`Terraform checks` runs formatting, validation and mock-provider plan tests without cloud credentials. These are not real cloud plans. `NixOS VM E2E` has no cloud identity permission. Both run on PRs; neither job can provision Azure. All GitHub actions are commit-pinned.

## Live orchestration, disabled until approved setup

The manual `Approved Azure host orchestration` workflow accepts `plan`, `apply`, or `e2e`. It only accepts `main`, and requires environment variable `FLEET_ENABLED=explicitly-approved`. Do not configure this until the exact action is authorized. This string is an additional guard, not proof of authorization.

Before use, create protected environments `fleet-plan`, `fleet-apply`, `fleet-e2e` with required reviewers, prevent self-review and restrict deployment branches to main. The workflow cannot establish its own review protection. No environment, OIDC identity, role grant or runner has been created by this PR.

GitHub OIDC federation is the selected authentication method. Use distinct OIDC identities for plan and apply, with no shared client secret. See [the exact proposed trust and role bundle](azure-oidc.md); the checked-in subject template is a proposal and has not been applied. Bind issuer, audience and the actual repository/environment subject from GitHub's current OIDC claims, not a guessed legacy subject string. Limit apply identity to the approved fleet RG; plan identity needs read access plus backend blob lease/write rights. No automatic provider registration. Backend storage has no public blob access, uses Azure AD authentication and blob lease state locking; assign data-plane permissions only on the specific state/plan containers. Storage/transactions are not assumed free and must fit the approved cost boundary.

Environment secret values (outside Git): `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `TF_BACKEND_CONFIG` (backend resource group, storage account, container and state key), `TF_TOPOLOGY_JSON` (private non-secret host inventory), `PLAN_STORAGE_ACCOUNT`, `PLAN_CONTAINER`. Do not put WireGuard keys, passwords or bootstrap credentials in Terraform inputs, custom_data, state, outputs or plan files. Host secrets stay in root-only persistent host files and are supplied separately as described in operations.md. GitHub holds no host private keys in this design.

Plans and state are private data. The workflow redirects Terraform output away from public logs and uploads saved plans, source revision and checksums to the approved private blob container, never public Actions artifacts. Review `terraform show` through an approved private operator environment. Apply downloads the same plan, checks both its SHA-256 and source revision, then applies that exact plan under state locking. It does not replan. Protect the blob container from unrelated writers and configure a short approved retention policy. On failed/partial apply, inspect state before retry; no automatic destroy or retry is configured.

The module creates exactly three enabled VMs plus their OS disks from existing approved NICs and image IDs. Secure Boot and vTPM remain enabled. It does not create networks, NICs, DNS, public IPs, resource groups, images, accounts, OIDC grants, or state storage. A NixOS image with working boot, SSH provisioning, approved access and recovery must exist first. Generic leaf boot fixtures are not deployable cloud images. Upstream Azure Gen2 image compatibility with Secure Boot and ARM remains a blocker, not grounds to silently disable it.

After approval, enable the selected node modules and `lab.wasm.enable` only on an x86 node; ARM runtime packaging remains unqualified. Deliver runtime secrets out of band, bootstrap one canary and verify reboot/recovery before completing the fleet. Comin follows the approved main branch. No bootstrap remote-exec provisioner or secret-bearing cloud-init is used.

## Actual cloud E2E

A dedicated ephemeral self-hosted runner labeled `fleet-e2e` must have separately approved private reachability. Never expose it to PR workflows. Deliver `/run/fleet/inventory.json`, `/run/fleet/ssh_key` and verified `/run/fleet/known_hosts` outside Git with restrictive permissions. `python3 scripts/cloud-e2e.py /run/fleet/inventory.json` requires three distinct actual NixOS machine identities at the workflow source revision, unscoped ULA overlay addresses, active WireGuard/Comin/exporters, every cross-node metrics path, and an exact HTTP response from an actual Wasm service. Missing inventory or connectivity fails; there are no skips. It does not perform a disruptive live reboot or claim Knative/MCPJS coverage. Private SSH diagnostics remain outside public logs.

## Exact next approval bundle

1. Confirm Azure or explicitly choose another provider; choose three named host shapes/architectures/regions near California, dedicated fleet RG, existing NIC IDs and image IDs. Verify every compute/disk/image/storage/egress entitlement and expiry, including the third disk, with a zero incremental cost limit and no billing upgrade. This remains unresolved.
2. Approve the image boot/Secure Boot/ARM qualification plan and initial administrator/recovery path. Approve exact WireGuard endpoints, UDP51820, private overlay routes and SSH source scope. No public Grafana, DNS or TLS work is included.
3. Approve private state/plan storage resources and costs, protected GitHub environments/reviewers, exact OIDC subjects and least-privilege role scopes. Do not include the unrelated router RG. Approve the ephemeral E2E runner's private access and lifetime.
4. Approve one-time delivery of persistent host secrets and runner credentials outside Git, plus the owner-controlled backup destination. No external secret manager is selected.
5. Review a private real Terraform plan at a fixed main SHA, approve its SHA-256 and exact creates/changes, and set a maximum test lifetime with an independently reviewed cleanup plan. Only then dispatch apply. A passing local VM test is not this approval.

References: [AzureRM backend and locking](https://developer.hashicorp.com/terraform/language/backend/azurerm), [GitHub Azure OIDC](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-azure), [NixOS VM tests](https://nixos.org/manual/nixos/stable/#sec-nixos-tests), [Azure VM provider](https://registry.terraform.io/providers/hashicorp/azurerm/4.51.0/docs/resources/linux_virtual_machine).
