from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.cosmos import CosmosClient

from shared.config import (
    KEY_VAULT_URL,
    COSMOS_ENDPOINT,
    COSMOS_KEY,
    COSMOS_DATABASE,
    COSMOS_CONTAINER
)

_container = None


def _get_container():
    """Create the Cosmos client on first database use, not during API startup."""
    global _container
    if _container is not None:
        return _container

    if not COSMOS_DATABASE or not COSMOS_CONTAINER:
        raise RuntimeError(
            "COSMOS_DATABASE and COSMOS_CONTAINER must be configured."
        )

    endpoint = COSMOS_ENDPOINT
    key = COSMOS_KEY

    # Direct environment settings are the reliable option for an integrated
    # Static Web Apps API. Keep Key Vault as the secure fallback for local
    # development or a standalone Function App with managed identity.
    if not endpoint or not key:
        if not KEY_VAULT_URL:
            raise RuntimeError(
                "Configure COSMOS_ENDPOINT and COSMOS_KEY, or KEY_VAULT_URL."
            )
        credential = DefaultAzureCredential()
        secret_client = SecretClient(
            vault_url=KEY_VAULT_URL,
            credential=credential
        )
        endpoint = secret_client.get_secret("CosmosEndpoint").value
        key = secret_client.get_secret("CosmosKey").value

    cosmos_client = CosmosClient(endpoint, credential=key)
    database = cosmos_client.get_database_client(COSMOS_DATABASE)
    _container = database.get_container_client(COSMOS_CONTAINER)
    return _container


# ==========================================================
# CREATE Ticket
# ==========================================================

def create_ticket(ticket):

    # Store the ticket document inside Cosmos DB.
    return _get_container().create_item(
        body=ticket
    )
    
# ==========================================================
# GET All Tickets
# ==========================================================

def get_all_tickets():

    # Query all ticket documents from Cosmos DB
    items = _get_container().query_items(
        query="SELECT * FROM c",
        enable_cross_partition_query=True
    )

    # Convert Cosmos query result into a Python list
    return list(items)

# ==========================================================
# GET Ticket By ID
# ==========================================================

def get_ticket_by_id(ticket_id):

    # Search ticket by ID across all partitions.
    # This is needed because Cosmos DB partition key is /category.
    query = """
        SELECT * FROM c
        WHERE c.id = @ticket_id
    """

    parameters = [
        {
            "name": "@ticket_id",
            "value": ticket_id
        }
    ]

    items = list(
        _get_container().query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        )
    )

    # Return first matching ticket
    if items:
        return items[0]

    # Return None if ticket does not exist
    return None

# ==========================================================
# UPDATE Ticket
# ==========================================================

def update_ticket(ticket_id, new_status=None, new_category=None):

    # Find existing ticket first
    ticket = get_ticket_by_id(ticket_id)

    if ticket is None:
        return None

    # original category because /category
    # is the Cosmos DB partition key.
    old_category = ticket["category"]

    # Update status if provided
    if new_status:
        ticket["status"] = new_status

    # If category is NOT changing, we can replace normally.
    if not new_category or new_category == old_category:

        return _get_container().replace_item(
            item=ticket_id,
            body=ticket
        )

    # ------------------------------------------------------
    # Category is changing
    # ------------------------------------------------------
    # /category is the partition key, so Cosmos DB cannot
    # simply change it using replace_item().
    # ------------------------------------------------------

    container = _get_container()
    container.delete_item(
        item=ticket_id,
        partition_key=old_category
    )

    ticket["category"] = new_category
    ticket["categorySource"] = "manual"

    # Remove Cosmos-generated system properties before
    # creating the document again.
    for field in [
        "_rid",
        "_self",
        "_etag",
        "_attachments",
        "_ts"
    ]:
        ticket.pop(field, None)

    return container.create_item(
        body=ticket
    )
