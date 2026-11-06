/**
 * AnonDoc v2.0 - Client Application Engine
 * Minimalist, Vanilla JS, Zero external dependencies.
 */

// Application State
const state = {
  currentJobId: null,
  accessToken: null,
  currentFilename: "",
  entities: [],
  categories: [],
  activeCategoryFilter: "ALL",
  activeConfidenceFilter: "ALL"
};

// Every job request carries the secret access token issued at upload.
function authFetch(url, options = {}) {
  const headers = Object.assign({}, options.headers, { Authorization: `Bearer ${state.accessToken}` });
  return fetch(url, Object.assign({}, options, { headers }));
}

async function errorMessage(res, fallback) {
  try {
    const err = await res.json();
    return err.detail || fallback;
  } catch (_) {
    return fallback;
  }
}

// DOM Elements
const uploadSection = document.getElementById("uploadSection");
const reviewSection = document.getElementById("reviewSection");
const resultSection = document.getElementById("resultSection");

const dropZone = document.getElementById("dropZone");
const fileInput = document.getElementById("fileInput");
const uploadProgress = document.getElementById("uploadProgress");
const progressBar = document.getElementById("progressBar");
const progressText = document.getElementById("progressText");

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
dropZone.addEventListener("click", () => fileInput.click());

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
  if (e.dataTransfer.files.length > 0) {
    handleFileUpload(e.dataTransfer.files[0]);
  }
});

fileInput.addEventListener("change", (e) => {
  if (e.target.files.length > 0) {
    handleFileUpload(e.target.files[0]);
  }
});

btnBackToUpload.addEventListener("click", resetToUpload);
btnReset.addEventListener("click", resetToUpload);

// Upload & Analysis Pipeline
async function handleFileUpload(file) {
  const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
  if (ext !== ".pdf" && ext !== ".docx") {
    alert("Formato no admitido. Por favor cargue un archivo PDF o DOCX.");
    return;
  }

  // Show progress
  dropZone.style.display = "none";
  uploadProgress.style.display = "block";
  progressBar.style.width = "30%";
  progressText.textContent = `Cargando ${file.name}...`;

  const formData = new FormData();
  formData.append("file", file);

  try {
    // 1. Upload
    const uploadRes = await fetch("/api/v1/documents", {
      method: "POST",
      body: formData
    });

    if (!uploadRes.ok) {
      throw new Error(await errorMessage(uploadRes, "Error al cargar documento."));
    }

    const uploadData = await uploadRes.json();
    state.currentJobId = uploadData.job_id;
    state.accessToken = uploadData.access_token;
    state.currentFilename = uploadData.filename;

    progressBar.style.width = "65%";
    progressText.textContent = "Extrayendo texto y detectando información sensible (PII)...";

    // 2. Trigger Analysis
    const analyzeRes = await authFetch(`/api/v1/documents/${state.currentJobId}/analyze`, {
      method: "POST"
    });

    if (!analyzeRes.ok) {
      throw new Error(await errorMessage(analyzeRes, "Error durante el análisis."));
    }

    const analysisData = await analyzeRes.json();
    progressBar.style.width = "100%";
    progressText.textContent = "¡Análisis completado!";

    setTimeout(() => {
      renderReviewView(analysisData);
    }, 300);

  } catch (error) {
    alert(`Error: ${error.message}`);
    resetToUpload();
  }
}

// Render Review View
function renderReviewView(data) {
  state.entities = data.entities || [];
  state.categories = data.categories_found || [];

  docTitle.textContent = state.currentFilename;
  docMeta.textContent = `Identificador de sesión: ${state.currentJobId} • ${state.entities.length} entidades detectadas`;

  // Populate Categories Filter
  categoryFilter.innerHTML = '<option value="ALL">Todas las categorías</option>';
  state.categories.forEach(cat => {
    const opt = document.createElement("option");
    opt.value = cat;
    opt.textContent = CATEGORY_LABELS[cat] || cat;
    categoryFilter.appendChild(opt);
  });

  updateMetrics();
  renderEntitiesTable();

  // Switch screens
  uploadSection.classList.remove("active");
  resultSection.classList.remove("active");
  reviewSection.classList.add("active");
}

function updateMetrics() {
  chipTotal.textContent = state.entities.length;
  chipHigh.textContent = state.entities.filter(e => e.confidence === "HIGH").length;
  chipMed.textContent = state.entities.filter(e => e.confidence === "MEDIUM").length;
  chipLow.textContent = state.entities.filter(e => e.confidence === "LOW").length;
}

