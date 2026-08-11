const { SecretClient } = require('@azure/keyvault-secrets');
const { DefaultAzureCredential } = require('@azure/identity');
const { CosmosClient } = require('@azure/cosmos');

require('dotenv').config();

async function initializeCosmosContainer() {
    const keyVaultUrl = process.env.KEY_VAULT_URL;
    
    if (!keyVaultUrl) {
        throw new Error("KEY_VAULT_URL is not defined in the environment variables.");
    }

    // Authenticate using Azure Identity (uses 'az login' locally, or Managed Identity in production)
    const credential = new DefaultAzureCredential();
    const secretClient = new SecretClient(keyVaultUrl, credential);

    // Fetch secrets securely from Azure Key Vault
    console.log("Fetching credentials from Azure Key Vault...");
    const endpointSecret = await secretClient.getSecret("CosmosEndpoint");
    const keySecret = await secretClient.getSecret("CosmosKey");

    const endpoint = endpointSecret.value;
    const key = keySecret.value;
    const databaseId = process.env.COSMOS_DATABASE;
    const containerId = process.env.COSMOS_CONTAINER;

    // Initialize Cosmos DB client with fetched secrets
    const client = new CosmosClient({ endpoint, key });
    return client.database(databaseId).container(containerId);
}


module.exports = initializeCosmosContainer();
