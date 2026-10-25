variable "enabled" {
  type    = bool
  default = false
}
variable "approval" {
  description = "Private evidence references and operator attestations; not a replacement for action-time approval."
  type        = object({ free_entitlement_verified = bool, image_boot_verified = bool, network_access_approved = bool, monthly_cost_usd = number, evidence_reference = string })
  default     = { free_entitlement_verified = false, image_boot_verified = false, network_access_approved = false, monthly_cost_usd = 0, evidence_reference = "" }
}
variable "nodes" {
  description = "Existing approved dedicated RG/NIC/image only. No private keys, passwords or cloud-init secrets."
  type        = map(object({ location = string, resource_group_name = string, size = string, source_image_id = string, network_interface_id = string, ssh_public_key = string, architecture = string, disk_gib = number, disk_type = string }))
  default     = {}
  validation {
    condition     = alltrue([for n in values(var.nodes) : contains(["x86_64", "aarch64"], n.architecture) && n.disk_gib > 0 && n.disk_gib <= 64])
    error_message = "Architecture must be x86_64/aarch64 and disk size 1..64 GiB; actual free entitlement still needs verification."
  }
}
