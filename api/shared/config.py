import os
from dataclasses import dataclass

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


# ==========================================================
# Azure AI Language Configuration
# ==========================================================

def _clean(name):
    return (os.getenv(name) or "").strip()


def _float_setting(name, default, minimum, maximum):
    """Read a bounded float without allowing bad configuration to break startup."""
    try:
        value = float(_clean(name) or default)
    except (TypeError, ValueError):
        value = float(default)
    return max(minimum, min(maximum, value))


@dataclass(frozen=True)
class AzureLanguageSettings:
    endpoint: str
    key: str
    api_version: str
    timeout_seconds: float

    @property
    def configured(self) -> bool:
        """Key phrase extraction needs only a Language endpoint and key."""
        return bool(self.endpoint and self.key)


def get_azure_language_settings() -> AzureLanguageSettings:
    """Read settings at call time so tests and local tooling can override them safely."""
    return AzureLanguageSettings(
        endpoint=_clean("AZURE_LANGUAGE_ENDPOINT").rstrip("/"),
        key=_clean("AZURE_LANGUAGE_KEY"),
        api_version=_clean("AZURE_LANGUAGE_API_VERSION") or "2024-11-01",
        timeout_seconds=_float_setting(
            "AZURE_LANGUAGE_TIMEOUT_SECONDS", "6", 0.1, 30.0
        ),
    )
