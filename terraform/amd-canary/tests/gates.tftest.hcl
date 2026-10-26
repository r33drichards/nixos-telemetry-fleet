mock_provider "azurerm" {}
variables {
  subscription_id     = "00000000-0000-0000-0000-000000000000"
  resource_group_name = "example"
  image_version_id    = "example"
  ssh_public_key      = "unconfigured"
}
run "default_creates_nothing" {
  command = plan
  assert {
    condition     = output.node_count == 0
    error_message = "Default must create no VM."
  }
}
run "enable_without_approvals_fails" {
  command = plan
  variables { enabled = true }
  expect_failures = [terraform_data.approval]
}
