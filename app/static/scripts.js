// app/static/js/chat.js

// ── Configure marked ──────────────────────────────────────────────────────────
marked.setOptions({ gfm: true, breaks: true });

// ── State ─────────────────────────────────────────────────────────────────────
let session_id = null;
let isStreaming = false;

// { tempId, file, document_id, status: "uploading"|"processing"|"ready"|"failed" }
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

// ── File input → immediate upload ────────────────────────────────────────────
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

// ── Upload file immediately on selection ──────────────────────────────────────
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

// ── Progress bar (shown while graph nodes run) ────────────────────────────────
// Lives inside the thinking bubble — replaced by real response when LLM starts.
function createProgressBubble() {
  hidePlaceholder();
  const row = document.createElement("div");
  row.className = "msg-row bot"; row.id = "thinking-row";

  const label = document.createElement("div");
  label.className = "role-label"; label.textContent = "Assistant";

  const bubble = document.createElement("div");
  bubble.className = "bubble bot progress-bubble";

  // Thinking dots (shown before first progress event)
  bubble.innerHTML = `
    <div class="thinking" id="thinking-dots">
      <span></span><span></span><span></span>
    </div>
    <div class="progress-steps" id="progress-steps"></div>
  `;

  row.appendChild(label);
  row.appendChild(bubble);
  chatBox.appendChild(row);
  chatBox.scrollTop = chatBox.scrollHeight;
  return bubble;
}

// Add a step to the progress bubble
function addProgressStep(label) {
  const steps = document.getElementById("progress-steps");
  const dots  = document.getElementById("thinking-dots");
  if (!steps) return;

  // Hide dots once we have real progress
  if (dots) dots.style.display = "none";

  // Mark previous step as done
  const prev = steps.querySelector(".step.active");
  if (prev) {
    prev.classList.remove("active");
    prev.classList.add("done");
    prev.querySelector(".step-spinner")?.remove();
    const tick = document.createElement("span");
    tick.className = "step-tick"; tick.textContent = "✓";
    prev.appendChild(tick);
  }

  // Add new active step
  const step = document.createElement("div");
  step.className = "step active";
  step.innerHTML = `
    <span class="step-spinner"></span>
    <span class="step-label">${escapeHtml(label)}</span>
  `;
  steps.appendChild(step);
  chatBox.scrollTop = chatBox.scrollHeight;
}

// When LLM starts streaming — convert progress bubble into a real response bubble
function convertToResponseBubble(progressBubble) {
  progressBubble.classList.remove("progress-bubble");
  progressBubble.classList.add("response-bubble");

  // Mark the last step as done
  const lastStep = progressBubble.querySelector(".step.active");
  if (lastStep) {
    lastStep.classList.remove("active");
    lastStep.classList.add("done");
    lastStep.querySelector(".step-spinner")?.remove();
    const tick = document.createElement("span");
    tick.className = "step-tick"; tick.textContent = "✓";
    lastStep.appendChild(tick);
  }

  // Clear progress UI and prepare for text
  const progressSteps = progressBubble.querySelector("#progress-steps");
  const thinkingDots  = progressBubble.querySelector("#thinking-dots");
  if (thinkingDots)  thinkingDots.remove();

  // Create the text content div AFTER the steps summary
  const textDiv = document.createElement("div");
  textDiv.className = "response-text";
  progressBubble.appendChild(textDiv);

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

function createBotBubble() {
  hidePlaceholder();
  const row = document.createElement("div");
  row.className = "msg-row bot";
  const label = document.createElement("div");
  label.className = "role-label"; label.textContent = "Assistant";
  const bubble = document.createElement("div");
  bubble.className = "bubble bot";
  row.appendChild(label); row.appendChild(bubble);
  chatBox.appendChild(row);
  return bubble;
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
    const b = createBotBubble();
    b.innerHTML = `<span style="color:var(--danger)">Failed to get a response. Please try again.</span>`;
  } finally {
    isStreaming = false;
    refreshSendBtn();
    msgInput.focus();
  }
}

