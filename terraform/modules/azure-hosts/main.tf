resource "terraform_data" "approval" {
  count = var.enabled ? 1 : 0
  lifecycle {
    precondition {
      condition     = var.approval.free_entitlement_verified && var.approval.image_boot_verified && var.approval.network_access_approved && var.approval.monthly_cost_usd == 0 && length(var.approval.evidence_reference) > 0 && length(var.nodes) == 3
      error_message = "Three approved hosts, strictly-free entitlement, tested image/Secure Boot and network/access evidence are required. Credits do not count as free entitlement."
    }
  }
}
resource "azurerm_linux_virtual_machine" "node" {
  for_each                        = var.enabled ? var.nodes : {}
  name                            = each.key
  location                        = each.value.location
  zone                            = each.value.zone
  resource_group_name             = each.value.resource_group_name
  size                            = each.value.size
  source_image_id                 = each.value.source_image_id
  network_interface_ids           = [each.value.network_interface_id]
  admin_username                  = "operator"
  disable_password_authentication = true
  secure_boot_enabled             = true
  vtpm_enabled                    = true
  provision_vm_agent              = true
  allow_extension_operations      = false
  admin_ssh_key {
    username   = "operator"
    public_key = each.value.ssh_public_key
  }
  os_disk {
    caching              = "ReadWrite"
    storage_account_type = each.value.disk_type
    disk_size_gb         = each.value.disk_gib
  }
  tags       = { project = "nixos-telemetry-fleet", managed_by = "terraform" }
  depends_on = [terraform_data.approval]
}
output "node_count" { value = length(azurerm_linux_virtual_machine.node) }