function renderEntitiesTable() {
  entitiesTableBody.innerHTML = "";

  const filtered = state.entities.filter(e => {
    const matchCat = state.activeCategoryFilter === "ALL" || e.category === state.activeCategoryFilter;
    const matchConf = state.activeConfidenceFilter === "ALL" || e.confidence === state.activeConfidenceFilter;
    return matchCat && matchConf;
  });

  if (filtered.length === 0) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="6" style="text-align: center; color: var(--text-muted); padding: 2rem;">No se encontraron entidades con los filtros seleccionados.</td>`;
    entitiesTableBody.appendChild(tr);
    return;
  }

  filtered.forEach(entity => {
    const tr = document.createElement("tr");

    tr.innerHTML = `
      <td>
        <input type="checkbox" data-id="${escapeHtml(entity.id)}" class="entity-chk" ${entity.selected ? "checked" : ""}>
      </td>
      <td>
        <span class="badge-category">${escapeHtml(CATEGORY_LABELS[entity.category] || entity.category)}</span>
      </td>
      <td>
        <div class="cell-entity-text">${escapeHtml(entity.original_text)}</div>
        <div class="cell-context" title="${escapeHtml(entity.context)}">${escapeHtml(entity.context)}</div>
      </td>
      <td>${escapeHtml(entity.page_or_section)}</td>
      <td>
        <span class="badge-confidence ${escapeHtml(entity.confidence)}">${escapeHtml(entity.confidence)}</span>
      </td>
      <td>
        <button class="btn-danger-icon" title="Eliminar falso positivo" data-delete-id="${escapeHtml(entity.id)}">✕</button>
      </td>
    `;
    entitiesTableBody.appendChild(tr);
  });

  // Re-attach checkbox event listeners
  document.querySelectorAll(".entity-chk").forEach(chk => {
    chk.addEventListener("change", (e) => {
      const id = e.target.getAttribute("data-id");
      const ent = state.entities.find(item => item.id === id);
      if (ent) {
        ent.selected = e.target.checked;
      }
    });
  });
}

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
    alert("Por favor ingrese el texto que desea anonimizar.");
    return;
  }

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
  const selectedCount = state.entities.filter(e => e.selected).length;
  if (selectedCount === 0) {
    if (!confirm("No has seleccionado ninguna entidad. ¿Deseas generar el documento sin cambios?")) {
      return;
    }
  }

  btnExecuteAnonymization.disabled = true;
  btnExecuteAnonymization.textContent = "Procesando...";

  try {
    // 1. Sync updated entities
    await authFetch(`/api/v1/documents/${state.currentJobId}/detections`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ entities: state.entities })
    });

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
      throw new Error(await errorMessage(res, "Error en la anonimización."));
    }

    const resultData = await res.json();
    renderResultView(resultData);

  } catch (error) {
    alert(`Error: ${error.message}`);
  } finally {
    btnExecuteAnonymization.disabled = false;
    btnExecuteAnonymization.textContent = "🛡️ Anonimizar Documento";
  }
});

// Render Result View
function renderResultView(data) {
  resStrategy.textContent = data.strategy_used;
  resCount.textContent = `${data.total_anonymized} elementos anonimizados`;
  btnDownload.dataset.url = data.download_url;

  if (data.warnings && data.warnings.length > 0) {
    resWarnings.style.display = "block";
    resWarnings.innerHTML = `<strong>Observaciones de seguridad:</strong><ul>${data.warnings.map(w => `<li>${escapeHtml(w)}</li>`).join("")}</ul>`;
  } else {
    resWarnings.style.display = "none";
  }

  reviewSection.classList.remove("active");
  resultSection.classList.add("active");
}

btnDownload.addEventListener("click", async (ev) => {
  ev.preventDefault();
  try {
    const res = await authFetch(btnDownload.dataset.url);
    if (!res.ok) throw new Error(await errorMessage(res, "No se pudo descargar el documento."));
    const blob = await res.blob();
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `anonimizado_${state.currentJobId.slice(0, 8)}.${blob.type === "application/pdf" ? "pdf" : "docx"}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 10000);
  } catch (error) {
    alert(`Error: ${error.message}`);
  }
});

function resetToUpload() {
  if (state.currentJobId && state.accessToken) {
    // Best-effort immediate deletion of the server-side job.
    authFetch(`/api/v1/documents/${state.currentJobId}`, { method: "DELETE" }).catch(() => {});
  }
  state.currentJobId = null;
  state.accessToken = null;
  state.currentFilename = "";
  state.entities = [];
  fileInput.value = "";
  uploadProgress.style.display = "none";
  dropZone.style.display = "block";

  reviewSection.classList.remove("active");
  resultSection.classList.remove("active");
  uploadSection.classList.add("active");
}

function escapeHtml(text) {
  if (!text) return "";
  const div = document.createElement("div");
  div.textContent = String(text);
  return div.innerHTML.replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}
