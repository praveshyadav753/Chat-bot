// app/static/js/chat.js

// ── Configure marked ──────────────────────────────────────────────────────────
marked.setOptions({ gfm: true, breaks: true });

// ── State ─────────────────────────────────────────────────────────────────────
let session_id = null;
let isStreaming = false;
let uploadedFiles = [];

// ── DOM refs ──────────────────────────────────────────────────────────────────
const fileInput    = document.getElementById("documents");
const chatBox      = document.getElementById("chat-box");
const sendBtn      = document.getElementById("send-btn");
const msgInput     = document.getElementById("message");
const sessionLabel = document.getElementById("session-label");
const stagedDiv    = document.getElementById("staged-files");
const placeholder  = document.getElementById("chat-placeholder");

// ── Send button state ─────────────────────────────────────────────────────────
function refreshSendBtn() {
  const pending = uploadedFiles.filter(
    f => f.status === "uploading" || f.status === "processing"
  ).length;
  sendBtn.disabled = pending > 0 || isStreaming;
  if (isStreaming) {
    sendBtn.textContent = "Sending…";
  } else if (pending > 0) {
    const uploadingCount  = uploadedFiles.filter(f => f.status === "uploading").length;
    const processingCount = uploadedFiles.filter(f => f.status === "processing").length;
    sendBtn.textContent   = uploadingCount > 0
      ? `Uploading… (${uploadingCount})`
      : `Processing… (${processingCount})`;
  } else {
    sendBtn.textContent = "Send";
  }
}

// ── Textarea ──────────────────────────────────────────────────────────────────
msgInput.addEventListener("input", () => {
  msgInput.style.height = "auto";
  msgInput.style.height = Math.min(msgInput.scrollHeight, 140) + "px";
});
msgInput.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(e); }
});

// ── File input ────────────────────────────────────────────────────────────────
fileInput.addEventListener("change", () => {
  Array.from(fileInput.files).forEach(file => {
    const tempId = crypto.randomUUID();
    const entry  = { tempId, file, document_id: null, status: "uploading" };
    uploadedFiles.push(entry);
    renderChip(entry);
    uploadFile(entry);
  });
  fileInput.value = "";
  refreshSendBtn();
});

// ── Chip render & state machine ───────────────────────────────────────────────
function renderChip(entry) {
  const chip = document.createElement("div");
  chip.className = "staged-chip uploading";
  chip.id        = "chip-" + entry.tempId;
  chip.innerHTML = `
    <span class="chip-icon">${fileIcon(entry.file.name)}</span>
    <span class="chip-name" title="${escapeHtml(entry.file.name)}">${escapeHtml(entry.file.name)}</span>
    <span class="chip-badge">uploading</span>
    <span class="chip-spinner"></span>
    <span class="chip-remove" onclick="removeChip('${entry.tempId}')">✕</span>
  `;
  stagedDiv.appendChild(chip);
}

const CHIP_LABELS = {
  uploading: "uploading", processing: "processing",
  ready: "ready ✓", failed: "failed ✕",
};

function setChipStatus(tempId, status) {
  const entry = uploadedFiles.find(f => f.tempId === tempId);
  if (entry) entry.status = status;
  const chip = document.getElementById("chip-" + tempId);
  if (!chip) return;
  chip.classList.remove("uploading", "processing", "ready", "failed");
  chip.classList.add(status);
  const badge = chip.querySelector(".chip-badge");
  if (badge) badge.textContent = CHIP_LABELS[status] || status;
  const spinner = chip.querySelector(".chip-spinner");
  if (spinner) spinner.style.display =
    (status === "ready" || status === "failed") ? "none" : "";
  refreshSendBtn();
}

function removeChip(tempId) {
  const entry = uploadedFiles.find(f => f.tempId === tempId);
  if (entry && (entry.status === "uploading" || entry.status === "processing")) return;
  uploadedFiles = uploadedFiles.filter(f => f.tempId !== tempId);
  document.getElementById("chip-" + tempId)?.remove();
  refreshSendBtn();
}

