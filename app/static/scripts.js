// ── Configure marked ──────────────────────────────────────────────────────────
marked.setOptions({ gfm: true, breaks: true });

// ── State ─────────────────────────────────────────────────────────────────────
let session_id    = null;
let isStreaming   = false;
let uploadedFiles = [];
let placeholderHidden = false;   // FIX: guard so we don't query DOM repeatedly

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
    <span class="chip-remove">✕</span>
  `;
  // FIX: attach remove handler via addEventListener, not inline onclick
  chip.querySelector(".chip-remove").addEventListener("click", () => removeChip(entry.tempId));
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

// FIX: close the document status SSE when the user leaves the page
window.addEventListener("beforeunload", () => evtSource.close());

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

// FIX: guard with a boolean so we don't query/mutate the DOM on every call
function hidePlaceholder() {
  if (placeholderHidden) return;
  if (placeholder) placeholder.style.display = "none";
  placeholderHidden = true;
}

// ── Progress bubble ───────────────────────────────────────────────────────────
function createProgressBubble() {
  hidePlaceholder();
  const row = document.createElement("div");
  row.className = "msg-row bot";
  row.id = "thinking-row";

  const label = document.createElement("div");
  label.className = "role-label";
  label.textContent = "Assistant";

  const bubble = document.createElement("div");
  bubble.className = "bubble bot progress-bubble";
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

function addProgressStep(bubble, label) {
  const steps = bubble.querySelector(".progress-steps");
  const dots  = bubble.querySelector(".thinking-dots");
  if (!steps) return;

  if (dots) dots.style.display = "none";

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

function convertToResponseBubble(bubble) {
  bubble.classList.remove("progress-bubble");
  bubble.classList.add("response-bubble");

  const lastStep = bubble.querySelector(".step.active");
  if (lastStep) {
    lastStep.classList.remove("active");
    lastStep.classList.add("done");
    lastStep.querySelector(".step-spinner")?.remove();
    const tick = document.createElement("span");
    tick.className = "step-tick";
    tick.textContent = "✓";
    lastStep.appendChild(tick);
  }

  bubble.querySelector(".thinking-dots")?.remove();

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
    // FIX: always show role label above text bubble, even when attachments present
    const label = document.createElement("div");
    label.className = "role-label"; label.textContent = "You";
    const bubble = document.createElement("div");
    bubble.className = "bubble user";
    bubble.innerHTML = escapeHtml(text);
    row.appendChild(label);
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

// ── Markdown render — debounced hljs highlighting ─────────────────────────────
// FIX: only run syntax highlighting after streaming ends, not on every chunk,
//      to avoid expensive re-highlighting of the same blocks repeatedly.
let highlightTimer = null;

function renderChunk(el, fullText, cursorEl) {
  el.innerHTML = marked.parse(fullText);
  if (cursorEl) el.appendChild(cursorEl);
  chatBox.scrollTop = chatBox.scrollHeight;

  // Debounce: highlight 300 ms after the last chunk arrives
  clearTimeout(highlightTimer);
  highlightTimer = setTimeout(() => {
    el.querySelectorAll("pre code:not([data-highlighted])").forEach(block => {
      hljs.highlightElement(block);
    });
  }, 300);
}

function finalizeHighlighting(el) {
  clearTimeout(highlightTimer);
  el.querySelectorAll("pre code:not([data-highlighted])").forEach(block => {
    hljs.highlightElement(block);
  });
}

// ── Clarification submit helpers ──────────────────────────────────────────────
// FIX: these were referenced but never defined in the original code.

async function submitClarification(answer, sid) {
  // Remove the clarification widget
  const clarRow = document.getElementById("clarification-row");
  if (clarRow) {
    // Clean up keyboard listener if any
    const bubble = clarRow.querySelector(".clarif-bubble");
    if (bubble?._keyHandler) document.removeEventListener("keydown", bubble._keyHandler);
    clarRow.remove();
  }

  // Show the chosen answer as a user message
  appendUserMessage(answer, null);

  isStreaming = true;
  refreshSendBtn();

  const fd = new FormData();
  fd.append("message", answer);
  fd.append("is_clarification", "true");
  if (sid) fd.append("session_id", sid);

  try {
    const res = await fetch("/api/chat/stream", {
      method: "POST", body: fd, credentials: "include",
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    await parseSSEStream(res);
  } catch (err) {
    console.error("[clarification] error:", err);
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

function submitClarificationFromInput(sid) {
  // FIX: find the input by traversing the DOM, not by interpolating sid into a
  //      selector — avoids any injection if sid contains special characters.
  const clarRow = document.getElementById("clarification-row");
  if (!clarRow) return;
  const input = clarRow.querySelector(".clarif-input");
  if (!input) return;
  const answer = input.value.trim();
  if (!answer) return;
  submitClarification(answer, sid);
}

// ── Clarification widget ──────────────────────────────────────────────────────
function showClarificationWidget(question, options, sid) {
  document.getElementById("thinking-row")?.remove();
  hidePlaceholder();

  const row = document.createElement("div");
  row.className = "msg-row bot";
  row.id = "clarification-row";

  // FIX: ARIA role so screen readers announce this as a dialog
  row.setAttribute("role", "dialog");
  row.setAttribute("aria-modal", "false");
  row.setAttribute("aria-labelledby", "clarif-question-label");

  const label = document.createElement("div");
  label.className = "role-label";
  label.textContent = "Assistant";

  const bubble = document.createElement("div");
  bubble.className = "bubble bot clarif-bubble";

  const allOptions = options?.length ? [...options, null] : [];
  let selectedIdx    = 0;
  let showingFreetext = false;

  function render() {
    bubble.innerHTML = `
      <div class="clarif-header">
        <div class="clarif-question" id="clarif-question-label">${escapeHtml(question)}</div>
        ${allOptions.length ? `<div class="clarif-pager" aria-hidden="true">1 of 1</div>` : ""}
      </div>
      <div class="clarif-list" role="listbox" aria-labelledby="clarif-question-label">
        ${allOptions.map((opt, i) =>
          opt === null
            ? `<div class="clarif-item clarif-something ${i === selectedIdx ? "clarif-focused" : ""}"
                data-idx="${i}" role="option" aria-selected="${i === selectedIdx}" tabindex="-1">
                <span class="clarif-pencil" aria-hidden="true">✏</span>
                <span class="clarif-item-text">Something else</span>
               </div>`
            : `<div class="clarif-item ${i === selectedIdx ? "clarif-focused" : ""}"
                data-idx="${i}" role="option" aria-selected="${i === selectedIdx}" tabindex="-1">
                <span class="clarif-num" aria-hidden="true">${i + 1}</span>
                <span class="clarif-item-text">${escapeHtml(opt)}</span>
                ${i === selectedIdx ? '<span class="clarif-arrow" aria-hidden="true">→</span>' : ""}
               </div>`
        ).join("")}
        ${showingFreetext ? `
          <div class="clarif-freetext-wrap">
            <input class="clarif-input" placeholder="Type your answer…"
              aria-label="Custom answer"
              aria-describedby="clarif-hint-label" />
            <button type="button">Send</button>
          </div>` : ""}
      </div>
      <div class="clarif-hint" id="clarif-hint-label" aria-live="polite">
        ↑ ↓ to navigate · Enter to select · Esc to skip
      </div>
    `;

    // FIX: all event listeners attached programmatically — no inline handlers,
    //      no sid interpolation into HTML strings.
    bubble.querySelectorAll(".clarif-item").forEach(el => {
      el.addEventListener("click", () => {
        const idx = parseInt(el.dataset.idx);
        if (allOptions[idx] === null) {
          showingFreetext = true;
          selectedIdx = idx;
          render();
          bubble.querySelector(".clarif-input")?.focus();
        } else {
          submitClarification(allOptions[idx], sid);
        }
      });

      // FIX: only update selectedIdx state, don't re-render the whole widget on
      //      mouseenter — avoids the keyboard listener attach/detach storm.
      el.addEventListener("mouseenter", () => {
        const prev = bubble.querySelector(".clarif-item.clarif-focused");
        if (prev) {
          prev.classList.remove("clarif-focused");
          prev.setAttribute("aria-selected", "false");
        }
        el.classList.add("clarif-focused");
        el.setAttribute("aria-selected", "true");
        selectedIdx = parseInt(el.dataset.idx);
      });
    });

    // FIX: attach send button listener after render
    const sendButton = bubble.querySelector(".clarif-freetext-wrap button");
    if (sendButton) {
      sendButton.addEventListener("click", () => submitClarificationFromInput(sid));
    }

    const inputEl = bubble.querySelector(".clarif-input");
    if (inputEl) {
      inputEl.addEventListener("keydown", e => {
        if (e.key === "Enter") { e.preventDefault(); submitClarificationFromInput(sid); }
      });
      // autofocus after DOM is ready
      requestAnimationFrame(() => inputEl.focus());
    }
  }

  // FIX: keyboard handler attached ONCE, not on every render/hover
  const keyHandler = (e) => {
    if (!document.getElementById("clarification-row")) {
      document.removeEventListener("keydown", keyHandler);
      return;
    }
    if (showingFreetext) return;

    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const prev = bubble.querySelector(".clarif-item.clarif-focused");
      if (prev) {
        prev.classList.remove("clarif-focused");
        prev.setAttribute("aria-selected", "false");
      }
      selectedIdx = e.key === "ArrowDown"
        ? (selectedIdx + 1) % allOptions.length
        : (selectedIdx - 1 + allOptions.length) % allOptions.length;
      const next = bubble.querySelector(`.clarif-item[data-idx="${selectedIdx}"]`);
      if (next) {
        next.classList.add("clarif-focused");
        next.setAttribute("aria-selected", "true");
      }
    }

    if (e.key === "Enter") {
      e.preventDefault();
      const opt = allOptions[selectedIdx];
      if (opt === null) {
        showingFreetext = true;
        render();
      } else {
        submitClarification(opt, sid);
      }
    }

    if (e.key === "Escape") {
      document.getElementById("clarification-row")?.remove();
      document.removeEventListener("keydown", keyHandler);
    }
  };

  // Store reference so we can clean it up in submitClarification
  bubble._keyHandler = keyHandler;
  document.addEventListener("keydown", keyHandler);

  row.appendChild(label);
  row.appendChild(bubble);
  chatBox.appendChild(row);
  chatBox.scrollTop = chatBox.scrollHeight;

  render();

  // FIX: move focus into the widget for keyboard users
  requestAnimationFrame(() => {
    const first = bubble.querySelector(".clarif-item");
    if (first) first.focus();
  });
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
  document_context:        "Fetching session context",
  classify:                "Analyzing input",
  clarification_node:      "Asking for clarification",
  rag_node:                "Searching documents",
  summarize_document_node: "Reading document",
  document_analysis_node:  "Analysing document",
  llm_node:                "Generating response",
  reject:                  "Checking policy",
};

const SKIP_NODES = new Set(["persist_data", "load_state"]);

// ── SSE stream parser ─────────────────────────────────────────────────────────
// FIX: stream stall timeout — if no data arrives for 30 s, abort and show error
const STREAM_STALL_MS = 30_000;

async function parseSSEStream(response) {
  const reader  = response.body.getReader();
  const decoder = new TextDecoder();

  let fullText       = "";
  let buffer         = "";
  let progressBubble = null;
  let textEl         = null;
  let tokenStarted   = false;

  const cursorEl = document.createElement("span");
  cursorEl.className = "stream-cursor";

  progressBubble = createProgressBubble();

  // Stall watchdog
  let stallTimer = null;
  function resetStallTimer() {
    clearTimeout(stallTimer);
    stallTimer = setTimeout(() => {
      reader.cancel();   // abort the stream
      cursorEl.remove();
      if (progressBubble) {
        progressBubble.innerHTML =
          `<span style="color:var(--danger)">Response timed out. Please try again.</span>`;
      }
    }, STREAM_STALL_MS);
  }

  resetStallTimer();

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      resetStallTimer();   // data arrived — reset the watchdog

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

        if (raw.startsWith("SESSION:")) {
          session_id = raw.replace("SESSION:", "").trim();
          sessionLabel.textContent = "session: " + session_id.slice(0, 8) + "…";
          continue;
        }

        let event;
        try { event = JSON.parse(raw); }
        catch { console.warn("[SSE] unrecognised:", raw); continue; }

        if (event.type === "session" && event.session_id) {
          session_id = event.session_id;
          sessionLabel.textContent = "session: " + session_id.slice(0, 8) + "…";
          continue;
        }

        if (event.type === "end" || event.type === "error") {
          clearTimeout(stallTimer);
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
            // FIX: run final highlight pass now that streaming is complete
            textEl.innerHTML = marked.parse(fullText);
            finalizeHighlighting(textEl);
            chatBox.scrollTop = chatBox.scrollHeight;
          }
          return;
        }

        if (event.type === "progress" && event.node) {
          if (!tokenStarted && !SKIP_NODES.has(event.node)) {
            const label = NODE_LABELS[event.node] || event.node.replace(/_/g, " ");
            addProgressStep(progressBubble, label);
          }
          continue;
        }

        if (event.type === "clarification") {
          clearTimeout(stallTimer);
          cursorEl.remove();
          showClarificationWidget(event.question, event.options, session_id);
          return;
        }

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
  } finally {
    clearTimeout(stallTimer);
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────
window.addEventListener("load", () => {
  refreshSendBtn();
  msgInput.focus();

  // FIX: attach button needs an accessible label for screen readers
  const attachBtn = document.querySelector(".attach-btn");
  if (attachBtn && !attachBtn.getAttribute("aria-label")) {
    attachBtn.setAttribute("aria-label", "Attach files");
  }
});