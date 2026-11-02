// ComplaintIQ Frontend Controller

let currentPage = 1;
const pageSize = 15;
let currentTriageResponse = null;

// Presets data
const PRESETS = {
  debt: "I am writing to report persistent harassment from debt collectors at ABC Recovery. They keep calling my cell phone and place of work at 3:00 AM demanding payment on an alleged debt of $1,250 that was already paid off. My SSN is 123-45-6789 and my email is consumer@test.com. Please stop these illegal collection calls immediately.",
  fraud: "URGENT FRAUD ALERT: Over $7,500 in unauthorized wire transactions were drained from my account yesterday. I believe my online banking was hacked and my stolen identity was used to open secondary lines of credit. Immediate escalation to fraud investigation required.",
  lowconf: "I am writing regarding an ambiguous financial issue with my online balance. The calculation seemed uncertain and strange when I looked at it last week. Please have someone review this general account query.",
  mortgage: "The mortgage servicer miscalculated my escrow account and is now improperly threatening foreclosure and legal action on my family home. We made all payments on time and our court date or sale deadline is within 48 hours.",
  creditcard: "I have a disputed charge of $380 on my credit card statement from an unknown vendor. I called customer support three times and submitted receipts, but the billing error has not been reversed."
};

// Lifecycle init
document.addEventListener("DOMContentLoaded", () => {
  initHealthCheck();
  initInputListeners();
  fetchOverviewMetrics();

  // Check URL query param or hash for console view
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get("view") === "console" || window.location.hash === "#console") {
    switchView("console");
  }
});

// View switching
function switchView(viewName) {
  const landing = document.getElementById("view-landing");
  const consoleView = document.getElementById("view-console");
  const navOverview = document.getElementById("nav-overview-btn");

  if (viewName === "console") {
    landing.classList.add("hidden");
    consoleView.classList.remove("hidden");
    window.scrollTo({ top: 0, behavior: "smooth" });
    fetchConsoleData();
  } else {
    consoleView.classList.add("hidden");
    landing.classList.remove("hidden");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
}

function scrollToDemo() {
  switchView("landing");
  const el = document.getElementById("demo-section");
  if (el) el.scrollIntoView({ behavior: "smooth" });
}

function scrollToArchitecture() {
  switchView("landing");
  const el = document.getElementById("architecture-section");
  if (el) el.scrollIntoView({ behavior: "smooth" });
}

// System Health Check
async function initHealthCheck() {
  try {
    const res = await fetch("/health");
    if (res.ok) {
      const data = await res.json();
      const statusEl = document.getElementById("sys-status");
      const dbText = document.getElementById("db-badge-text");
      if (statusEl) statusEl.textContent = `API Healthy (${data.model_version})`;
      if (dbText) {
        dbText.textContent = data.is_mock_database ? "MongoDB (In-Memory Mock)" : "MongoDB Connected";
      }
    }
  } catch (err) {
    console.warn("Health check unreachable:", err);
  }
}

// Input listeners
function initInputListeners() {
  const input = document.getElementById("complaint-input");
  const counter = document.getElementById("char-counter");
  if (input && counter) {
    input.addEventListener("input", () => {
      const len = input.value.length;
      counter.textContent = `${len} / 10000 chars`;
      if (len < 20) {
        counter.classList.add("text-rose-400");
        counter.classList.remove("text-slate-500");
      } else {
        counter.classList.remove("text-rose-400");
        counter.classList.add("text-slate-500");
      }
    });
  }
}

// Load preset
function loadPreset(key) {
  const input = document.getElementById("complaint-input");
  if (input && PRESETS[key]) {
    input.value = PRESETS[key];
    input.dispatchEvent(new Event("input"));
  }
}

// Execute Triage Pipeline
async function executeTriage() {
  const input = document.getElementById("complaint-input");
  const text = input ? input.value.trim() : "";

  if (text.length < 20) {
    alert("Please enter at least 20 characters for complaint triage.");
    return;
  }

  const btnText = document.getElementById("triage-btn-text");
  const spinner = document.getElementById("triage-spinner");
  const submitBtn = document.getElementById("triage-submit-btn");

  if (submitBtn) submitBtn.disabled = true;
  if (spinner) spinner.classList.remove("hidden");
  if (btnText) btnText.textContent = "Processing...";

  try {
    const response = await fetch("/v1/triage", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text })
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || "Triage execution failed");
    }

    const data = await response.json();
    currentTriageResponse = data;
    renderTriageResult(data);
    fetchOverviewMetrics();
  } catch (err) {
    alert(`Error running triage: ${err.message}`);
  } finally {
    if (submitBtn) submitBtn.disabled = false;
    if (spinner) spinner.classList.add("hidden");
    if (btnText) btnText.textContent = "Execute Triage";
  }
}

