/**
 * AnonDoc v2.0 - Client Application Engine
 * Minimalist, Vanilla JS, Zero external dependencies.
 */

// Application State
const state = {
  currentJobId: null,
  accessToken: null,
  currentFilename: "",
  currentFormat: "",
  entities: [],
  categories: [],
  selectedFile: null,
  busy: false,
  partial: false,
  // Defaults; replaced by the limits the backend publishes in /api/v1/health.
  limits: { maxBytes: 25 * 1024 * 1024, extensions: [".pdf", ".docx"] },
  activeCategoryFilter: "ALL",
  activeConfidenceFilter: "ALL"
};

// Every job request carries the secret access token issued at upload.
function authFetch(url, options = {}) {
  const headers = Object.assign({}, options.headers, { Authorization: `Bearer ${state.accessToken}` });
  return fetch(url, Object.assign({}, options, { headers }));
}

// User-facing text only: the backend never returns paths or traces, and we never echo raw bodies.
async function errorMessage(res, fallback) {
  if (res.status === 404) return "La sesión expiró o fue eliminada. Cargue el documento nuevamente.";
  if (res.status === 429) return "Demasiadas solicitudes. Espere un momento e intente de nuevo.";
  try {
    const err = await res.json();
    if (typeof err.detail === "string" && err.detail) return err.detail;
  } catch (_) {
    // non-JSON body: fall through
  }
  if (res.status >= 500) return "El servidor no pudo completar la operación. Intente de nuevo más tarde.";
  return fallback;
}

const STEP_LABELS = { pending: "Pendiente", processing: "Procesando", completed: "Completado", error: "Error" };

function setStep(step, status) {
  const li = document.querySelector(`#pipeline [data-step="${step}"]`);
  if (!li) return;
  li.dataset.status = status;
  li.querySelector(".step-state").textContent = STEP_LABELS[status];
}

function resetPipeline() {
  ["upload", "analyze", "review", "anonymize", "download"].forEach(s => setStep(s, "pending"));
}

function showMessage(el, text) {
  el.textContent = text || "";
  el.hidden = !text;
}

function setBusy(flag) {
  state.busy = flag;
  [btnStart, btnClearFile, btnReanalyze, btnExecuteAnonymization, btnDownload, btnBackToUpload, btnReset]
    .forEach(b => { b.disabled = flag; });
}