// ── SSE stream parser — handles typed events ──────────────────────────────────
//
// Event types from backend:
//   { type: "session",  session_id: "abc" }
//   { type: "progress", node: "rag_node", label: "Searching documents…" }
//   { type: "token",    content: "Hello" }
//   { type: "end" }
//   { type: "error",    message: "..." }
//
// ── Node name → human readable label ────────────────────────────────────────
const NODE_LABELS = {
  load_state:              "Loading history",
  input_guardrails:        "Checking safety",
  check_messages_length:   "Checking memory",
  summarize_conversation:  "Summarizing history",
  document_context:        "Loading documents",
  classify:                "Classifying intent",
  rag_node:                "Searching documents",
  summarize_document_node: "Reading document",
  document_analysis_node:  "Analysing document",
  llm_node:                "Generating response",
  persist_data:            "Saving",
  reject:                  "Checking policy",
};

// Nodes to silently skip — not interesting to show the user
const SKIP_NODES = new Set(["persist_data", "load_state"]);

async function parseSSEStream(response) {
  const reader  = response.body.getReader();
  const decoder = new TextDecoder();

  let fullText       = "";
  let buffer         = "";
  let progressBubble = null;  // bot bubble shown during node execution
  let textEl         = null;  // text div inside bubble for LLM tokens
  let tokenStarted   = false; // true once first LLM token arrives

  const cursorEl = document.createElement("span");
  cursorEl.className = "stream-cursor";

  // Show thinking bubble immediately
  progressBubble = createProgressBubble();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Split on SSE double-newline boundary
    const parts = buffer.split(/\n\n|\r\n\r\n/);
    buffer = parts.pop(); // keep incomplete trailing chunk

    for (const part of parts) {
      const trimmed = part.trim();
      if (!trimmed) continue;
      if (trimmed.startsWith(":")) continue; // ": ping - ..." comments

      // Extract data line
      const dataLine = trimmed.split("\n").find(l => l.startsWith("data:"));
      if (!dataLine) continue;

      const raw = dataLine.replace(/^data:\s*/, "").trim();
      if (!raw) continue;

      // ── SESSION:<id>  (plain string, not JSON) ────────────────────────────
      if (raw.startsWith("SESSION:")) {
        session_id = raw.replace("SESSION:", "").trim();
        sessionLabel.textContent = "session: " + session_id.slice(0, 8) + "…";
        continue;
      }

      // ── [END] / [ERROR]  (plain strings) ─────────────────────────────────
      if (raw === "[END]" || raw === "[ERROR]") {
        cursorEl.remove();

        if (raw === "[ERROR]") {
          if (progressBubble) {
            progressBubble.innerHTML =
              `<span style="color:var(--danger)">An error occurred. Please try again.</span>`;
          }
        } else if (!tokenStarted) {
          // Graph finished but no LLM tokens were ever sent
          if (progressBubble) {
            progressBubble.innerHTML =
              `<span style="color:var(--text-sub)">No response.</span>`;
          }
        } else if (textEl) {
          // Final clean markdown render — no cursor
          textEl.innerHTML = marked.parse(fullText);
          textEl.querySelectorAll("pre code").forEach(b => hljs.highlightElement(b));
          chatBox.scrollTop = chatBox.scrollHeight;
        }
        return;
      }

      // ── JSON events ───────────────────────────────────────────────────────
      let event;
      try {
        event = JSON.parse(raw);
      } catch {
        // Not JSON and not a known plain string — ignore
        console.warn("[SSE] unrecognised data:", raw);
        continue;
      }

      // ── {"type": "progress", "node": "rag_node"} ──────────────────────────
      // Emitted by your backend for each graph node that runs.
      // Only show before LLM tokens start — once streaming begins, ignore.
      if (event.type === "progress" && event.node) {
        if (!tokenStarted && !SKIP_NODES.has(event.node)) {
          const label = NODE_LABELS[event.node] || event.node.replace(/_/g, " ");
          addProgressStep(label);
        }
        continue;
      }

      // ── {"content": "..."} — LLM token chunk ─────────────────────────────
      // Your backend sends raw content chunks (no "type" field).
      if (event.content) {
        if (!tokenStarted) {
          // First token: convert the progress bubble into a response bubble
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