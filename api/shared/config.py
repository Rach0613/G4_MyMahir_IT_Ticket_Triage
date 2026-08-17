import os

# ==========================================================
# Azure Key Vault Configuration
# ==========================================================

# URL of the Azure Key Vault used by the team
KEY_VAULT_URL = os.getenv("KEY_VAULT_URL")


# ==========================================================
# Azure Cosmos DB Configuration
# ==========================================================

# Cosmos DB database name
COSMOS_DATABASE = os.getenv("COSMOS_DATABASE")

# Cosmos DB container name
COSMOS_CONTAINER = os.getenv("COSMOS_CONTAINER")