function formatBytes(n) {
  if (n >= 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  if (n >= 1024) return `${Math.round(n / 1024)} KB`;
  return `${n} B`;
}

// DOM Elements
const uploadSection = document.getElementById("uploadSection");
const reviewSection = document.getElementById("reviewSection");
const resultSection = document.getElementById("resultSection");

const dropZone = document.getElementById("dropZone");
const fileInput = document.getElementById("fileInput");
const uploadProgress = document.getElementById("uploadProgress");
const progressText = document.getElementById("progressText");
const uploadError = document.getElementById("uploadError");
const fileCard = document.getElementById("fileCard");
const fileName = document.getElementById("fileName");
const fileFormat = document.getElementById("fileFormat");
const fileSize = document.getElementById("fileSize");
const btnStart = document.getElementById("btnStart");
const btnClearFile = document.getElementById("btnClearFile");
const partialBanner = document.getElementById("partialBanner");
const partialMessage = document.getElementById("partialMessage");
const btnReanalyze = document.getElementById("btnReanalyze");
const limitationsBox = document.getElementById("limitationsBox");
const limitationsList = document.getElementById("limitationsList");
const reviewError = document.getElementById("reviewError");
const categorySummary = document.getElementById("categorySummary");
const partialAckRow = document.getElementById("partialAckRow");
const partialAck = document.getElementById("partialAck");
const resIcon = document.getElementById("resIcon");
const resTitle = document.getElementById("resTitle");
const resLead = document.getElementById("resLead");
const resPartial = document.getElementById("resPartial");
const resError = document.getElementById("resError");

const docTitle = document.getElementById("docTitle");
const docMeta = document.getElementById("docMeta");
const chipTotal = document.getElementById("chipTotal");
const chipHigh = document.getElementById("chipHigh");
const chipMed = document.getElementById("chipMed");
const chipLow = document.getElementById("chipLow");

const masterCheckbox = document.getElementById("masterCheckbox");
const entitiesTableBody = document.getElementById("entitiesTableBody");
const categoryFilter = document.getElementById("categoryFilter");
const confidenceFilter = document.getElementById("confidenceFilter");

const btnSelectAll = document.getElementById("btnSelectAll");
const btnDeselectAll = document.getElementById("btnDeselectAll");
const btnAddManual = document.getElementById("btnAddManual");
const manualText = document.getElementById("manualText");
const manualCategory = document.getElementById("manualCategory");

const btnExecuteAnonymization = document.getElementById("btnExecuteAnonymization");
const customPlaceholder = document.getElementById("customPlaceholder");

const btnBackToUpload = document.getElementById("btnBackToUpload");
const btnReset = document.getElementById("btnReset");
const btnDownload = document.getElementById("btnDownload");
const resStrategy = document.getElementById("resStrategy");
const resCount = document.getElementById("resCount");
const resVerification = document.getElementById("resVerification");
const resWarnings = document.getElementById("resWarnings");

// Category Translations / Labels
const CATEGORY_LABELS = {
  PERSON: "Persona / Nombre",
  ECUADOR_CEDULA: "Cédula",
  ECUADOR_RUC: "RUC",
  PASSPORT: "Pasaporte",
  EMAIL: "Correo",
  PHONE: "Teléfono",
  CREDIT_CARD: "Tarjeta Pago",
  BANK_ACCOUNT: "Cta Bancaria",
  DATE_OF_BIRTH: "Fecha Nacimiento",
  IP_ADDRESS: "Dirección IP",
  VEHICLE_PLATE: "Placa Vehicular",
  ADDRESS: "Dirección",
  USERNAME: "Usuario",
  MEDICAL_DATA: "Dato Médico",
  FINANCIAL_DATA: "Dato Financiero"
};

// Event Listeners: File Upload
dropZone.addEventListener("click", () => { if (!state.busy) fileInput.click(); });
dropZone.addEventListener("keydown", (e) => {
  if ((e.key === "Enter" || e.key === " ") && !state.busy) {
    e.preventDefault();
    fileInput.click();
  }
});

dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("dragover");
});

dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("dragover");
});

dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("dragover");
  if (state.busy) return;
  if (e.dataTransfer.files.length > 1) {
    showMessage(uploadError, "Se procesa un solo documento a la vez. Suelte únicamente un archivo.");
    return;
  }
  if (e.dataTransfer.files.length === 1) selectFile(e.dataTransfer.files[0]);
});

fileInput.addEventListener("change", (e) => {
  if (e.target.files.length > 0) selectFile(e.target.files[0]);
  fileInput.value = "";
});

btnBackToUpload.addEventListener("click", resetToUpload);
btnReset.addEventListener("click", resetToUpload);
btnClearFile.addEventListener("click", clearSelectedFile);
btnStart.addEventListener("click", startAnalysis);
btnReanalyze.addEventListener("click", reanalyze);

// Informational only: the server re-validates size, extension and real content on every upload.
async function loadLimits() {
  try {
    const res = await fetch("/api/v1/health");
    if (!res.ok) return;
    const h = await res.json();
    if (h.max_file_size_bytes > 0) state.limits.maxBytes = h.max_file_size_bytes;
    if (Array.isArray(h.allowed_extensions) && h.allowed_extensions.length) state.limits.extensions = h.allowed_extensions;
  } catch (_) {
    // keep defaults
  }
  document.getElementById("maxSize").textContent = formatBytes(state.limits.maxBytes);
  document.getElementById("allowedFormats").textContent =
    state.limits.extensions.map(e => e.replace(".", "").toUpperCase()).join(" y ");
  fileInput.accept = state.limits.extensions.join(",");
}

