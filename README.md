# G4_MyMahir_IT_Ticket_Triage

A web-based IT helpdesk assistant developed as part of the Microsoft AI-200 Capstone Project under the MyMahir programme.

The system allows users to submit support tickets, automatically suggests a suitable ticket category, stores ticket information in Azure Cosmos DB, and provides an admin dashboard for reviewing, filtering, and updating ticket status.

## Features

- Submit support tickets through a web interface
- Automatic ticket category suggestion
- Store and retrieve tickets using Azure Cosmos DB
- Admin dashboard for ticket management
- Search and filter tickets by category, status, email, and keywords
- Update ticket status and category
- Secure retrieval of database credentials using Azure Key Vault
- REST API built using Python Azure Functions

## Technology Stack

### Frontend

- HTML
- CSS
- JavaScript
- Azure Static Web Apps

### Backend

- Python
- Azure Functions
- REST API

### Database

- Azure Cosmos DB

### Security

- Azure Key Vault
- Azure Identity

## Backend API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Check API status and dashboard information |
| GET | `/api/categories` | Retrieve available categories, statuses, and priorities |
| POST | `/api/tickets` | Create and store a new support ticket |
| GET | `/api/tickets` | Retrieve tickets |
| GET | `/api/tickets/{ticket_id}` | Retrieve a specific ticket |
| PATCH | `/api/tickets/{ticket_id}` | Update ticket status and/or category |

## Local Setup

### 1. Prerequisites

Make sure the following tools are installed:

- Python
- Azure Functions Core Tools
- Azure CLI
- Node.js 20
- Azure Static Web Apps CLI

### 2. Configure Local Settings

Inside the `api` folder, copy:

`local.settings.example.json`

and rename the copy to:

`local.settings.json`

Fill in the required configuration values.

> Do not commit `local.settings.json` to GitHub because it contains local configuration information.

### 3. Install Backend Dependencies

Open a terminal from the project directory and run:

```powershell
cd api
pip install -r requirements.txt
```

### 4. Sign In to Azure

Run:

```powershell
az login
```

Select the appropriate Azure subscription when prompted.

The Azure account must have permission to access the project's Azure Key Vault.

### 5. Run the Application

Return to the project root:

```powershell
cd ..
```

Then start the application:

```powershell
swa start . --api-location api
```

The application will be available locally at:

`http://localhost:4280`

The Azure Static Web Apps emulator will serve the frontend and connect `/api` requests to the local Azure Functions backend.

## Application Flow

```text
User submits a support ticket
        ↓
Frontend sends request to Backend API
        ↓
Ticket category is suggested
        ↓
Ticket is stored in Azure Cosmos DB
        ↓
Admin Dashboard retrieves tickets
        ↓
Admin reviews the ticket
        ↓
Admin updates status/category
        ↓
Updated ticket is saved to Azure Cosmos DB
```

## Azure Services

The project integrates with the following Azure services:

- **Azure Static Web Apps** — hosts and serves the web frontend
- **Azure Functions** — provides the serverless backend REST API
- **Azure Cosmos DB** — stores support ticket data
- **Azure Key Vault** — securely stores and provides database credentials

## Project

**Microsoft AI-200 Capstone Project**  
**MyMahir Programme**

The project demonstrates the development of a cloud-based ticket triage system using Microsoft Azure services, combining a web interface, serverless backend API, secure credential management, persistent cloud storage, and automated ticket categorisation.