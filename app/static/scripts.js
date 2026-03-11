// app/static/js/chat.js

// ── Configure marked ─────────────────────────────────────────────────────────
marked.setOptions({
  gfm: true,      // GitHub Flavoured Markdown (tables, strikethrough, etc.)
  breaks: true,   // single newline = <br> like ChatGPT/Claude
});

// ── State ─────────────────────────────────────────────────────────────────────
let session_id = null;
let stagedFiles = []; // [{ file, tempId }]

// ── DOM refs ──────────────────────────────────────────────────────────────────
const fileInput    = document.getElementById("documents");
const chatBox      = document.getElementById("chat-box");
const sendBtn      = document.getElementById("send-btn");
const msgInput     = document.getElementById("message");
const sessionLabel = document.getElementById("session-label");
const stagedDiv    = document.getElementById("staged-files");
const placeholder  = document.getElementById("chat-placeholder");

// ── Textarea auto-resize ──────────────────────────────────────────────────────
msgInput.addEventListener("input", () => {
  msgInput.style.height = "auto";
  msgInput.style.height = Math.min(msgInput.scrollHeight, 140) + "px";
});
msgInput.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(e); }
});

// ── File staging ──────────────────────────────────────────────────────────────
fileInput.addEventListener("change", () => {
  for (const file of fileInput.files) {
    const tempId = crypto.randomUUID();
    stagedFiles.push({ file, tempId });
    renderStagedChip(file.name, tempId);
  }
  fileInput.value = "";
});

function renderStagedChip(name, tempId) {
  const chip = document.createElement("div");
  chip.className = "staged-chip";
  chip.id = "chip-" + tempId;
  chip.innerHTML = `
    <span class="chip-icon">${fileIcon(name)}</span>
    <span class="chip-name" title="${escapeHtml(name)}">${escapeHtml(name)}</span>
    <span class="chip-remove" onclick="removeStagedFile('${tempId}')">✕</span>
  `;
  stagedDiv.appendChild(chip);
}

function removeStagedFile(tempId) {
  stagedFiles = stagedFiles.filter(f => f.tempId !== tempId);
  document.getElementById("chip-" + tempId)?.remove();
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function escapeHtml(t) {
  return t.replace(/[&<>"']/g, m =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" })[m]);
}

function fileIcon(name) {
  const ext = name.split(".").pop().toLowerCase();
  const map = {
    pdf: "📄", doc: "📝", docx: "📝", txt: "📃", csv: "📊", xlsx: "📊", xls: "📊",
    png: "🖼", jpg: "🖼", jpeg: "🖼", gif: "🖼", webp: "🖼",
    mp4: "🎬", mp3: "🎵", zip: "📦", json: "🔧",
    py: "🐍", js: "⚡", ts: "⚡", html: "🌐", css: "🎨",
  };
  return map[ext] || "📎";
}

function hidePlaceholder() {
  if (placeholder) placeholder.style.display = "none";
}

// ── Attach cards ──────────────────────────────────────────────────────────────
function createAttachCard(name, tempId) {
  const card = document.createElement("div");
  card.className = "attach-card uploading";
  card.id = "ac-" + tempId;
  card.innerHTML = `
    <span class="ac-icon">${fileIcon(name)}</span>
    <div class="ac-info">
      <span class="ac-name" title="${escapeHtml(name)}">${escapeHtml(name)}</span>
      <span class="ac-status">uploading…</span>
    </div>
  `;
  return card;
}

// ── Document status SSE ───────────────────────────────────────────────────────
const evtSource = new EventSource("/api/document-status-stream");
evtSource.addEventListener("update", e => {
  try {
    const data = JSON.parse(e.data);
    const card = document.getElementById("ac-" + data.document_id);
    if (!card) return;
    if (data.status === "READY") {
      card.classList.replace("uploading", "ready");
      card.querySelector(".ac-status").textContent = "ready";
    } else if (data.status === "FAILED") {
      card.classList.replace("uploading", "failed");
      card.querySelector(".ac-status").textContent = "failed";
    }
  } catch (err) { console.error("Status parse error:", err); }
});
evtSource.onerror = () => console.warn("Document status stream disconnected");