function selectFile(file) {
  showMessage(uploadError, "");
  const dot = file.name.lastIndexOf(".");
  const ext = dot >= 0 ? file.name.substring(dot).toLowerCase() : "";
  if (!state.limits.extensions.includes(ext)) {
    showMessage(uploadError, `Formato no admitido. Cargue un archivo ${state.limits.extensions.map(e => e.slice(1).toUpperCase()).join(" o ")}.`);
    return;
  }
  if (file.size === 0) {
    showMessage(uploadError, "El archivo está vacío.");
    return;
  }
  if (file.size > state.limits.maxBytes) {
    showMessage(uploadError, `El archivo (${formatBytes(file.size)}) excede el tamaño máximo permitido (${formatBytes(state.limits.maxBytes)}).`);
    return;
  }
  state.selectedFile = file;
  fileName.textContent = file.name;
  fileFormat.textContent = ext.slice(1).toUpperCase();
  fileSize.textContent = formatBytes(file.size);
  fileCard.hidden = false;
  dropZone.hidden = true;
  setStep("upload", "pending");
}

function clearSelectedFile() {
  if (state.busy) return;
  state.selectedFile = null;
  fileCard.hidden = true;
  dropZone.hidden = false;
  showMessage(uploadError, "");
}

function discardServerJob() {
  if (state.currentJobId && state.accessToken) {
    // Best-effort immediate deletion of the server-side job.
    authFetch(`/api/v1/documents/${state.currentJobId}`, { method: "DELETE" }).catch(() => {});
  }
  state.currentJobId = null;
  state.accessToken = null;
}

// Upload & Analysis Pipeline. Steps reflect real backend calls only: no simulated progress.
async function startAnalysis() {
  if (state.busy || !state.selectedFile) return;
  setBusy(true);
  showMessage(uploadError, "");
  resetPipeline();
  uploadProgress.hidden = false;
  fileCard.hidden = true;

  const formData = new FormData();
  formData.append("file", state.selectedFile);
  let step = "upload";

  try {
    setStep("upload", "processing");
    progressText.textContent = "Cargando e inspeccionando el documento...";
    const uploadRes = await fetch("/api/v1/documents", { method: "POST", body: formData });
    if (!uploadRes.ok) throw new Error(await errorMessage(uploadRes, "No se pudo cargar el documento."));

    const uploadData = await uploadRes.json();
    state.currentJobId = uploadData.job_id;
    state.accessToken = uploadData.access_token;
    state.currentFilename = uploadData.filename;
    state.currentFormat = uploadData.format;
    setStep("upload", "completed");

    step = "analyze";
    setStep("analyze", "processing");
    progressText.textContent = "Extrayendo texto y detectando información sensible...";
    const analyzeRes = await authFetch(`/api/v1/documents/${state.currentJobId}/analyze`, { method: "POST" });
    if (!analyzeRes.ok) throw new Error(await errorMessage(analyzeRes, "No se pudo completar el análisis."));

    const analysisData = await analyzeRes.json();
    setStep("analyze", "completed");
    renderReviewView(analysisData);
  } catch (error) {
    setStep(step, "error");
    discardServerJob();
    showMessage(uploadError, error.message);
    fileCard.hidden = !state.selectedFile;
  } finally {
    uploadProgress.hidden = true;
    setBusy(false);
  }
}

async function reanalyze() {
  if (state.busy || !state.currentJobId) return;
  if (!confirm("Se repetirá el análisis y se perderán las ediciones realizadas en esta lista. ¿Continuar?")) return;
  setBusy(true);
  showMessage(reviewError, "");
  setStep("analyze", "processing");
  setStep("review", "pending");
  try {
    const res = await authFetch(`/api/v1/documents/${state.currentJobId}/analyze`, { method: "POST" });
    if (!res.ok) throw new Error(await errorMessage(res, "No se pudo repetir el análisis."));
    setStep("analyze", "completed");
    renderReviewView(await res.json());
  } catch (error) {
    setStep("analyze", "error");
    showMessage(reviewError, error.message);
  } finally {
    setBusy(false);
  }
}

