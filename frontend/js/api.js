

const API_BASE = "/api";


let adminKey = "";



export function setAdminKey(value) {
  adminKey = (value || "").trim();
}

export function getAdminKey() {
  return adminKey;
}



async function request(path, options = {}) {

  /*
    Default headers.
  */

  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {})
  };


  /*
    Add admin key when available.
  */

  if (adminKey) {
    headers["x-admin-key"] = adminKey;
  }


  let response;


  /*
    Send request.
  */

  try {

    response = await fetch(
      `${API_BASE}${path}`,
      {
        ...options,
        headers
      }
    );

  } catch (networkError) {

    console.error(
      "Network error:",
      networkError
    );

    throw new Error(
      "Cannot reach the API. Please check that the Azure backend is running."
    );
  }


  /*
    Read response body.
  */

  const text = await response.text();

  let body = null;


  /*
    Try to parse JSON.
  */

  if (text) {

    try {

      body = JSON.parse(text);

    } catch {

      body = {
        error: text
      };

    }

  }


  /*
    Handle HTTP errors.
  */

  if (!response.ok) {

    const message =
      (
        body &&
        body.error
      ) ||
      `Request failed (${response.status})`;


    const error = new Error(message);

    error.status = response.status;

    error.fields =
      (
        body &&
        body.fields
      ) || {};


    throw error;
  }


  /*
    Return parsed response.
  */

  return body;
}


/* =========================================================
   API Endpoints
========================================================= */

export const api = {

  /* -------------------------------------------------------
     Health Check
  ------------------------------------------------------- */

  health: () =>
    request("/health"),


  /* -------------------------------------------------------
     Categories / Reference Data
  ------------------------------------------------------- */

  categories: () =>
    request("/categories"),


  /* -------------------------------------------------------
     Create Ticket
  ------------------------------------------------------- */

  createTicket: (payload) =>
    request(
      "/tickets",
      {
        method: "POST",

        body: JSON.stringify(
          payload
        )
      }
    ),


  /* -------------------------------------------------------
     List Tickets
  ------------------------------------------------------- */

  listTickets: (filters = {}) => {

    const query =
      new URLSearchParams();


    /*
      Only include filters that
      actually have values.
    */

    Object.entries(filters).forEach(
      ([key, value]) => {

        if (
          value !== undefined &&
          value !== null &&
          String(value).trim() !== ""
        ) {

          query.append(
            key,
            String(value)
          );

        }

      }
    );


    const queryString =
      query.toString();


    const suffix =
      queryString
        ? `?${queryString}`
        : "";


    return request(
      `/tickets${suffix}`
    );
  },


  /* -------------------------------------------------------
     Get Individual Ticket
  ------------------------------------------------------- */

  getTicket: (id) =>
    request(
      `/tickets/${encodeURIComponent(id)}`
    ),


  /* -------------------------------------------------------
     Update Ticket
  ------------------------------------------------------- */

  updateTicket: (id, payload) =>
    request(
      `/tickets/${encodeURIComponent(id)}`,
      {
        method: "PATCH",

        body: JSON.stringify(
          payload
        )
      }
    )

};


/* =========================================================
   Shared UI Helpers
========================================================= */


/*
  Converts ticket status into
  a CSS class.
*/

export function statusClass(status) {

  const classes = {

    "New":
      "new",

    "Categorised":
      "categorised",

    "In Progress":
      "progress",

    "Resolved":
      "resolved"

  };


  return (
    classes[status] ||
    "cat"
  );
}


/* =========================================================
   Date Formatting
========================================================= */

/*
  Formats ISO timestamps into
  a readable local date/time.
*/

export function formatDate(iso) {

  if (!iso) {
    return "";
  }


  const date =
    new Date(iso);


  if (
    Number.isNaN(
      date.getTime()
    )
  ) {

    return iso;
  }


  return date.toLocaleString(
    undefined,
    {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    }
  );
}


/* =========================================================
   HTML Escape
========================================================= */

/*
  Escape values before inserting
  them into innerHTML.

  This prevents user-submitted
  ticket content from being
  interpreted as HTML.
*/

export function esc(value) {

  return String(
    value ?? ""
  ).replace(
    /[&<>"']/g,
    (character) => {

      return {

        "&":
          "&amp;",

        "<":
          "&lt;",

        ">":
          "&gt;",

        '"':
          "&quot;",

        "'":
          "&#39;"

      }[character];

    }
  );
}