// Render Triage Result
function renderTriageResult(data) {
  const placeholder = document.getElementById("results-placeholder");
  const container = document.getElementById("results-container");

  if (placeholder) placeholder.classList.add("hidden");
  if (container) container.classList.remove("hidden");

  // Headers
  document.getElementById("res-request-id").textContent = data.request_id;
  document.getElementById("res-latency").textContent = `${data.latency_ms || 12} ms`;

  // Gate Decision Pill
  const gatePill = document.getElementById("res-gate-pill");
  if (data.gate_decision === "ALLOW_ROUTING") {
    gatePill.className = "text-xs px-2.5 py-1 rounded-full font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";
    gatePill.textContent = "GATE PASSED: AUTO ROUTE";
  } else {
    gatePill.className = "text-xs px-2.5 py-1 rounded-full font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20";
    gatePill.textContent = "CONFIDENCE GATE TRIGGERED";
  }

  // 1. PII
  const piiBadge = document.getElementById("res-pii-badge");
  if (data.pii_detected) {
    piiBadge.className = "text-[10px] font-semibold px-2 py-0.5 rounded-full bg-violet-500/20 text-violet-300 border border-violet-500/30";
    piiBadge.textContent = `${data.pii_entities_count} PII Redacted`;
  } else {
    piiBadge.className = "text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-800 text-slate-400";
    piiBadge.textContent = "No PII Detected";
  }
  document.getElementById("res-redacted-text").textContent = data.redacted_text;

  // 2. Model & Classification
  document.getElementById("res-model-badge").textContent = `${data.predictor_type} (${data.model_version})`;
  document.getElementById("res-product").textContent = data.predicted_product;
  document.getElementById("res-issue").textContent = data.predicted_issue;

  // 3. Priority
  const prioBadge = document.getElementById("res-priority-badge");
  prioBadge.textContent = data.priority;
  if (data.priority === "CRITICAL") {
    prioBadge.className = "text-xs font-bold px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-400 border border-rose-500/30";
  } else if (data.priority === "HIGH") {
    prioBadge.className = "text-xs font-bold px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30";
  } else if (data.priority === "MEDIUM") {
    prioBadge.className = "text-xs font-bold px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-400 border border-blue-500/30";
  } else {
    prioBadge.className = "text-xs font-bold px-2 py-0.5 rounded-full bg-slate-800 text-slate-400";
  }
  document.getElementById("res-priority-reason").textContent = data.priority_reason;

  // 4. Confidence
  const confPct = Math.round(data.product_confidence * 100);
  const confNum = document.getElementById("res-conf-num");
  const confBar = document.getElementById("res-conf-bar");
  const gateDesc = document.getElementById("res-gate-desc");

  confNum.textContent = `${(data.product_confidence).toFixed(2)} (${confPct}%)`;
  confBar.style.width = `${Math.min(100, Math.max(5, confPct))}%`;

  if (data.product_confidence >= data.threshold) {
    confNum.className = "text-xs font-mono font-bold text-[#f2842f]";
    confBar.className = "h-2 rounded-full bg-gradient-to-r from-[#f2842f] to-[#ff9848] shadow-sm shadow-[#f2842f]/40";
    gateDesc.textContent = `Confidence exceeds required threshold tau (${data.threshold}). Automated routing approved.`;
  } else {
    confNum.className = "text-xs font-mono font-bold text-amber-400";
    confBar.className = "h-2 rounded-full bg-amber-500";
    gateDesc.textContent = `Confidence is below threshold tau (${data.threshold}). Sent to Human Review Queue.`;
  }

  // 5. Routing
  const routingBox = document.getElementById("res-routing-box");
  const assignedTeam = document.getElementById("res-assigned-team");
  const ruleId = document.getElementById("res-rule-id");
  const routingExp = document.getElementById("res-routing-explanation");
  const humanBox = document.getElementById("res-human-action-box");

  assignedTeam.textContent = data.assigned_team;
  ruleId.textContent = data.routing_rule_id;
  routingExp.textContent = data.routing_explanation;

  if (data.assigned_team === "Human Review Queue") {
    routingBox.className = "p-4 rounded-xl border border-amber-500/30 bg-amber-500/5";
    assignedTeam.className = "text-lg font-bold text-amber-400 mt-0.5";
    humanBox.classList.remove("hidden");
  } else if (data.assigned_team === "Fraud and Risk") {
    routingBox.className = "p-4 rounded-xl border border-rose-500/30 bg-rose-500/5";
    assignedTeam.className = "text-lg font-bold text-rose-400 mt-0.5";
    humanBox.classList.add("hidden");
  } else {
    routingBox.className = "p-4 rounded-xl border border-slate-800 bg-slate-950/60";
    assignedTeam.className = "text-lg font-bold text-emerald-400 mt-0.5";
    humanBox.classList.add("hidden");
  }
}

