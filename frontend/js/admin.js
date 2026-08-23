import {
  api,
  esc,
  formatDate,
  setAdminKey,
  statusClass
} from "./api.js?v=20260823-2";

/* =========================================================
   DOM Elements
========================================================= */

const els = {
  banner: document.getElementById("banner"),
  stats: document.getElementById("stats"),
  rows: document.getElementById("rows"),

  category: document.getElementById("f-category"),
  status: document.getElementById("f-status"),
  email: document.getElementById("f-email"),
  q: document.getElementById("f-q"),

  apply: document.getElementById("apply"),
  clear: document.getElementById("clear"),
  refresh: document.getElementById("refresh"),

  adminKey: document.getElementById("admin-key"),
  ticketCount: document.getElementById("ticket-count")
};

/* =========================================================
   Reference Data
========================================================= */

let reference = {
  categories: [],
  statuses: [],
  priorities: []
};

/* =========================================================
   Banner
========================================================= */

function setBanner(kind, message) {
  if (!message) {
    els.banner.innerHTML = "";
    return;
  }

  els.banner.innerHTML = `
    <div class="notice ${esc(kind)}">
      ${esc(message)}
    </div>
  `;
}

/* =========================================================
   Classification Method
========================================================= */

function methodShort(method) {
  const methods = {
    "azure-ai-language-custom": "AI Custom Model",
    "azure-ai-language-keyphrase": "AI Key Phrases",
    "keyword-rules": "Keyword Rules"
  };

  return methods[method] || method || "Unknown";
}

/* =========================================================
   Confidence
========================================================= */

function formatConfidence(value) {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return "N/A";
  }

  const number = Number(value);

  if (Number.isNaN(number)) {
    return String(value);
  }

  if (number <= 1) {
    return `${Math.round(number * 100)}%`;
  }

  return `${Math.round(number)}%`;
}

/* =========================================================
   Load Reference Lists
========================================================= */

async function loadReference() {
  reference = await api.categories();

  /* Populate categories */

  reference.categories.forEach((category) => {
    els.category.add(
      new Option(category, category)
    );
  });

  /* Populate statuses */

  reference.statuses.forEach((status) => {
    els.status.add(
      new Option(status, status)
    );
  });
}

/* =========================================================
   Load Health / Dashboard Statistics
========================================================= */

async function loadHealth() {
  try {
    const health = await api.health();

    const total =
      health.stats?.total ?? 0;

    const storage =
      health.storage || "Unknown";

    const classifier =
      methodShort(
        health.classifierChain?.[0]
      );

    els.stats.innerHTML = `
      <div class="stat">
        <div class="n">
          ${esc(total)}
        </div>

        <div class="k">
          Total Tickets
        </div>
      </div>

      <div class="stat">
        <div class="n">
          ${esc(storage)}
        </div>

        <div class="k">
          Storage
        </div>
      </div>

      <div class="stat">
        <div class="n">
          ${esc(classifier)}
        </div>

        <div class="k">
          AI Classifier
        </div>
      </div>
    `;

    /* Configuration warnings */

    const warnings =
      (health.warnings || [])
        .map(
          (warning) =>
            `<li>${esc(warning)}</li>`
        )
        .join("");

    if (warnings) {
      els.banner.innerHTML = `
        <div class="notice warn">

          <strong>
            Configuration notes
          </strong>

          <ul
            style="
              margin:6px 0 0 18px;
            "
          >
            ${warnings}
          </ul>

        </div>
      `;
    }
  } catch (error) {
    console.error(
      "Health check failed:",
      error
    );

    els.stats.innerHTML = `
      <div class="stat">
        <div class="n">—</div>
        <div class="k">Total Tickets</div>
      </div>

      <div class="stat">
        <div class="n">Unavailable</div>
        <div class="k">Storage</div>
      </div>

      <div class="stat">
        <div class="n">Unavailable</div>
        <div class="k">AI Classifier</div>
      </div>
    `;
  }
}

/* =========================================================
   Status Options
========================================================= */

function statusOptions(ticket) {
  return reference.statuses
    .map((status) => {
      const selected =
        status === ticket.status
          ? " selected"
          : "";

      return `
        <option
          value="${esc(status)}"
          ${selected}
        >
          ${esc(status)}
        </option>
      `;
    })
    .join("");
}

/* =========================================================
   Category Options
========================================================= */

function categoryOptions(ticket) {
  return reference.categories
    .map((category) => {
      const selected =
        category === ticket.category
          ? " selected"
          : "";

      return `
        <option
          value="${esc(category)}"
          ${selected}
        >
          ${esc(category)}
        </option>
      `;
    })
    .join("");
}

/* =========================================================
   Action Cell
========================================================= */

