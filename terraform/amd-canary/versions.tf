terraform {
  required_version = "= 1.14.0"
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "= 4.51.0" }
  }
  backend "azurerm" {
    use_oidc         = true
    use_azuread_auth = true
  }
}
provider "azurerm" {
  subscription_id = var.subscription_id
  features {}
  resource_provider_registrations = "none"
}