// Fetch Overview Metrics for KPI Cards
async function fetchOverviewMetrics() {
  try {
    const res = await fetch("/v1/analytics/overview");
    if (res.ok) {
      const data = await res.json();
      document.getElementById("kpi-total").textContent = data.total_requests;
      document.getElementById("kpi-auto-rate").textContent = `${data.automation_rate}%`;
      document.getElementById("kpi-pending-review").textContent = data.review_status_breakdown.PENDING || 0;
      document.getElementById("kpi-avg-conf").textContent = data.avg_confidence.toFixed(2);

      // Header Badge
      const hBadge = document.getElementById("header-review-badge");
      const pendingCount = data.review_status_breakdown.PENDING || 0;
      if (pendingCount > 0) {
        hBadge.textContent = pendingCount;
        hBadge.classList.remove("hidden");
      } else {
        hBadge.classList.add("hidden");
      }
    }
  } catch (err) {
    console.warn("Failed to fetch analytics:", err);
  }
}

function refreshConsoleData() {
  fetchOverviewMetrics();
  fetchRequestsTable();
}

function fetchConsoleData() {
  fetchOverviewMetrics();
  fetchRequestsTable();
}

// Fetch Requests Table
async function fetchRequestsTable() {
  const tbody = document.getElementById("requests-tbody");
  if (!tbody) return;

  const team = document.getElementById("filter-queue").value;
  const priority = document.getElementById("filter-priority").value;
  const status = document.getElementById("filter-status").value;
  const query = document.getElementById("search-query").value.trim();

  let url = `/v1/requests?page=${currentPage}&size=${pageSize}`;
  if (team) url += `&team=${encodeURIComponent(team)}`;
  if (priority) url += `&priority=${encodeURIComponent(priority)}`;
  if (status) url += `&review_status=${encodeURIComponent(status)}`;
  if (query) url += `&q=${encodeURIComponent(query)}`;

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error("Failed to load requests");
    const data = await res.json();

    renderTableRows(data.items);
    updatePagination(data.total, data.page, data.pages);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center py-6 text-rose-400">${err.message}</td></tr>`;
  }
}