// Render Review View
const PARTIAL_MESSAGES = {
  busy: "El motor semántico local (GLiNER) estaba ocupado con otra solicitud. Solo se aplicaron reglas deterministas; pueden faltar nombres propios y datos contextuales.",
  failed: "La detección semántica falló o excedió el tiempo límite. Solo se aplicaron reglas deterministas; pueden faltar nombres propios y datos contextuales.",
  unavailable: "El motor semántico local (GLiNER) no está disponible. Solo se aplicaron reglas deterministas; pueden faltar nombres propios y datos contextuales."
};

const CONFIDENCE_LABELS = { HIGH: "Alta", MEDIUM: "Media", LOW: "Baja" };

function renderReviewView(data) {
  state.entities = data.entities || [];
  state.categories = data.categories_found || [];
  state.partial = !!data.analysis_partial;
  state.activeCategoryFilter = "ALL";
  state.activeConfidenceFilter = "ALL";
  confidenceFilter.value = "ALL";

  docTitle.textContent = state.currentFilename;
  docMeta.textContent = `${state.currentFormat.toUpperCase()} · ${state.entities.length} entidades detectadas`;
  showMessage(reviewError, "");

  partialBanner.hidden = !state.partial;
  partialMessage.textContent = PARTIAL_MESSAGES[data.partial_reason] || PARTIAL_MESSAGES.unavailable;
  partialAckRow.hidden = !state.partial;
  partialAck.checked = false;

  // The partial warning already has its own banner.
  const notes = (data.limitations || []).filter(l => !l.startsWith("ANÁLISIS PARCIAL"));
  limitationsList.replaceChildren(...notes.map(n => {
    const li = document.createElement("li");
    li.textContent = n;
    return li;
  }));
  limitationsBox.hidden = notes.length === 0;

  // Populate Categories Filter
  categoryFilter.innerHTML = '<option value="ALL">Todas las categorías</option>';
  state.categories.forEach(cat => {
    const opt = document.createElement("option");
    opt.value = cat;
    opt.textContent = CATEGORY_LABELS[cat] || cat;
    categoryFilter.appendChild(opt);
  });
  categoryFilter.value = "ALL";

  updateMetrics();
  renderEntitiesTable();

  setStep("review", "processing");
  uploadSection.classList.remove("active");
  resultSection.classList.remove("active");
  reviewSection.classList.add("active");
}

