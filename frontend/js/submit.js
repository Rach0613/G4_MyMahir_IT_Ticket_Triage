
import { api, esc, formatDate } from "./api.js?v=20260823-2";

const form = document.getElementById("ticket-form");
const submitBtn = document.getElementById("submit-btn");
const resetBtn = document.getElementById("reset-btn");
const banner = document.getElementById("banner");
const result = document.getElementById("result");

const description = document.getElementById("description");
const characterCount = document.querySelector(".character-count");


/* =========================================================
   Character Counter
   ========================================================= */

if (description && characterCount) {
  description.addEventListener("input", () => {
    const length = description.value.length;

    characterCount.textContent =
      `${length.toLocaleString()} / 4,000 characters`;
  });
}


/* =========================================================
   Form Validation
   ========================================================= */

function clearFieldErrors() {
  document.querySelectorAll(".field").forEach((field) => {
    field.classList.remove("invalid");

    const error = field.querySelector(".err");

    if (error) {
      error.textContent = "";
    }
  });
}


function showFieldErrors(fields) {
  Object.entries(fields || {}).forEach(([name, message]) => {
    const wrapper = document.querySelector(
      `.field[data-field="${name}"]`
    );

    if (!wrapper) {
      return;
    }

    wrapper.classList.add("invalid");

    const error = wrapper.querySelector(".err");

    if (error) {
      error.textContent = message;
    }
  });
}


/* =========================================================
   Banner
   ========================================================= */

function setBanner(kind, message) {
  if (!banner) {
    return;
  }

  if (!message) {
    banner.innerHTML = "";
    return;
  }

  banner.innerHTML = `
    <div class="notice ${esc(kind)}">
      ${esc(message)}
    </div>
  `;
}


/* =========================================================
   Load Categories
   ========================================================= */

async function loadCategories() {
  try {
    const data = await api.categories();

    const select = document.getElementById("category");

    if (!select) {
      return;
    }

    const existingValues = new Set(
      [...select.options].map(
        (option) => option.value
      )
    );

    (data.categories || []).forEach((category) => {
      if (existingValues.has(category)) {
        return;
      }

      const option = document.createElement("option");

      option.value = category;
      option.textContent = category;

      select.appendChild(option);
    });

  } catch (error) {
    console.error(
      "Category loading failed:",
      error
    );

    setBanner(
      "warn",
      "The category list could not be loaded. You can still submit your ticket."
    );
  }
}


/* =========================================================
   Classification Method Label
   ========================================================= */

function methodLabel(method) {
  const labels = {
    "azure-ai-language-custom":
      "Azure AI Language · Custom trained model",

    "azure-ai-language-keyphrase":
      "Azure AI Language · Key phrase extraction",

    "keyword-rules":
      "Keyword rules · Offline fallback"
  };

  return (
    labels[method] ||
    method ||
    "Automatic classification"
  );
}


/* =========================================================
   Confidence Formatting
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
   Render Submitted Ticket
   ========================================================= */

function renderResult(ticket) {
  if (!result) {
    return;
  }

  const auto =
    ticket.categorySource === "auto";

  const evidence =
    (ticket.classificationEvidence || [])
      .map(esc)
      .join(", ");

  const categorySource =
    auto
      ? "Suggested automatically by AI"
      : "Selected manually";

  result.innerHTML = `
    <div class="result">

      <h2>
        🎉 Ticket submitted successfully
      </h2>

      <p class="muted">
        Your support request has been received.
        Keep the reference number below for future follow-up.
      </p>

      <dl>

        <dt>Reference</dt>

        <dd class="mono">
          ${esc(ticket.id)}
        </dd>


        <dt>Title</dt>

        <dd>
          ${esc(ticket.title)}
        </dd>


        <dt>Category</dt>

        <dd>

          <span class="pill cat">
            ${esc(ticket.category)}
          </span>

          <span class="muted">
            · ${esc(categorySource)}
          </span>

        </dd>


        <dt>Status</dt>

        <dd>

          <span class="pill new">
            ${esc(ticket.status)}
          </span>

        </dd>


        <dt>Priority</dt>

        <dd>
          ${esc(ticket.priority)}
        </dd>


        <dt>Submitted</dt>

        <dd>
          ${esc(formatDate(ticket.createdAt))}
        </dd>


        <dt>Classified by</dt>

        <dd>

          ${esc(
            methodLabel(
              ticket.classificationMethod
            )
          )}

          <span class="muted">
            · Confidence
            ${esc(
              formatConfidence(
                ticket.classificationConfidence
              )
            )}
          </span>

        </dd>


        ${
          evidence
            ? `
              <dt>AI signals</dt>

              <dd class="muted">
                ${evidence}
              </dd>
            `
            : ""
        }

      </dl>

    </div>
  `;

  result.scrollIntoView({
    behavior: "smooth",
    block: "center"
  });
}


/* =========================================================
   Collect Form Data
   ========================================================= */

function getFormPayload() {
  return {
    name: document
      .getElementById("name")
      .value
      .trim(),

    email: document
      .getElementById("email")
      .value
      .trim(),

    title: document
      .getElementById("title")
      .value
      .trim(),

    description: document
      .getElementById("description")
      .value
      .trim(),

    priority: document
      .getElementById("priority")
      .value,

    category: document
      .getElementById("category")
      .value
  };
}


/* =========================================================
   Submit Ticket
   ========================================================= */

if (form) {
  form.addEventListener(
    "submit",
    async (event) => {
      event.preventDefault();

      clearFieldErrors();

      setBanner("", "");

      if (result) {
        result.innerHTML = "";
      }

      const payload = getFormPayload();

      submitBtn.disabled = true;

      submitBtn.innerHTML = `
        <span>Analysing ticket...</span>
        <span>⏳</span>
      `;

      try {

        /*
         * Send ticket to the API.
         */

        const ticket =
          await api.createTicket(payload);


        /*
         * Display successful result.
         */

        renderResult(ticket);


        /*
         * Reset form.
         */

        form.reset();


        /*
         * Reset character counter.
         */

        if (characterCount) {
          characterCount.textContent =
            "0 / 4,000 characters";
        }


        setBanner(
          "ok",
          "Your ticket was submitted successfully."
        );

      } catch (error) {

        console.error(
          "Ticket submission failed:",
          error
        );


        showFieldErrors(
          error.fields
        );


        setBanner(
          "bad",
          error.message ||
            "We could not submit your ticket. Please try again."
        );

      } finally {

        submitBtn.disabled = false;

        submitBtn.innerHTML = `
          <span>Submit ticket</span>
          <span class="button-arrow">→</span>
        `;
      }
    }
  );
}


/* =========================================================
   Clear Form
   ========================================================= */

if (resetBtn) {
  resetBtn.addEventListener(
    "click",
    () => {

      form.reset();

      clearFieldErrors();

      setBanner("", "");

      if (result) {
        result.innerHTML = "";
      }

      if (characterCount) {
        characterCount.textContent =
          "0 / 4,000 characters";
      }
    }
  );
}


/* =========================================================
   Initialisation
   ========================================================= */

(async function init() {
  await loadCategories();
})();