// ── Upload file ───────────────────────────────────────────────────────────────
async function uploadFile(entry) {
  const fd = new FormData();
  fd.append("documents", entry.file);
  if (session_id) fd.append("session_id", session_id);
  try {
    const res  = await fetch("/api/documents/upload", { method: "POST", body: fd, credentials: "include" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const doc  = data.documents?.[0];
    if (!doc?.document_id) throw new Error("No document_id returned");
    entry.document_id = doc.document_id;
    setChipStatus(entry.tempId, "processing");
  } catch (err) {
    console.error("[upload] error:", err);
    setChipStatus(entry.tempId, "failed");
  }
}

// ── Document status SSE ───────────────────────────────────────────────────────
const evtSource = new EventSource("/api/document-status-stream");
evtSource.addEventListener("update", e => {
  try {
    const { document_id, status } = JSON.parse(e.data);
    const entry = uploadedFiles.find(f => f.document_id === document_id);
    if (!entry) return;
    if (status === "READY")  setChipStatus(entry.tempId, "ready");
    if (status === "FAILED") setChipStatus(entry.tempId, "failed");
  } catch (err) { console.error("[SSE doc] parse error:", err); }
});
evtSource.onerror = () => console.warn("[SSE doc] disconnected");

// ── Helpers ───────────────────────────────────────────────────────────────────
function escapeHtml(t) {
  return t.replace(/[&<>"']/g, m =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" })[m]);
}
function fileIcon(name) {
  const ext = name.split(".").pop().toLowerCase();
  return ({ pdf:"📄",doc:"📝",docx:"📝",txt:"📃",csv:"📊",xlsx:"📊",xls:"📊",
    png:"🖼",jpg:"🖼",jpeg:"🖼",gif:"🖼",webp:"🖼",mp4:"🎬",mp3:"🎵",
    zip:"📦",json:"🔧",py:"🐍",js:"⚡",ts:"⚡",html:"🌐",css:"🎨" })[ext] || "📎";
}
function hidePlaceholder() {
  if (placeholder) placeholder.style.display = "none";
}

// ── Progress bubble ───────────────────────────────────────────────────────────
// Returns the bubble element — steps and text divs are queried
// RELATIVELY off this element, never by global ID.
// This prevents multi-message bugs where querySelector finds
// the wrong element from a previous message.
function createProgressBubble() {
  hidePlaceholder();
  const row = document.createElement("div");
  row.className = "msg-row bot";
  row.id = "thinking-row";  // only one thinking row exists at a time — safe

  const label = document.createElement("div");
  label.className = "role-label";
  label.textContent = "Assistant";

  const bubble = document.createElement("div");
  bubble.className = "bubble bot progress-bubble";

  // Use classes not IDs — multiple messages can coexist in DOM
  bubble.innerHTML = `
    <div class="thinking-dots">
      <span></span><span></span><span></span>
    </div>
    <div class="progress-steps"></div>
  `;

  row.appendChild(label);
  row.appendChild(bubble);
  chatBox.appendChild(row);
  chatBox.scrollTop = chatBox.scrollHeight;
  return bubble;
}

// Add a step — queries RELATIVE to bubble, not global DOM
function addProgressStep(bubble, label) {
  const steps = bubble.querySelector(".progress-steps");  // ← relative
  const dots  = bubble.querySelector(".thinking-dots");   // ← relative
  if (!steps) return;

  if (dots) dots.style.display = "none";

  // Mark previous step done
  const prev = steps.querySelector(".step.active");
  if (prev) {
    prev.classList.remove("active");
    prev.classList.add("done");
    prev.querySelector(".step-spinner")?.remove();
    const tick = document.createElement("span");
    tick.className = "step-tick";
    tick.textContent = "✓";
    prev.appendChild(tick);
  }

  const step = document.createElement("div");
  step.className = "step active";
  step.innerHTML = `
    <span class="step-spinner"></span>
    <span class="step-label">${escapeHtml(label)}</span>
  `;
  steps.appendChild(step);
  chatBox.scrollTop = chatBox.scrollHeight;
}

// Convert progress bubble → response bubble, return textEl
function convertToResponseBubble(bubble) {
  bubble.classList.remove("progress-bubble");
  bubble.classList.add("response-bubble");

  // Mark last active step done
  const lastStep = bubble.querySelector(".step.active");  // ← relative
  if (lastStep) {
    lastStep.classList.remove("active");
    lastStep.classList.add("done");
    lastStep.querySelector(".step-spinner")?.remove();
    const tick = document.createElement("span");
    tick.className = "step-tick";
    tick.textContent = "✓";
    lastStep.appendChild(tick);
  }

  // Remove thinking dots
  bubble.querySelector(".thinking-dots")?.remove();       // ← relative

  // Append text div after steps summary
  const textDiv = document.createElement("div");
  textDiv.className = "response-text";
  bubble.appendChild(textDiv);

  return textDiv;
}

// ── Message builders ──────────────────────────────────────────────────────────
function appendUserMessage(text, attachCards) {
  hidePlaceholder();
  const row = document.createElement("div");
  row.className = "msg-row user";

  if (attachCards?.length) {
    const lbl = document.createElement("div");
    lbl.className = "role-label"; lbl.textContent = "You";
    const strip = document.createElement("div");
    strip.className = "attach-strip";
    attachCards.forEach(c => strip.appendChild(c));
    row.appendChild(lbl);
    row.appendChild(strip);
  }

  if (text) {
    const label = document.createElement("div");
    label.className = "role-label"; label.textContent = "You";
    const bubble = document.createElement("div");
    bubble.className = "bubble user";
    bubble.innerHTML = escapeHtml(text);
    if (!attachCards?.length) row.appendChild(label);
    row.appendChild(bubble);
  }

  chatBox.appendChild(row);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function createAttachCard(name) {
  const card = document.createElement("div");
  card.className = "attach-card ready";
  card.innerHTML = `
    <span class="ac-icon">${fileIcon(name)}</span>
    <div class="ac-info">
      <span class="ac-name" title="${escapeHtml(name)}">${escapeHtml(name)}</span>
      <span class="ac-status">attached</span>
    </div>
  `;
  return card;
}

// ── Markdown render per chunk ─────────────────────────────────────────────────
function renderChunk(el, fullText, cursorEl) {
  el.innerHTML = marked.parse(fullText);
  el.querySelectorAll("pre code").forEach(block => {
    if (!block.dataset.highlighted) hljs.highlightElement(block);
  });
  if (cursorEl) el.appendChild(cursorEl);
  chatBox.scrollTop = chatBox.scrollHeight;
}

// ── Send ──────────────────────────────────────────────────────────────────────
async function sendMessage(e) {
  e.preventDefault();
  const message = msgInput.value.trim();
  if (!message || sendBtn.disabled) return;

  const readyFiles       = uploadedFiles.filter(f => f.status === "ready");
  const attachCards      = readyFiles.map(f => createAttachCard(f.file.name));
  const active_documents = readyFiles
    .filter(f => f.document_id)
    .map(f => ({ document_id: f.document_id, filename: f.file.name, status: "PROCESSING" }));

  appendUserMessage(message, attachCards.length ? attachCards : null);

  msgInput.value = ""; msgInput.style.height = "auto";
  uploadedFiles  = []; stagedDiv.innerHTML = "";

  isStreaming = true;
  refreshSendBtn();

  const fd = new FormData();
  fd.append("message", message);
  if (session_id) fd.append("session_id", session_id);
  if (active_documents.length)
    fd.append("active_documents", JSON.stringify(active_documents));

  try {
    const res = await fetch("/api/chat/stream", {
      method: "POST", body: fd, credentials: "include",
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    await parseSSEStream(res);
  } catch (err) {
    console.error("[chat] error:", err);
    document.getElementById("thinking-row")?.remove();
    const row = document.createElement("div");
    row.className = "msg-row bot";
    const label = document.createElement("div");
    label.className = "role-label"; label.textContent = "Assistant";
    const bubble = document.createElement("div");
    bubble.className = "bubble bot";
    bubble.innerHTML = `<span style="color:var(--danger)">Failed to get a response. Please try again.</span>`;
    row.appendChild(label); row.appendChild(bubble);
    chatBox.appendChild(row);
  } finally {
    isStreaming = false;
    refreshSendBtn();
    msgInput.focus();
  }
}

// ── Node name → human readable label ─────────────────────────────────────────
const NODE_LABELS = {
  input_guardrails:        "Checking safety",
  summarize_conversation:  "Compacting conversation",
  document_context:        "fetching session context",
  classify:                "analyzing input",
  rag_node:                "Searching documents",
  summarize_document_node: "Reading document",
  document_analysis_node:  "Analysing document",
  llm_node:                "Generating response",
  reject:                  "Checking policy",
};

const SKIP_NODES = new Set(["persist_data", "load_state"]);

// ── SSE stream parser ─────────────────────────────────────────────────────────
async function parseSSEStream(response) {
  const reader  = response.body.getReader();
  const decoder = new TextDecoder();

  let fullText     = "";
  let buffer       = "";
  let progressBubble = null;
  let textEl         = null;
  let tokenStarted   = false;

  const cursorEl = document.createElement("span");
  cursorEl.className = "stream-cursor";

  progressBubble = createProgressBubble();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split(/\n\n|\r\n\r\n/);
    buffer = parts.pop();

    for (const part of parts) {
      const trimmed = part.trim();
      if (!trimmed || trimmed.startsWith(":")) continue;

      const dataLine = trimmed.split("\n").find(l => l.startsWith("data:"));
      if (!dataLine) continue;

      const raw = dataLine.replace(/^data:\s*/, "").trim();
      if (!raw) continue;

      // ── Plain string events ───────────────────────────────────────────────
      // Keep SESSION: support in case of legacy backend
      if (raw.startsWith("SESSION:")) {
        session_id = raw.replace("SESSION:", "").trim();
        sessionLabel.textContent = "session: " + session_id.slice(0, 8) + "…";
        continue;
      }

      // ── JSON events ───────────────────────────────────────────────────────
      let event;
      try { event = JSON.parse(raw); }
      catch { console.warn("[SSE] unrecognised:", raw); continue; }

      // {"type":"session","session_id":"..."}
      if (event.type === "session" && event.session_id) {
        session_id = event.session_id;
        sessionLabel.textContent = "session: " + session_id.slice(0, 8) + "…";
        continue;
      }

      // {"type":"end"} or {"type":"error"}
      if (event.type === "end" || event.type === "error") {
        cursorEl.remove();
        if (event.type === "error") {
          if (progressBubble)
            progressBubble.innerHTML =
              `<span style="color:var(--danger)">An error occurred. Please try again.</span>`;
        } else if (!tokenStarted) {
          if (progressBubble)
            progressBubble.innerHTML =
              `<span style="color:var(--text-sub)">No response.</span>`;
        } else if (textEl) {
          textEl.innerHTML = marked.parse(fullText);
          textEl.querySelectorAll("pre code").forEach(b => hljs.highlightElement(b));
          chatBox.scrollTop = chatBox.scrollHeight;
        }
        return;
      }

      // {"type":"progress","node":"rag_node"}
      if (event.type === "progress" && event.node) {
        if (!tokenStarted && !SKIP_NODES.has(event.node)) {
          const label = NODE_LABELS[event.node] || event.node.replace(/_/g, " ");
          addProgressStep(progressBubble, label);
        }
        continue;
      }

      // {"type":"chunk","content":"..."} — LLM token
      if (event.type === "chunk" && event.content) {
        if (!tokenStarted) {
          tokenStarted = true;
          textEl = convertToResponseBubble(progressBubble);
        }
        fullText += event.content;
        renderChunk(textEl, fullText, cursorEl);
        continue;
      }
    }
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────
window.addEventListener("load", () => {
  refreshSendBtn();
  msgInput.focus();
});