// Render Table Rows
function renderTableRows(items) {
  const tbody = document.getElementById("requests-tbody");
  if (!items || items.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center py-8 text-slate-500">No requests match current filters.</td></tr>`;
    return;
  }

  tbody.innerHTML = items.map(item => {
    // Priority badge
    let pClass = "bg-slate-800 text-slate-400";
    if (item.priority === "CRITICAL") pClass = "bg-rose-500/20 text-rose-400 border border-rose-500/30";
    else if (item.priority === "HIGH") pClass = "bg-amber-500/20 text-amber-400 border border-amber-500/30";
    else if (item.priority === "MEDIUM") pClass = "bg-blue-500/20 text-blue-400 border border-blue-500/30";

    // Status badge
    let sClass = "bg-slate-800 text-slate-400";
    if (item.review_status === "PENDING") sClass = "bg-amber-500/20 text-amber-300 border border-amber-500/30";
    else if (item.review_status === "CORRECTED") sClass = "bg-violet-500/20 text-violet-300 border border-violet-500/30";
    else if (item.review_status === "CONFIRMED") sClass = "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30";

    const preview = item.redacted_text.length > 55 ? item.redacted_text.substring(0, 55) + "..." : item.redacted_text;

    return `
      <tr class="hover:bg-[#18253f] transition">
        <td class="py-3 px-4 font-mono font-bold text-[#f2842f]">${item.request_id}</td>
        <td class="py-3 px-4 text-slate-300 font-mono text-[11px] max-w-xs truncate" title="${escapeHtml(item.redacted_text)}">${escapeHtml(preview)}</td>
        <td class="py-3 px-4 text-white font-medium">${escapeHtml(item.predicted_product)}</td>
        <td class="py-3 px-4"><span class="px-2 py-0.5 rounded text-[10px] font-bold ${pClass}">${item.priority}</span></td>
        <td class="py-3 px-4 font-mono font-medium">${item.product_confidence.toFixed(2)}</td>
        <td class="py-3 px-4 font-semibold ${item.assigned_team === 'Human Review Queue' ? 'text-amber-400' : 'text-slate-200'}">${escapeHtml(item.assigned_team)}</td>
        <td class="py-3 px-4"><span class="px-2 py-0.5 rounded text-[10px] font-semibold ${sClass}">${item.review_status}</span></td>
        <td class="py-3 px-4 text-right space-x-1.5 whitespace-nowrap">
          <button onclick="openJourneyModal('${item.request_id}')" class="px-2.5 py-1 text-[11px] font-medium rounded bg-[#253c6d] hover:bg-[#30497d] text-slate-200 transition">Audit</button>
          ${item.review_status === 'PENDING' ? `
            <button onclick="openReviewModal('${item.request_id}', '${escapeHtml(item.predicted_product)}', '${escapeHtml(preview)}')" class="btn-palette-orange px-2.5 py-1 text-[11px] rounded transition">Review</button>
          ` : ''}
        </td>
      </tr>
    `;
  }).join("");
}

// Pagination controls
function updatePagination(total, page, pages) {
  document.getElementById("pagination-info").textContent = `Showing page ${page} of ${pages || 1} (${total} total requests)`;
  document.getElementById("page-num-display").textContent = page;
  document.getElementById("prev-page-btn").disabled = page <= 1;
  document.getElementById("next-page-btn").disabled = page >= pages;
}

function prevPage() {
  if (currentPage > 1) {
    currentPage--;
    fetchRequestsTable();
  }
}

function nextPage() {
  currentPage++;
  fetchRequestsTable();
}

