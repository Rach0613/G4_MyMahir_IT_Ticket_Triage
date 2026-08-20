import azure.functions as func
import json
import uuid

from datetime import datetime, timezone
from shared.classifier import classifier_chain, classify_ticket
from shared.repository import (
    create_ticket as save_ticket,
    get_all_tickets,
    get_ticket_by_id,
    update_ticket
)

# Create Azure Functions app
app = func.FunctionApp(
    http_auth_level=func.AuthLevel.ANONYMOUS
)

# ==========================================================
# GET /api/health
# Purpose: Check API status and return dashboard information
# ==========================================================

@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:

    try:
        # Retrieve tickets so we can calculate dashboard statistics
        tickets = get_all_tickets()

        return func.HttpResponse(
            json.dumps({
                "status": "ok",

                # Total number of tickets currently stored
                "stats": {
                    "total": len(tickets)
                },

                # Storage technology used by the backend
                "storage": "Cosmos DB",

                # Current ticket classification method
                "classifierChain": classifier_chain(),

                # No configuration warnings for now
                "warnings": []
            }),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:
        return func.HttpResponse(
            json.dumps({
                "status": "error",
                "error": str(e)
            }),
            status_code=500,
            mimetype="application/json"
        )
    
# ==========================================================
# GET /api/categories
# Purpose: Return ticket categories, statuses and priorities
# ==========================================================

@app.route(route="categories", methods=["GET"])
def categories(req: func.HttpRequest) -> func.HttpResponse:

    data = {
        "categories": [
            "IT Support",
            "Facilities",
            "Course Registration",
            "Student Finance",
            "Library Services",
            "General Enquiry"
        ],

        "statuses": [
            "New",
            "Categorised",
            "In Progress",
            "Resolved"
        ],

        "priorities": [
            "Low",
            "Medium",
            "High"
        ]
    }

    return func.HttpResponse(
        json.dumps(data),
        status_code=200,
        mimetype="application/json"
    )
    
# ==========================================================
# POST /api/tickets
# Purpose: Create a new support ticket
# ==========================================================

@app.route(route="tickets", methods=["POST"])
def create_ticket(req: func.HttpRequest) -> func.HttpResponse:

    try:
        # Read JSON sent by frontend
        body = req.get_json()

        name = body.get("name")
        email = body.get("email")
        title = body.get("title")
        description = body.get("description")
        priority = body.get("priority", "Medium")
        selected_category = body.get("category")

        # Validate required fields
        if not name or not email or not title or not description:
            return func.HttpResponse(
                json.dumps({
                    "error": "Please complete all required fields.",
                    "fields": {
                        "name": "Required" if not name else "",
                        "email": "Required" if not email else "",
                        "title": "Required" if not title else "",
                        "description": "Required" if not description else ""
                    }
                }),
                status_code=400,
                mimetype="application/json"
            )

        classification = classify_ticket(title, description)
        suggested_category = classification["category"]

        # If user manually selected a category, use it.
        # Otherwise use automatic classification.
        if selected_category:
            final_category = selected_category
            category_source = "manual"
        else:
            final_category = suggested_category
            category_source = "auto"

        ticket_id = f"TKT-{str(uuid.uuid4())[:8].upper()}"

        ticket = {
            "id": ticket_id,
            "ticketId": ticket_id,
            "name": name,
            "email": email,
            "title": title,
            "description": description,
            "priority": priority,
            "category": final_category,
            "suggestedCategory": suggested_category,
            "categorySource": category_source,
            "status": "New",
            "createdAt": datetime.now(timezone.utc).isoformat(),

            "classificationMethod": classification["method"],
            "classificationConfidence": classification["confidence"],
            "classificationEvidence": classification["evidence"]
        }
        # Save ticket into Cosmos DB
        save_ticket(ticket)

        return func.HttpResponse(
            json.dumps(ticket),
            status_code=201,
            mimetype="application/json"
        )

    except ValueError:
        return func.HttpResponse(
            json.dumps({
                "error": "Invalid JSON body."
            }),
            status_code=400,
            mimetype="application/json"
        )
        
# ==========================================================
# GET /api/tickets
# Purpose: Retrieve tickets with optional filters/search
# ==========================================================

@app.route(route="tickets", methods=["GET"])
def get_tickets(req: func.HttpRequest) -> func.HttpResponse:

    try:
        # Retrieve all tickets from Cosmos DB
        tickets = get_all_tickets()

        # Read optional query parameters
        category = req.params.get("category")
        status = req.params.get("status")
        email = req.params.get("email")
        q = req.params.get("q")

        filtered_tickets = tickets

        # Filter by category
        if category:
            filtered_tickets = [
                ticket for ticket in filtered_tickets
                if ticket.get("category", "").lower() == category.lower()
            ]

        # Filter by status
        if status:
            filtered_tickets = [
                ticket for ticket in filtered_tickets
                if ticket.get("status", "").lower() == status.lower()
            ]

        # Filter by email
        if email:
            filtered_tickets = [
                ticket for ticket in filtered_tickets
                if ticket.get("email", "").lower() == email.lower()
            ]

        # General search
        # Searches ticket ID, name, email, title and description
        if q:
            search = q.lower()

            filtered_tickets = [
                ticket for ticket in filtered_tickets
                if (
                    search in ticket.get("id", "").lower()
                    or search in ticket.get("name", "").lower()
                    or search in ticket.get("email", "").lower()
                    or search in ticket.get("title", "").lower()
                    or search in ticket.get("description", "").lower()
                )
            ]

        # Return format expected by admin.js
        return func.HttpResponse(
            json.dumps({
                "items": filtered_tickets
            }),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:
        return func.HttpResponse(
            json.dumps({
                "error": str(e)
            }),
            status_code=500,
            mimetype="application/json"
        )
        
# ==========================================================
# GET /api/tickets/{ticket_id}
# Purpose: Retrieve one specific ticket by ID
# ==========================================================

@app.route(route="tickets/{ticket_id}", methods=["GET"])
def get_single_ticket(req: func.HttpRequest) -> func.HttpResponse:

    try:
        # Get ticket ID from the URL
        ticket_id = req.route_params.get("ticket_id")

        # Search for the ticket in Cosmos DB
        ticket = get_ticket_by_id(ticket_id)

        # If ticket does not exist
        if ticket is None:
            return func.HttpResponse(
                json.dumps({
                    "error": "Ticket not found."
                }),
                status_code=404,
                mimetype="application/json"
            )

        # Return the ticket
        return func.HttpResponse(
            json.dumps(ticket),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:
        return func.HttpResponse(
            json.dumps({
                "error": str(e)
            }),
            status_code=500,
            mimetype="application/json"
        )
        
# ==========================================================
# PATCH /api/tickets/{ticket_id}
# Purpose: Update ticket status and/or category
# ==========================================================

@app.route(route="tickets/{ticket_id}", methods=["PATCH"])
def patch_ticket(req: func.HttpRequest) -> func.HttpResponse:

    try:
        # Get ticket ID from URL
        ticket_id = req.route_params.get("ticket_id")

        # Read JSON body
        body = req.get_json()

        new_status = body.get("status")
        new_category = body.get("category")

        # Allowed values
        allowed_statuses = [
            "New",
            "Categorised",
            "In Progress",
            "Resolved"
        ]

        allowed_categories = [
            "IT Support",
            "Facilities",
            "Course Registration",
            "Student Finance",
            "Library Services",
            "General Enquiry"
        ]

        # Validate status
        if new_status and new_status not in allowed_statuses:
            return func.HttpResponse(
                json.dumps({
                    "error": "Invalid status."
                }),
                status_code=400,
                mimetype="application/json"
            )

        # Validate category
        if new_category and new_category not in allowed_categories:
            return func.HttpResponse(
                json.dumps({
                    "error": "Invalid category."
                }),
                status_code=400,
                mimetype="application/json"
            )

        # Update ticket in Cosmos DB
        updated_ticket = update_ticket(
            ticket_id,
            new_status=new_status,
            new_category=new_category
        )

        # Ticket doesn't exist
        if updated_ticket is None:
            return func.HttpResponse(
                json.dumps({
                    "error": "Ticket not found."
                }),
                status_code=404,
                mimetype="application/json"
            )

        return func.HttpResponse(
            json.dumps(updated_ticket),
            status_code=200,
            mimetype="application/json"
        )

    except ValueError:
        return func.HttpResponse(
            json.dumps({
                "error": "Invalid JSON body."
            }),
            status_code=400,
            mimetype="application/json"
        )

    except Exception as e:
        return func.HttpResponse(
            json.dumps({
                "error": str(e)
            }),
            status_code=500,
            mimetype="application/json"
        )
