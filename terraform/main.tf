module "hosts" {
  source   = "./modules/azure-hosts"
  enabled  = var.enabled
  approval = var.approval
  nodes    = var.nodes
}
output "node_count" { value = module.hosts.node_count }