// Audit Journey Modal
async function openJourneyModal(requestId) {
  try {
    const res = await fetch(`/v1/requests/${requestId}`);
    if (!res.ok) throw new Error("Could not load request details");
    const data = await res.json();

    document.getElementById("modal-req-id").textContent = data.request_id;
    document.getElementById("modal-created-at").textContent = `Ingested: ${new Date(data.created_at).toLocaleString()}`;
    document.getElementById("modal-redacted-text").textContent = data.redacted_text;
    document.getElementById("modal-prod").textContent = data.predicted_product;
    document.getElementById("modal-conf").textContent = `${data.product_confidence.toFixed(2)} (tau = ${data.threshold})`;
    document.getElementById("modal-team").textContent = data.assigned_team;
    document.getElementById("modal-status").textContent = data.review_status;
    document.getElementById("modal-explanation").textContent = data.routing_explanation;

    // Timeline events
    const timelineContainer = document.getElementById("modal-timeline-container");
    if (timelineContainer && data.timeline) {
      timelineContainer.innerHTML = data.timeline.map(t => `
        <div class="relative pl-3 pb-2 text-xs">
          <div class="absolute -left-[21px] top-1.5 w-2.5 h-2.5 rounded-full bg-[#f2842f] border-2 border-[#0a0f1b] shadow-sm shadow-[#f2842f]/50"></div>
          <div class="flex items-center gap-2">
            <span class="font-bold text-[#f2842f] uppercase">${t.stage}</span>
            <span class="text-[10px] text-slate-400 font-mono">${new Date(t.timestamp).toLocaleTimeString()}</span>
          </div>
          <div class="text-[11px] text-slate-300 font-mono mt-0.5">${JSON.stringify(t.details)}</div>
        </div>
      `).join("");
    }

    document.getElementById("modal-journey").classList.remove("hidden");
  } catch (err) {
    alert(err.message);
  }
}

function closeJourneyModal() {
  document.getElementById("modal-journey").classList.add("hidden");
}

// Review Modal
function openReviewModalFromDemo() {
  if (!currentTriageResponse) return;
  openReviewModal(
    currentTriageResponse.request_id,
    currentTriageResponse.predicted_product,
    currentTriageResponse.redacted_text.substring(0, 100) + "..."
  );
}

function openReviewModal(requestId, product, excerpt) {
  document.getElementById("review-req-id").value = requestId;
  document.getElementById("review-modal-excerpt").textContent = excerpt || "";
  const select = document.getElementById("review-product-select");
  if (select && product) {
    select.value = product;
  }
  document.getElementById("modal-review").classList.remove("hidden");
}

function closeReviewModal() {
  document.getElementById("modal-review").classList.add("hidden");
}

function toggleCorrectionFields(isCorrection) {
  const fields = document.getElementById("correction-fields");
  if (fields) {
    if (isCorrection) {
      fields.classList.remove("hidden");
    } else {
      fields.classList.add("hidden");
    }
  }
}

// Submit Review Action
async function submitReviewAction(event) {
  event.preventDefault();
  const reqId = document.getElementById("review-req-id").value;
  const action = document.querySelector('input[name="review_action"]:checked').value;
  const correctedProduct = document.getElementById("review-product-select").value;
  const notes = document.getElementById("review-notes").value;
  const reviewerId = document.getElementById("review-operator-id").value;

  const btn = document.getElementById("submit-review-btn");
  btn.disabled = true;
  btn.textContent = "Submitting...";

  try {
    const res = await fetch(`/v1/requests/${reqId}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: action,
        corrected_product: action === "CORRECT" ? correctedProduct : null,
        correction_reason: notes,
        reviewer_id: reviewerId
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Review submission failed");
    }

    const result = await res.json();
    alert(`Success! Request ${result.request_id} status updated to ${result.review_status}. Re-routed to: ${result.updated_assigned_team}`);
    closeReviewModal();
    refreshConsoleData();
    if (currentTriageResponse && currentTriageResponse.request_id === reqId) {
      // Refresh demo box if same request
      currentTriageResponse.assigned_team = result.updated_assigned_team;
      currentTriageResponse.review_status = result.review_status;
      renderTriageResult(currentTriageResponse);
    }
  } catch (err) {
    alert(`Error: ${err.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = "Submit Decision & Re-Route";
  }
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}
