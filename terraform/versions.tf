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
  features {}
  resource_provider_registrations = "none"
}
