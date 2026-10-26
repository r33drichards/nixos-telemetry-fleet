# First-boot qualification with explicitly approved IPv6-only, key-only SSH.
# Guest key delivery/firewall qualification is required; Comin stays paused.
variable "enabled" { default = false }
variable "location" {
  type    = string
  default = "denmarkeast"
  validation {
    condition     = contains(["denmarkeast", "westus", "westus2", "westus3", "centralus", "eastus", "eastus2", "northcentralus", "southcentralus", "westcentralus"], var.location)
    error_message = "Select Denmark East or a reviewed US Azure region; quota, free entitlement and image replication must be verified there."
  }
}
variable "subscription_id" { type = string }
variable "resource_group_name" { type = string }
variable "image_version_id" { type = string }
variable "ssh_public_key" { type = string }
variable "approval" {
  type    = object({ standard_unsigned_gen2 = bool, public_ipv6_ssh = bool, free_compute_and_p6 = bool, quota_capacity_checked = bool, state_and_roles = bool, image_region_ready = bool, monthly_ancillary_usd = number, evidence = string })
  default = { standard_unsigned_gen2 = false, public_ipv6_ssh = false, free_compute_and_p6 = false, quota_capacity_checked = false, state_and_roles = false, image_region_ready = false, monthly_ancillary_usd = 0, evidence = "" }
}
locals {
  approved = var.approval.standard_unsigned_gen2 && var.approval.public_ipv6_ssh && var.approval.free_compute_and_p6 && var.approval.quota_capacity_checked && var.approval.state_and_roles && var.approval.image_region_ready && var.approval.monthly_ancillary_usd >= 0 && var.approval.monthly_ancillary_usd <= 3 && length(var.approval.evidence) > 0
  create   = var.enabled && local.approved
}
resource "terraform_data" "approval" {
  count = var.enabled ? 1 : 0
  lifecycle {
    precondition {
      condition     = local.approved
      error_message = "Explicit unsigned Gen2, public IPv6 TCP22, free B1s/P6, quota, state/RBAC and <=$3 monthly evidence are required."
    }
  }
}
resource "azurerm_virtual_network" "fleet" {
  count               = local.create ? 1 : 0
  name                = "vnet-nixos-fleet-${var.location}"
  location            = var.location
  resource_group_name = var.resource_group_name
  address_space       = ["10.78.0.0/16", "fd42:6e69:7800::/48"]
}
resource "azurerm_subnet" "fleet" {
  count                           = local.create ? 1 : 0
  name                            = "bare-hosts"
  resource_group_name             = var.resource_group_name
  virtual_network_name            = azurerm_virtual_network.fleet[0].name
  address_prefixes                = ["10.78.1.0/24", "fd42:6e69:7800:1::/64"]
  default_outbound_access_enabled = false
}
resource "azurerm_network_security_group" "closed" {
  count               = local.create ? 1 : 0
  name                = "nsg-nixos-node2-ssh6"
  location            = var.location
  resource_group_name = var.resource_group_name
  security_rule {
    name                       = "AllowIPv6KeyOnlySSH"
    priority                   = 1000
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = "::/0"
    destination_address_prefix = "*"
  }
  security_rule {
    name                       = "DenyAllInbound"
    priority                   = 4096
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}
resource "azurerm_public_ip" "node2" {
  count               = local.create ? 1 : 0
  name                = "pip6-nixos-node2"
  location            = var.location
  resource_group_name = var.resource_group_name
  allocation_method   = "Static"
  sku                 = "Standard"
  ip_version          = "IPv6"
}
resource "azurerm_network_interface" "node2" {
  count               = local.create ? 1 : 0
  name                = "nic-nixos-node2"
  location            = var.location
  resource_group_name = var.resource_group_name
  ip_configuration {
    name                          = "private-ipv4"
    primary                       = true
    subnet_id                     = azurerm_subnet.fleet[0].id
    private_ip_address_allocation = "Dynamic"
    private_ip_address_version    = "IPv4"
  }
  ip_configuration {
    name                          = "public-ipv6"
    primary                       = false
    subnet_id                     = azurerm_subnet.fleet[0].id
    private_ip_address_allocation = "Dynamic"
    private_ip_address_version    = "IPv6"
    public_ip_address_id          = azurerm_public_ip.node2[0].id
  }
}
resource "azurerm_network_interface_security_group_association" "closed" {
  count                     = local.create ? 1 : 0
  network_interface_id      = azurerm_network_interface.node2[0].id
  network_security_group_id = azurerm_network_security_group.closed[0].id
}
resource "azurerm_linux_virtual_machine" "node2" {
  count                 = local.create ? 1 : 0
  name                  = "nixos-node2"
  location              = var.location
  resource_group_name   = var.resource_group_name
  size                  = "Standard_B1s"
  priority              = "Regular"
  source_image_id       = var.image_version_id
  network_interface_ids = [azurerm_network_interface.node2[0].id]
  # Public key and fixed bootstrap code only; never put secrets in custom data.
  custom_data = base64encode("#cloud-config\n${jsonencode({
    disable_root = true
    ssh_pwauth   = false
    write_files = [
      { path = "/var/lib/fleet-access/authorized_keys", owner = "root:root", permissions = "0644", content = "${trimspace(var.ssh_public_key)}\n" },
      { path = "/var/lib/cloud/scripts/per-boot/fleet-ssh6", owner = "root:root", permissions = "0700", content = file("${path.module}/bootstrap/ssh6-per-boot.sh") }
    ]
  })}")
  admin_username                  = "operator"
  disable_password_authentication = true
  secure_boot_enabled             = false # Only reachable after explicit standard_unsigned_gen2 approval.
  vtpm_enabled                    = false
  provision_vm_agent              = true
  allow_extension_operations      = false
  admin_ssh_key {
    username   = "operator"
    public_key = var.ssh_public_key
  }
  os_disk {
    name                 = "os-nixos-node2"
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
    disk_size_gb         = 64
  }
  boot_diagnostics {}
  tags       = { project = "nixos-telemetry-fleet", purpose = "ssh6-boot-canary", managed_by = "terraform" }
  depends_on = [terraform_data.approval, azurerm_network_interface_security_group_association.closed]
}
output "node_count" { value = length(azurerm_linux_virtual_machine.node2) }
