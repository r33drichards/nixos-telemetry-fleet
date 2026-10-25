mock_provider "azurerm" {}
run "unapproved_enable_rejected" {
  command = plan
  variables { enabled = true }
  expect_failures = [terraform_data.approval]
}