function actionCell(ticket) {
  return `
    <div
      style="
        display:flex;
        flex-direction:column;
        gap:7px;
      "
    >

      <select
        class="js-status"
        data-id="${esc(ticket.id)}"
      >
        ${statusOptions(ticket)}
      </select>

      <select
        class="js-category"
        data-id="${esc(ticket.id)}"
      >
        ${categoryOptions(ticket)}
      </select>

      <button
        class="sm js-save"
        data-id="${esc(ticket.id)}"
        type="button"
      >
        Save changes
      </button>

    </div>
  `;
}

/* =========================================================
   Ticket Detail
========================================================= */

function detailCell(ticket) {
  const evidence =
    (ticket.classificationEvidence || [])
      .map(esc)
      .join(", ");

  const history =
    (ticket.statusHistory || [])
      .map((historyItem) => {
        return `
          <li>

            <strong>
              ${esc(historyItem.status)}
            </strong>

            · ${esc(
              formatDate(historyItem.at)
            )}

            · ${esc(historyItem.by)}

            ${
              historyItem.note
                ? ` · ${esc(historyItem.note)}`
                : ""
            }

          </li>
        `;
      })
      .join("");

  return `
    <details class="row-detail">

      <summary>
        View ticket details
      </summary>

      <div class="body">

        <!-- Description -->

        <div
          style="
            background:#fafaff;
            padding:12px;
            border-radius:9px;
            margin-bottom:10px;
          "
        >

          <strong
            style="
              font-size:.78rem;
            "
          >
            Description
          </strong>

          <p
            style="
              margin:5px 0 0;
              font-size:.84rem;
            "
          >
            ${esc(ticket.description || "No description")}
          </p>

        </div>

        <!-- AI Classification -->

        <div
          style="
            background:#f4f1ff;
            border:1px solid #e2dcff;
            padding:12px;
            border-radius:9px;
            margin-bottom:10px;
          "
        >

          <strong
            style="
              color:#5141b7;
              font-size:.78rem;
            "
          >
            ✨ AI Classification
          </strong>

          <p
            style="
              margin:5px 0 0;
              font-size:.82rem;
            "
          >
            Suggested category:

            <strong>
              ${esc(
                ticket.suggestedCategory ||
                ticket.category ||
                "N/A"
              )}
            </strong>
          </p>

          <p
            style="
              margin:3px 0 0;
              font-size:.82rem;
            "
          >
            Classified by:

            ${esc(
              methodShort(
                ticket.classificationMethod
              )
            )}
          </p>

          <p
            style="
              margin:3px 0 0;
              font-size:.82rem;
            "
          >
            Confidence:

            <strong>
              ${esc(
                formatConfidence(
                  ticket.classificationConfidence
                )
              )}
            </strong>
          </p>

          ${
            evidence
              ? `
                <p
                  style="
                    margin:3px 0 0;
                    font-size:.82rem;
                  "
                >
                  Signals:
                  ${evidence}
                </p>
              `
              : ""
          }

        </div>

        <!-- Status History -->

        ${
          history
            ? `
              <div>

                <strong
                  style="
                    font-size:.78rem;
                  "
                >
                  Status history
                </strong>

                <ul
                  class="muted"
                  style="
                    margin:7px 0 0 18px;
                    padding:0;
                  "
                >
                  ${history}
                </ul>

              </div>
            `
            : ""
        }

        <!-- Ticket ID -->

        <p
          class="mono muted"
          style="
            margin:10px 0 0;
          "
        >
          Ticket ID:
          ${esc(ticket.id)}
        </p>

      </div>

    </details>
  `;
}

/* =========================================================
   Render Ticket Rows
========================================================= */

function renderRows(items) {
  /* Update ticket count */

  if (els.ticketCount) {
    els.ticketCount.textContent =
      `${items.length} ticket${
        items.length === 1
          ? ""
          : "s"
      }`;
  }

  /* Empty state */

  if (!items.length) {
    els.rows.innerHTML = `
      <tr>

        <td
          colspan="7"
          style="
            padding:45px;
            text-align:center;
          "
        >

          <div
            style="
              font-size:2rem;
              margin-bottom:8px;
            "
          >
            🎫
          </div>

          <strong>
            No tickets found
          </strong>

          <p
            class="muted"
            style="
              margin:5px 0 0;
            "
          >
            Try changing your filters.
          </p>

        </td>

      </tr>
    `;

    return;
  }

  /* Render tickets */

  els.rows.innerHTML = items
    .map((ticket) => {
      return `
        <tr>

          <!-- Submitted -->

          <td
            class="muted"
            style="
              white-space:nowrap;
            "
          >
            ${esc(
              formatDate(
                ticket.createdAt
              )
            )}
          </td>

          <!-- Requester -->

          <td>

            <strong>
              ${esc(ticket.name)}
            </strong>

            <div class="muted">
              ${esc(ticket.email)}
            </div>

          </td>

          <!-- Ticket -->

          <td>

            <strong>
              ${esc(ticket.title)}
            </strong>

            ${detailCell(ticket)}

          </td>

          <!-- Category -->

          <td>

            <span class="pill cat">
              ${esc(
                ticket.category ||
                ticket.suggestedCategory ||
                "General Enquiry"
              )}
            </span>

          </td>

          <!-- Priority -->

          <td>

            <span
              class="pill ${esc(
                String(
                  ticket.priority || "Medium"
                ).toLowerCase()
              )}"
            >
              ${esc(
                ticket.priority || "Medium"
              )}
            </span>

          </td>

          <!-- Status -->

          <td>

            <span
              class="pill ${esc(
                statusClass(
                  ticket.status || "New"
                )
              )}"
            >
              ${esc(
                ticket.status || "New"
              )}
            </span>

          </td>

          <!-- Actions -->

          <td>
            ${actionCell(ticket)}
          </td>

        </tr>
      `;
    })
    .join("");

  /* Save buttons */

  els.rows
    .querySelectorAll(".js-save")
    .forEach((button) => {
      button.addEventListener(
        "click",
        () =>
          saveTicket(
            button.dataset.id,
            button
          )
      );
    });
}

