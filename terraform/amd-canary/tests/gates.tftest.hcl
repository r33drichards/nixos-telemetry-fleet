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
run "only_ipv6_ssh_is_allowed" {
  command = plan
  plan_options { target = [azurerm_network_security_group.closed] }
  variables {
    enabled = true
    approval = {
      standard_unsigned_gen2 = true
      public_ipv6_ssh        = true
      free_compute_and_p6    = true
      quota_capacity_checked = true
      state_and_roles        = true
      image_region_ready     = true
      monthly_ancillary_usd  = 1
      evidence               = "synthetic test fixture, not live approval"
    }
  }
  assert {
    condition = length(azurerm_network_security_group.closed[0].security_rule) == 2 && alltrue([
      for rule in azurerm_network_security_group.closed[0].security_rule :
      rule.access == "Allow" ? (rule.direction == "Inbound" && rule.protocol == "Tcp" && rule.destination_port_range == "22" && rule.source_address_prefix == "::/0" && rule.priority == 1000) : (rule.access == "Deny" && rule.direction == "Inbound" && rule.protocol == "*" && rule.destination_port_range == "*" && rule.source_address_prefix == "*" && rule.priority == 4096)
    ])
    error_message = "Permit only IPv6 TCP22 and explicitly deny all other inbound traffic."
  }
}