// ── DOM builders ──────────────────────────────────────────────────────────────
function appendUserMessage(text, attachCards) {
  hidePlaceholder();
  const row = document.createElement("div");
  row.className = "msg-row user";

  if (attachCards && attachCards.length) {
    const lbl = document.createElement("div");
    lbl.className = "role-label"; lbl.textContent = "You";
    const strip = document.createElement("div");
    strip.className = "attach-strip";
    attachCards.forEach(c => strip.appendChild(c));
    row.appendChild(lbl);
    row.appendChild(strip);
  }

  const label = document.createElement("div");
  label.className = "role-label"; label.textContent = "You";
  const bubble = document.createElement("div");
  bubble.className = "bubble user";
  bubble.innerHTML = escapeHtml(text);

  if (!attachCards || !attachCards.length) row.appendChild(label);
  row.appendChild(bubble);
  chatBox.appendChild(row);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function appendThinkingRow() {
  hidePlaceholder();
  const row = document.createElement("div");
  row.className = "msg-row bot"; row.id = "thinking-row";
  const label = document.createElement("div");
  label.className = "role-label"; label.textContent = "Assistant";
  const bubble = document.createElement("div");
  bubble.className = "bubble bot";
  bubble.innerHTML = `<div class="thinking"><span></span><span></span><span></span></div>`;
  row.appendChild(label); row.appendChild(bubble);
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

// ── Markdown render per chunk ─────────────────────────────────────────────────
// Called on every incoming chunk — marked handles partial markdown gracefully.
// The cursor element is re-appended after each innerHTML update.
function renderChunk(bubbleEl, fullText, cursorEl) {
  bubbleEl.innerHTML = marked.parse(fullText);
  // Re-run syntax highlighting on any code blocks
  bubbleEl.querySelectorAll("pre code").forEach(block => {
    if (!block.dataset.highlighted) hljs.highlightElement(block);
  });
  // Re-attach cursor (innerHTML wipes it on each update)
  if (cursorEl) bubbleEl.appendChild(cursorEl);
  chatBox.scrollTop = chatBox.scrollHeight;
}

// ── Send message ──────────────────────────────────────────────────────────────
async function sendMessage(e) {
  e.preventDefault();
  const message = msgInput.value.trim();
  const hasFiles = stagedFiles.length > 0;
  if (!message && !hasFiles) return;

  const filesToUpload = [...stagedFiles];
  stagedFiles = []; stagedDiv.innerHTML = "";

  const attachCards = filesToUpload.map(({ file, tempId }) =>
    createAttachCard(file.name, tempId)
  );
  appendUserMessage(message || "", attachCards.length ? attachCards : null);

  msgInput.value = ""; msgInput.style.height = "auto";
  sendBtn.disabled = true;

  // ── Upload documents ───────────────────────────────────────────────────────
  let active_documents = [];
  if (filesToUpload.length) {
    const fd = new FormData();
    filesToUpload.forEach(({ file }) => fd.append("documents", file));
    if (session_id) fd.append("session_id", session_id);
    try {
      const res = await fetch("/api/documents/upload", {
        method: "POST", body: fd, credentials: "include",
      });
      if (!res.ok) throw new Error("Upload failed");
      const data = await res.json();
      data.documents.forEach((doc, i) => {
        const card = document.getElementById("ac-" + filesToUpload[i].tempId);
        if (card) card.id = "ac-" + doc.document_id;
        active_documents.push(doc);
      });
    } catch (err) {
      console.error("Upload error:", err);
      filesToUpload.forEach(({ tempId }) => {
        const card = document.getElementById("ac-" + tempId);
        if (card) {
          card.classList.replace("uploading", "failed");
          card.querySelector(".ac-status").textContent = "failed";
        }
      });
    }
  }

  // Files only — no message to send
  if (!message) { sendBtn.disabled = false; msgInput.focus(); return; }

  // ── Stream chat ────────────────────────────────────────────────────────────
  const fd = new FormData();
  fd.append("message", message);
  if (session_id) fd.append("session_id", session_id);
  if (active_documents.length)
    fd.append("active_documents", JSON.stringify(active_documents));

  appendThinkingRow();

  try {
    const res = await fetch("/api/chat/stream", {
      method: "POST", body: fd, credentials: "include",
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    await parseSSEStream(res);
  } catch (err) {
    console.error("Chat error:", err);
    document.getElementById("thinking-row")?.remove();
    const b = createBotBubble();
    b.innerHTML = `<span style="color:var(--danger)">Failed to get a response. Please try again.</span>`;
  } finally {
    sendBtn.disabled = false;
    msgInput.focus();
  }
}

// ── SSE stream parser ─────────────────────────────────────────────────────────
async function parseSSEStream(response) {
  const reader  = response.body.getReader();
  const decoder = new TextDecoder();

  let fullText = "";
  let buffer   = "";
  let bubbleEl = null;

  // Cursor is a real DOM node — re-appended after every innerHTML update
  const cursorEl = document.createElement("span");
  cursorEl.className = "stream-cursor";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Split on double newline (SSE spec). Also handle \r\n\r\n from some servers.
    const parts = buffer.split(/\n\n|\r\n\r\n/);
    buffer = parts.pop(); // keep incomplete trailing part

    for (const part of parts) {
      const trimmed = part.trim();
      if (!trimmed) continue;             // empty lines
      if (trimmed.startsWith(":")) continue; // SSE comments e.g. ": ping - ..."

      // Extract the data value — handle "data: value" or multiline "data:\ndata: value"
      const lines = trimmed.split("\n");
      const dataLine = lines.find(l => l.startsWith("data:"));
      if (!dataLine) continue;

      const data = dataLine.replace(/^data:\s*/, "").trim();
      if (!data) continue;

      // ── Session ID ─────────────────────────────────────────────────────────
      if (data.startsWith("SESSION:")) {
        session_id = data.replace("SESSION:", "").trim();
        sessionLabel.textContent = "session: " + session_id.slice(0, 8) + "…";
        continue;
      }

      // ── End / Error ────────────────────────────────────────────────────────
      if (data === "[END]" || data === "[ERROR]") {
        document.getElementById("thinking-row")?.remove();
        cursorEl.remove();

        if (data === "[ERROR]") {
          if (!bubbleEl) bubbleEl = createBotBubble();
          bubbleEl.innerHTML = `<span style="color:var(--danger)">An error occurred.</span>`;
        } else if (!fullText) {
          if (!bubbleEl) bubbleEl = createBotBubble();
          bubbleEl.innerHTML = `<span style="color:var(--text-sub)">No response.</span>`;
        } else {
          // Final clean render — no cursor
          bubbleEl.innerHTML = marked.parse(fullText);
          bubbleEl.querySelectorAll("pre code").forEach(b => hljs.highlightElement(b));
          chatBox.scrollTop = chatBox.scrollHeight;
        }
        return;
      }

      // ── Content chunk ──────────────────────────────────────────────────────
      try {
        const parsed = JSON.parse(data);
        if (parsed.content) {
          // First chunk: remove thinking dots, create bubble
          if (!bubbleEl) {
            document.getElementById("thinking-row")?.remove();
            bubbleEl = createBotBubble();
          }
          fullText += parsed.content;
          // Render markdown on every chunk with blinking cursor
          renderChunk(bubbleEl, fullText, cursorEl);
        }
      } catch (err) {
        console.error("JSON parse error:", err, "raw data:", data);
      }
    }
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────
window.addEventListener("load", () => msgInput.focus());