function updateMetrics() {
  chipTotal.textContent = state.entities.length;
  chipHigh.textContent = state.entities.filter(e => e.confidence === "HIGH").length;
  chipMed.textContent = state.entities.filter(e => e.confidence === "MEDIUM").length;
  chipLow.textContent = state.entities.filter(e => e.confidence === "LOW").length;

  const counts = {};
  state.entities.forEach(e => { counts[e.category] = (counts[e.category] || 0) + 1; });
  categorySummary.replaceChildren(...Object.keys(counts).sort().map(cat => {
    const chip = document.createElement("span");
    chip.className = "chip chip-total";
    chip.textContent = `${CATEGORY_LABELS[cat] || cat}: `;
    const n = document.createElement("strong");
    n.textContent = counts[cat];
    chip.appendChild(n);
    return chip;
  }));
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

// Rows are built with textContent only, so document fragments can never inject markup.
function buildEntityRow(entity) {
  const tr = document.createElement("tr");

  const tdChk = document.createElement("td");
  const chk = document.createElement("input");
  chk.type = "checkbox";
  chk.className = "entity-chk";
  chk.dataset.id = entity.id;
  chk.checked = !!entity.selected;
  chk.setAttribute("aria-label", "Incluir en la anonimización");
  tdChk.appendChild(chk);

  const tdCat = document.createElement("td");
  tdCat.appendChild(el("span", "badge-category", CATEGORY_LABELS[entity.category] || entity.category));

  const tdText = document.createElement("td");
  tdText.appendChild(el("div", "cell-entity-text", entity.original_text));
  const ctx = el("div", "cell-context", entity.context);
  ctx.title = entity.context || "";
  tdText.appendChild(ctx);

  const tdOrigin = document.createElement("td");
  tdOrigin.appendChild(el("div", "cell-origin", entity.is_manual ? "Manual" : (entity.validation_details || "—")));

  const tdLoc = el("td", "", entity.page_or_section);

  const tdConf = document.createElement("td");
  tdConf.appendChild(el("span", `badge-confidence ${CONFIDENCE_LABELS[entity.confidence] ? entity.confidence : ""}`,
    CONFIDENCE_LABELS[entity.confidence] || entity.confidence));
  if (!entity.is_manual && entity.confidence !== "HIGH") {
    tdConf.appendChild(el("span", "badge-review", "Revisar"));
  }

  const tdAct = document.createElement("td");
  const del = el("button", "btn-danger-icon", "✕");
  del.type = "button";
  del.title = "Eliminar falso positivo";
  del.setAttribute("aria-label", "Eliminar detección");
  del.dataset.deleteId = entity.id;
  tdAct.appendChild(del);

  tr.append(tdChk, tdCat, tdText, tdOrigin, tdLoc, tdConf, tdAct);
  return tr;
}

function renderEntitiesTable() {
  entitiesTableBody.replaceChildren();

  const filtered = state.entities.filter(e => {
    const matchCat = state.activeCategoryFilter === "ALL" || e.category === state.activeCategoryFilter;
    const matchConf = state.activeConfidenceFilter === "ALL" || e.confidence === state.activeConfidenceFilter;
    return matchCat && matchConf;
  });

  if (filtered.length === 0) {
    const tr = document.createElement("tr");
    const td = el("td", "empty-row", state.entities.length === 0
      ? "No se detectaron entidades. Esto no garantiza que el documento no contenga datos personales: revíselo y agregue detecciones manuales si es necesario."
      : "No se encontraron entidades con los filtros seleccionados.");
    td.colSpan = 7;
    tr.appendChild(td);
    entitiesTableBody.appendChild(tr);
    return;
  }

  filtered.forEach(entity => entitiesTableBody.appendChild(buildEntityRow(entity)));
}

entitiesTableBody.addEventListener("change", (e) => {
  const chk = e.target.closest(".entity-chk");
  if (!chk) return;
  const ent = state.entities.find(item => item.id === chk.dataset.id);
  if (ent) ent.selected = chk.checked;
});

// Global actions
entitiesTableBody.addEventListener("click", (ev) => {
  const btn = ev.target.closest("[data-delete-id]");
  if (btn) deleteEntity(btn.dataset.deleteId);
});

function deleteEntity(id) {
  state.entities = state.entities.filter(e => e.id !== id);
  updateMetrics();
  renderEntitiesTable();
}

btnSelectAll.addEventListener("click", () => {
  state.entities.forEach(e => e.selected = true);
  renderEntitiesTable();
});

btnDeselectAll.addEventListener("click", () => {
  state.entities.forEach(e => e.selected = false);
  renderEntitiesTable();
});

masterCheckbox.addEventListener("change", (e) => {
  const isChecked = e.target.checked;
  state.entities.forEach(ent => ent.selected = isChecked);
  renderEntitiesTable();
});

categoryFilter.addEventListener("change", (e) => {
  state.activeCategoryFilter = e.target.value;
  renderEntitiesTable();
});

confidenceFilter.addEventListener("change", (e) => {
  state.activeConfidenceFilter = e.target.value;
  renderEntitiesTable();
});

// Add Manual Entity
btnAddManual.addEventListener("click", () => {
  const text = manualText.value.trim();
  if (!text) {
    showMessage(reviewError, "Ingrese el texto que desea anonimizar.");
    return;
  }
  showMessage(reviewError, "");

  const newEntity = {
    id: "manual_" + Math.random().toString(36).substring(2, 9),
    category: manualCategory.value,
    original_text: text,
    confidence: "HIGH",
    context: "Agregado manualmente por el usuario",
    page_or_section: "Manual",
    selected: true,
    is_manual: true
  };

  state.entities.unshift(newEntity);
  manualText.value = "";
  updateMetrics();
  renderEntitiesTable();
});

// Execute Anonymization
btnExecuteAnonymization.addEventListener("click", async () => {
  if (state.busy) return;
  showMessage(reviewError, "");

  if (state.partial && !partialAck.checked) {
    showMessage(reviewError, "Debe confirmar que comprende que el análisis fue parcial antes de anonimizar.");
    partialAck.focus();
    return;
  }
  const selectedCount = state.entities.filter(e => e.selected).length;
  if (selectedCount === 0 && !confirm("No ha seleccionado ninguna entidad. ¿Desea generar el documento sin cambios?")) {
    return;
  }

  setBusy(true);
  btnExecuteAnonymization.textContent = "Procesando...";
  setStep("review", "completed");
  setStep("anonymize", "processing");

  try {
    // 1. Sync the reviewed list; anonymizing a stale list would ignore the user's decisions.
    const sync = await authFetch(`/api/v1/documents/${state.currentJobId}/detections`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ entities: state.entities })
    });
    if (!sync.ok) throw new Error(await errorMessage(sync, "No se pudieron guardar los cambios de la revisión."));

    // 2. Anonymize
    const selectedStrategy = document.querySelector('input[name="strategy"]:checked').value;
    const placeholder = customPlaceholder.value.trim() || null;

    const res = await authFetch(`/api/v1/documents/${state.currentJobId}/anonymize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        strategy: selectedStrategy,
        custom_placeholder: placeholder
      })
    });

    if (!res.ok) {
      throw new Error(await errorMessage(res, "No se pudo anonimizar el documento."));
    }

    setStep("anonymize", "completed");
    renderResultView(await res.json());
  } catch (error) {
    setStep("anonymize", "error");
    setStep("review", "processing");
    showMessage(reviewError, error.message);
  } finally {
    setBusy(false);
    btnExecuteAnonymization.textContent = "🛡️ Anonimizar Documento";
  }
});

// Render Result View
function renderResultView(data) {
  const partial = !!data.analysis_partial;
  resStrategy.textContent = data.strategy_used;
  resCount.textContent = `${data.total_anonymized} elementos anonimizados`;
  resVerification.textContent = data.stats && data.stats.verification_passed ? "Superada" : "No disponible";
  btnDownload.dataset.url = data.download_url;
  showMessage(resError, "");

  resPartial.hidden = !partial;
  resIcon.textContent = partial ? "!" : "✓";
  resIcon.classList.toggle("partial", partial);
  resTitle.textContent = partial ? "Documento generado con análisis parcial" : "Documento anonimizado";
  btnDownload.textContent = partial
    ? "📥 Descargar (resultado no definitivo)"
    : "📥 Descargar documento anonimizado";

  resWarnings.replaceChildren();
  const warnings = data.warnings || [];
  if (warnings.length > 0) {
    resWarnings.appendChild(el("strong", "", "Observaciones de seguridad:"));
    const ul = document.createElement("ul");
    warnings.forEach(w => ul.appendChild(el("li", "", w)));
    resWarnings.appendChild(ul);
  }
  resWarnings.hidden = warnings.length === 0;

  setStep("download", "pending");
  reviewSection.classList.remove("active");
  resultSection.classList.add("active");
}

btnDownload.addEventListener("click", async () => {
  if (state.busy) return;
  setBusy(true);
  showMessage(resError, "");
  setStep("download", "processing");
  try {
    const res = await authFetch(btnDownload.dataset.url);
    if (!res.ok) throw new Error(await errorMessage(res, "No se pudo descargar el documento."));
    const blob = await res.blob();
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `anonimizado_${state.currentJobId.slice(0, 8)}.${state.currentFormat}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 10000);
    setStep("download", "completed");
  } catch (error) {
    setStep("download", "error");
    showMessage(resError, error.message);
  } finally {
    setBusy(false);
  }
});

function resetToUpload() {
  if (state.busy) return;
  discardServerJob();
  state.currentFilename = "";
  state.currentFormat = "";
  state.entities = [];
  state.partial = false;
  state.selectedFile = null;
  fileInput.value = "";
  fileCard.hidden = true;
  uploadProgress.hidden = true;
  dropZone.hidden = false;
  showMessage(uploadError, "");
  showMessage(reviewError, "");
  resetPipeline();

  reviewSection.classList.remove("active");
  resultSection.classList.remove("active");
  uploadSection.classList.add("active");
}

loadLimits();
