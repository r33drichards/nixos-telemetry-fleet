mock_provider "azurerm" {}
run "default_has_no_hosts" {
  command = plan
  assert {
    condition     = output.node_count == 0
    error_message = "Default must create zero hosts."
  }
}
run "invalid_disk_rejected" {
  command = plan
  variables {
    nodes = { example = { location = "example", resource_group_name = "example", size = "example", source_image_id = "example", network_interface_id = "example", ssh_public_key = "example", architecture = "x86_64", disk_gib = 65, disk_type = "Standard_LRS" } }
  }
  expect_failures = [var.nodes]
}