/* =========================================================
   Save Ticket
========================================================= */

async function saveTicket(id, button) {
  const statusSelect =
    els.rows.querySelector(
      `.js-status[data-id="${CSS.escape(id)}"]`
    );

  const categorySelect =
    els.rows.querySelector(
      `.js-category[data-id="${CSS.escape(id)}"]`
    );

  if (
    !statusSelect ||
    !categorySelect
  ) {
    return;
  }

  const status =
    statusSelect.value;

  const category =
    categorySelect.value;

  button.disabled = true;
  button.textContent = "Saving...";

  try {
    /* Store admin key for this browser */

    setAdminKey(
      els.adminKey.value.trim()
    );

    /* Send update to Azure API */

    await api.updateTicket(
      id,
      {
        status,
        category
      }
    );

    setBanner(
      "ok",
      "Ticket updated successfully."
    );

    /* Reload table and statistics */

    await Promise.all([
      load(),
      loadHealth()
    ]);

  } catch (error) {
    console.error(
      "Ticket update failed:",
      error
    );

    setBanner(
      "bad",
      error.message ||
        "Could not update the ticket."
    );

    button.disabled = false;
    button.textContent =
      "Save changes";
  }
}

/* =========================================================
   Load Tickets
========================================================= */

async function load() {
  els.rows.innerHTML = `
    <tr>

      <td
        colspan="7"
        class="muted"
        style="
          padding:30px;
          text-align:center;
        "
      >
        Loading tickets...
      </td>

    </tr>
  `;

  try {
    const data =
      await api.listTickets({
        category:
          els.category.value,

        status:
          els.status.value,

        email:
          els.email.value.trim(),

        q:
          els.q.value.trim()
      });

    renderRows(
      data.items || []
    );

  } catch (error) {
    console.error(
      "Ticket loading failed:",
      error
    );

    els.rows.innerHTML = `
      <tr>

        <td
          colspan="7"
          style="padding:25px;"
        >

          <div class="notice bad">
            ${esc(
              error.message ||
                "Could not load tickets."
            )}
          </div>

        </td>

      </tr>
    `;

    if (els.ticketCount) {
      els.ticketCount.textContent =
        "Unavailable";
    }
  }
}

/* =========================================================
   Apply Filters
========================================================= */

els.apply.addEventListener(
  "click",
  () => {
    load();
  }
);

/* =========================================================
   Refresh
========================================================= */

els.refresh.addEventListener(
  "click",
  async () => {
    setBanner(
      "info",
      "Refreshing ticket data..."
    );

    try {
      await Promise.all([
        load(),
        loadHealth()
      ]);

      setBanner(
        "ok",
        "Dashboard refreshed."
      );

    } catch (error) {
      console.error(
        "Dashboard refresh failed:",
        error
      );

      setBanner(
        "bad",
        "Could not refresh the dashboard."
      );
    }
  }
);

/* =========================================================
   Clear Filters
========================================================= */

els.clear.addEventListener(
  "click",
  () => {
    els.category.value = "";
    els.status.value = "";
    els.email.value = "";
    els.q.value = "";

    load();
  }
);

/* =========================================================
   Enter Key Search
========================================================= */

[
  els.email,
  els.q
].forEach((input) => {
  input.addEventListener(
    "keydown",
    (event) => {
      if (event.key === "Enter") {
        load();
      }
    }
  );
});

/* =========================================================
   Admin Key
========================================================= */

els.adminKey.addEventListener(
  "change",
  () => {
    setAdminKey(
      els.adminKey.value.trim()
    );
  }
);

/* =========================================================
   Initialisation
========================================================= */

(async function init() {
  try {
    await loadReference();
  } catch (error) {
    console.error(
      "Reference loading failed:",
      error
    );

    setBanner(
      "warn",
      "Could not load category and status lists."
    );
  }

  await Promise.all([
    load(),
    loadHealth()
  ]);
})();
