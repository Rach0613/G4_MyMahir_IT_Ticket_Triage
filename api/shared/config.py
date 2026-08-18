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
    project_name: str
    deployment_name: str
    api_version: str
    min_confidence: float
    timeout_seconds: float

    @property
    def configured(self) -> bool:
        """Custom classification needs all four service/model identifiers."""
        return bool(
            self.endpoint
            and self.key
            and self.project_name
            and self.deployment_name
        )


def get_azure_language_settings() -> AzureLanguageSettings:
    """Read settings at call time so tests and local tooling can override them safely."""
    return AzureLanguageSettings(
        endpoint=_clean("AZURE_LANGUAGE_ENDPOINT").rstrip("/"),
        key=_clean("AZURE_LANGUAGE_KEY"),
        project_name=_clean("AZURE_LANGUAGE_PROJECT_NAME"),
        deployment_name=_clean("AZURE_LANGUAGE_DEPLOYMENT_NAME"),
        api_version=_clean("AZURE_LANGUAGE_API_VERSION") or "2024-11-01",
        min_confidence=_float_setting(
            "AZURE_LANGUAGE_MIN_CONFIDENCE", "0.55", 0.0, 1.0
        ),
        timeout_seconds=_float_setting(
            "AZURE_LANGUAGE_TIMEOUT_SECONDS", "6", 0.1, 30.0
        ),
    )
