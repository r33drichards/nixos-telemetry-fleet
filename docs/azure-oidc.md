# Selected GitHub-to-Azure federation

Robert selected GitHub OIDC for Actions runners. The cloud workflow uses `id-token: write`, Azure Login and Terraform OIDC authentication; it never accepts an Azure client secret. Client, tenant and subscription IDs are identifiers, not client secrets. The existing GitHub environment secret names for these IDs do not imply a shared secret-based login.

This document and `.github/oidc-subject-template.json` are proposed configuration only. No application/managed identity, federated credential, GitHub subject customization, environment protection or RBAC assignment has been created. Those are persistent security changes requiring approval of the exact bundle below. OIDC selection grants no host spend and no router access.

## Trust proposal

- Issuer: `https://token.actions.githubusercontent.com`
- Audience: `api://AzureADTokenExchange` (explicit in Azure Login; use the same audience for Terraform's OIDC exchange).
- Repository: `r33drichards/nixos-telemetry-fleet`, verified repository ID `1433023017`, owner ID `57335981`.
- Workflow: `.github/workflows/cloud.yml` at `refs/heads/main`.
- Identity type proposed: two Azure user-assigned managed identities in the dedicated fleet RG, one federated credential each; no shared application password.
- Separate environment/principal pairs: `fleet-plan` / `nixos-fleet-plan`, `fleet-apply` / `nixos-fleet-apply`.

Proposed GitHub subject customization: `use_default=false`, `include_claim_keys=["repo","environment","workflow_ref"]`. This adds workflow binding as well as repository/environment binding. It is NOT installed merely by committing the JSON file. Using GitHub's documented immutable naming convention for new repositories, the proposed full subjects are:

```text
repo:r33drichards@57335981/nixos-telemetry-fleet@1433023017:environment:fleet-plan:workflow_ref:r33drichards/nixos-telemetry-fleet/.github/workflows/cloud.yml@refs/heads/main
repo:r33drichards@57335981/nixos-telemetry-fleet@1433023017:environment:fleet-apply:workflow_ref:r33drichards/nixos-telemetry-fleet/.github/workflows/cloud.yml@refs/heads/main
```

No wildcard, pull-request subject, other repository or other workflow is proposed. Before creating grants, inspect current OIDC customization settings and approve the exact template and expected subjects. After authorized setup, verify the non-secret claims against these strings without logging the JWT. If GitHub's emitted format differs, stop and review; do not broaden Azure trust. No OIDC token has been requested just to test this proposal.

Both environments must restrict deployment to main and have an approved reviewer policy. A dispatcher cannot self-approve if self-review is disabled; select an independent reviewer or explicitly choose another review policy. The reviewer is not yet selected. The workflow's main/ref and `FLEET_ENABLED` checks are additional guards, not replacements for protected environments or authorization.

## Least-privilege role proposal

All host resources, referenced images and existing NICs must be in the dedicated approved fleet resource group for this minimal scope. The group name proposed for review is `rg-nixos-fleet-west`; it is not created and the subscription/resource-group IDs are unresolved. Do not reuse the separate router resource group or identity. No subscription-wide Owner, Contributor, role-assignment or provider-registration permission is proposed.

| Principal | Resource scope | Proposed role |
|---|---|---|
| `nixos-fleet-plan` | Exact fleet RG only | Reader |
| `nixos-fleet-plan` | Exact `tfstate` container only | Storage Blob Data Contributor, needed for backend leases/read/write |
| `nixos-fleet-plan` | Exact `tfplans` container only | Storage Blob Data Contributor for private saved-plan upload |
| `nixos-fleet-apply` | Exact fleet RG only | Custom `FleetHostApply`, actions below |
| `nixos-fleet-apply` | Exact `tfstate` container only | Storage Blob Data Contributor |
| `nixos-fleet-apply` | Exact `tfplans` container only | Storage Blob Data Reader |

Proposed `FleetHostApply` actions (no DataActions):

```text
Microsoft.Resources/subscriptions/resourceGroups/read
Microsoft.Compute/virtualMachines/read
Microsoft.Compute/virtualMachines/write
Microsoft.Compute/virtualMachines/delete
Microsoft.Compute/virtualMachines/instanceView/read
Microsoft.Compute/virtualMachines/start/action
Microsoft.Compute/virtualMachines/powerOff/action
Microsoft.Compute/virtualMachines/restart/action
Microsoft.Compute/virtualMachines/deallocate/action
Microsoft.Compute/disks/read
Microsoft.Compute/disks/write
Microsoft.Compute/disks/delete
Microsoft.Compute/images/read
Microsoft.Compute/galleries/read
Microsoft.Compute/galleries/images/read
Microsoft.Compute/galleries/images/versions/read
Microsoft.Network/networkInterfaces/read
Microsoft.Network/networkInterfaces/join/action
Microsoft.Network/networkSecurityGroups/read
Microsoft.Network/publicIPAddresses/read
Microsoft.Network/virtualNetworks/read
Microsoft.Network/virtualNetworks/subnets/read
Microsoft.Network/virtualNetworks/subnets/join/action
```

The new live SKU preflight additionally requires subscription-scoped `Microsoft.Compute/skus/read`. That read-only metadata exception needs separate approval for the relevant principals; it grants no resource writes. No such permission was added. Until approved, the preflight fails closed.

This is a candidate action set for the existing-NIC/image VM module, not a live-validated grant. If provider initialization or operations require more metadata reads, report the exact denied action and scope for review; never silently assign a broader role. VM Contributor is not substituted because it includes broader VM execution/NIC-management powers. Network provisioning, image upload, state-account creation and role assignment are excluded and require separate approved actions.

## State and remaining decisions

Proposed state storage: dedicated `rg-nixos-fleet-state-westus2`, westus2 Standard_LRS GPv2 account (globally unique name still undecided), private containers `tfstate` and `tfplans`, state key `fleet/terraform.tfstate`. Azure Blob leases provide locking. Use Azure AD data-plane access, HTTPS, no anonymous blob access, no SAS/account keys, and no public Actions artifacts. No private endpoint or paid network service is implicitly selected. Storage costs and allowed runner access still need approval.

Before action-time approval, fill in: exact subscription ID; existing/new fleet RG and state container resource IDs; managed-identity resource/client IDs; independent reviewer; confirmed free host/disk/image/egress/storage eligibility; boot-qualified image IDs; approved network/access and runtime-secret delivery. The router's $10 budget covers none of this fleet spending. The current Azure module still requires exactly two approved hosts and a zero-cost attestation; no single-node shortcut has been enabled.

Official references: [GitHub OIDC claims/customization](https://docs.github.com/en/actions/reference/security/oidc), [Azure Login OIDC](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-azure), [AzureRM backend roles and locking](https://developer.hashicorp.com/terraform/language/backend/azurerm).
