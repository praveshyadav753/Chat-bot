// app/static/scripts.js
// Handles: SSE streaming, file upload, chat UI rendering.
// Session management is in session_manager.js

marked.setOptions({ gfm: true, breaks: true });

// ── State ─────────────────────────────────────────────────────────────────────
let session_id      = null;
let isStreaming     = false;
let uploadedFiles   = [];       // active session's files only
let placeholderHidden = false;

// ── DOM refs ──────────────────────────────────────────────────────────────────
const fileInput    = document.getElementById("documents");
const chatBox      = document.getElementById("chat-box");
const sendBtn      = document.getElementById("send-btn");
const msgInput     = document.getElementById("message");
const sessionLabel = document.getElementById("session-label");
const stagedDiv    = document.getElementById("staged-files");

// ── Send button ───────────────────────────────────────────────────────────────
function refreshSendBtn() {
  const pending = uploadedFiles.filter(
    f => f.status === "uploading" || f.status === "processing"
  ).length;
  sendBtn.disabled = pending > 0 || isStreaming;
  if (isStreaming) {
    sendBtn.textContent = "Sending…";
  } else if (pending > 0) {
    const u = uploadedFiles.filter(f => f.status === "uploading").length;
    const p = uploadedFiles.filter(f => f.status === "processing").length;
    sendBtn.textContent = u > 0 ? `Uploading… (${u})` : `Processing… (${p})`;
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
    // Capture session_id at upload time — even if user switches session mid-upload,
    // the file will be linked to the correct session
    uploadFile(entry, window.session_id || session_id);
  });
  fileInput.value = "";
  refreshSendBtn();
});

// ── Chip render ───────────────────────────────────────────────────────────────
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
  chip.querySelector(".chip-remove").addEventListener("click", () => removeChip(entry.tempId));
  stagedDiv.appendChild(chip);
}

const CHIP_LABELS = {
  uploading: "uploading", processing: "processing",
  ready: "ready ✓", failed: "failed ✕",
};

function setChipStatus(tempId, status) {
  // Find entry in uploadedFiles (active session's files)
  const entry = uploadedFiles.find(f => f.tempId === tempId);
  if (entry) entry.status = status;

  const chip = document.getElementById("chip-" + tempId);
  if (!chip) return;  // chip not visible (user may have switched session)
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
// uploadSid captured at call time — survives session switches during async upload
async function uploadFile(entry, uploadSid) {
  const fd = new FormData();
  fd.append("documents", entry.file);
  // Use the session ID captured when upload started — NOT window.session_id
  // This prevents mid-switch race conditions
  if (uploadSid) fd.append("session_id", uploadSid);
  try {
    const res  = await fetch("/api/documents/upload", { method: "POST", body: fd, credentials: "include" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const doc  = data.documents?.[0];
    if (!doc?.document_id) throw new Error("No document_id returned");
    entry.document_id = doc.document_id;

    // Store document_id on the entry — SSE handler needs it
    // If user has switched sessions, update the file in that session's store
    if (window.sessionMgr && uploadSid !== (window.session_id || session_id)) {
      // Upload completed for a different session than currently active
      // Update the entry in that session's file store
      const sessionFilesForUploadSession = window.sessionMgr.getSessionFiles(uploadSid);
      const storedEntry = sessionFilesForUploadSession.find(f => f.tempId === entry.tempId);
      if (storedEntry) {
        storedEntry.document_id = doc.document_id;
        storedEntry.status = "processing";
      }
    }

    setChipStatus(entry.tempId, "processing");
  } catch (err) {
    console.error("[upload] error:", err);
    setChipStatus(entry.tempId, "failed");
  }
}

// ── Document status SSE ───────────────────────────────────────────────────────
// Single persistent connection — user stays connected while on the page
const evtSource = new EventSource("/api/document-status-stream");

evtSource.addEventListener("update", e => {
  try {
    const { document_id, status } = JSON.parse(e.data);

    // Search active session's files first
    let entry = uploadedFiles.find(f => f.document_id === document_id);

    // If not found in active session, search ALL sessions' file stores
    // This handles the case where user uploaded in session A, switched to B,
    // and the SSE update arrives
    if (!entry && window.sessionMgr) {
      for (const sid of Object.keys(window.sessionMgr.getSessionFiles
        ? _getAllSessionIds() : {})) {
        const files = window.sessionMgr.getSessionFiles(sid);
        entry = files.find(f => f.document_id === document_id);
        if (entry) {
          // Update the entry in that session's store
          if (status === "READY")  entry.status = "ready";
          if (status === "FAILED") entry.status = "failed";
          // Only update chip if it's the active session
          if (sid === (window.session_id || session_id)) {
            if (status === "READY")  setChipStatus(entry.tempId, "ready");
            if (status === "FAILED") setChipStatus(entry.tempId, "failed");
          }
          return;
        }
      }
    }

    if (!entry) return;  // doc not found in any session — ignore

    if (status === "READY")  setChipStatus(entry.tempId, "ready");
    if (status === "FAILED") setChipStatus(entry.tempId, "failed");
  } catch (err) {
    console.error("[SSE doc] parse error:", err);
  }
});

evtSource.onerror = () => console.warn("[SSE doc] disconnected");
window.addEventListener("beforeunload", () => evtSource.close());

// Helper to get all tracked session IDs from sessionFiles
function _getAllSessionIds() {
  if (!window.sessionMgr?.getSessionFiles) return {};
  // session_manager.js exposes getSessionFiles(id) — we need the keys
  // They're stored in its closure; we track them here via a mirror
  return window._sessionFileKeys || {};
}

// ── Per-session file swap — called by session_manager.js ─────────────────────
// When switching sessions, session_manager calls this to swap the file arrays
// and re-render the chip tray for the target session
function setUploadedFiles(files, sessionId) {
  uploadedFiles = files;

  // Track session IDs for SSE cross-session lookup
  if (!window._sessionFileKeys) window._sessionFileKeys = {};
  window._sessionFileKeys[sessionId] = true;

  // Re-render chip tray for this session's files
  stagedDiv.innerHTML = "";
  files.forEach(entry => {
    renderChip(entry);
    // Restore correct visual state for each chip
    if (entry.status !== "uploading") {
      setChipStatus(entry.tempId, entry.status);
    }
  });

  placeholderHidden = false;
  isStreaming = false;
  refreshSendBtn();
}

// Called by session_manager to read current session's files before switching
function getUploadedFiles() {
  return [...uploadedFiles];
}

// Expose to session_manager.js
window.setUploadedFiles  = setUploadedFiles;
window.getUploadedFiles  = getUploadedFiles;
window.appendUserMessage = appendUserMessage;  // used by history loader

// ── Helpers ───────────────────────────────────────────────────────────────────
function escapeHtml(t) {
  return t.replace(/[&<>"']/g, m =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"})[m]);
}
function fileIcon(name) {
  const ext = name.split(".").pop().toLowerCase();
  return ({pdf:"📄",doc:"📝",docx:"📝",txt:"📃",csv:"📊",xlsx:"📊",xls:"📊",
    png:"🖼",jpg:"🖼",jpeg:"🖼",gif:"🖼",webp:"🖼",mp4:"🎬",mp3:"🎵",
    zip:"📦",json:"🔧",py:"🐍",js:"⚡",ts:"⚡",html:"🌐",css:"🎨"})[ext] || "📎";
}
function hidePlaceholder() {
  if (placeholderHidden) return;
  const ph = document.getElementById("chat-placeholder");
  if (ph) ph.style.display = "none";
  placeholderHidden = true;
}

// ── Progress bubble ───────────────────────────────────────────────────────────
function createProgressBubble() {
  hidePlaceholder();
  const row = document.createElement("div");
  row.className = "msg-row bot"; row.id = "thinking-row";
  const label = document.createElement("div");
  label.className = "role-label"; label.textContent = "Assistant";
  const bubble = document.createElement("div");
  bubble.className = "bubble bot progress-bubble";
  bubble.innerHTML = `
    <div class="thinking-dots"><span></span><span></span><span></span></div>
    <div class="progress-steps"></div>
  `;
  row.appendChild(label); row.appendChild(bubble);
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
    prev.classList.remove("active"); prev.classList.add("done");
    prev.querySelector(".step-spinner")?.remove();
    const tick = document.createElement("span");
    tick.className = "step-tick"; tick.textContent = "✓";
    prev.appendChild(tick);
  }
  const step = document.createElement("div");
  step.className = "step active";
  step.innerHTML = `<span class="step-spinner"></span><span class="step-label">${escapeHtml(label)}</span>`;
  steps.appendChild(step);
  chatBox.scrollTop = chatBox.scrollHeight;
}
function convertToResponseBubble(bubble) {
  bubble.classList.remove("progress-bubble"); bubble.classList.add("response-bubble");
  bubble.closest(".msg-row")?.removeAttribute("id");
  const lastStep = bubble.querySelector(".step.active");
  if (lastStep) {
    lastStep.classList.remove("active"); lastStep.classList.add("done");
    lastStep.querySelector(".step-spinner")?.remove();
    const tick = document.createElement("span");
    tick.className = "step-tick"; tick.textContent = "✓";
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
    row.appendChild(lbl); row.appendChild(strip);
  }
  if (text) {
    const label = document.createElement("div");
    label.className = "role-label"; label.textContent = "You";
    const bubble = document.createElement("div");
    bubble.className = "bubble user"; bubble.innerHTML = escapeHtml(text);
    row.appendChild(label); row.appendChild(bubble);
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

// ── Markdown render ───────────────────────────────────────────────────────────
let highlightTimer = null;
function renderChunk(el, fullText, cursorEl) {
  el.innerHTML = marked.parse(fullText);
  if (cursorEl) el.appendChild(cursorEl);
  chatBox.scrollTop = chatBox.scrollHeight;
  clearTimeout(highlightTimer);
  highlightTimer = setTimeout(() => {
    el.querySelectorAll("pre code:not([data-highlighted])").forEach(b => hljs.highlightElement(b));
  }, 300);
}
function finalizeHighlighting(el) {
  clearTimeout(highlightTimer);
  el.querySelectorAll("pre code:not([data-highlighted])").forEach(b => hljs.highlightElement(b));
}

// ── Clarification ─────────────────────────────────────────────────────────────
async function submitClarification(answer, sid) {
  const clarRow = document.getElementById("clarification-row");
  if (clarRow) {
    clarRow.querySelector(".clarif-bubble")?._keyHandler &&
      document.removeEventListener("keydown", clarRow.querySelector(".clarif-bubble")._keyHandler);
    clarRow.remove();
  }
  appendUserMessage(answer, null);
  isStreaming = true; refreshSendBtn();
  const fd = new FormData();
  fd.append("message", answer);
  fd.append("is_clarification", "true");
  const activeSid = window.session_id || sid || session_id;
  if (activeSid) fd.append("session_id", activeSid);
  try {
    const res = await fetch("/api/chat/stream", { method: "POST", body: fd, credentials: "include" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    await parseSSEStream(res);
  } catch (err) {
    console.error("[clarification] error:", err);
    _appendErrorBubble("Failed. Please try again.");
  } finally {
    isStreaming = false; refreshSendBtn(); msgInput.focus();
  }
}
function submitClarificationFromInput(sid) {
  const input = document.getElementById("clarification-row")?.querySelector(".clarif-input");
  if (!input?.value.trim()) return;
  submitClarification(input.value.trim(), sid);
}
function showClarificationWidget(question, options, sid) {
  document.getElementById("thinking-row")?.remove();
  hidePlaceholder();
  const row = document.createElement("div");
  row.className = "msg-row bot"; row.id = "clarification-row";
  row.setAttribute("role","dialog"); row.setAttribute("aria-modal","false");
  row.setAttribute("aria-labelledby","clarif-question-label");
  const label = document.createElement("div");
  label.className = "role-label"; label.textContent = "Assistant";
  const bubble = document.createElement("div");
  bubble.className = "bubble bot clarif-bubble";
  const allOptions = options?.length ? [...options, null] : [];
  let selectedIdx = 0, showingFreetext = false;
  function render() {
    bubble.innerHTML = `
      <div class="clarif-question" id="clarif-question-label">${escapeHtml(question)}</div>
      <div class="clarif-list" role="listbox">
        ${allOptions.map((opt, i) => opt === null
          ? `<div class="clarif-item clarif-something ${i===selectedIdx?"clarif-focused":""}" data-idx="${i}" role="option" tabindex="-1">
              <span class="clarif-pencil">✏</span><span class="clarif-item-text">Something else</span></div>`
          : `<div class="clarif-item ${i===selectedIdx?"clarif-focused":""}" data-idx="${i}" role="option" tabindex="-1">
              <span class="clarif-num">${i+1}</span>
              <span class="clarif-item-text">${escapeHtml(opt)}</span>
              ${i===selectedIdx?'<span class="clarif-arrow">→</span>':""}</div>`
        ).join("")}
        ${showingFreetext?`<div class="clarif-freetext-wrap">
          <input class="clarif-input" placeholder="Type your answer…" aria-label="Custom answer"/>
          <button type="button">Send</button></div>`:""}
      </div>
      <div class="clarif-hint" aria-live="polite">↑ ↓ navigate · Enter select · Esc skip</div>
    `;
    bubble.querySelectorAll(".clarif-item").forEach(el => {
      el.addEventListener("click", () => {
        const idx = parseInt(el.dataset.idx);
        if (allOptions[idx]===null){showingFreetext=true;selectedIdx=idx;render();bubble.querySelector(".clarif-input")?.focus();}
        else submitClarification(allOptions[idx], sid);
      });
      el.addEventListener("mouseenter", () => {
        bubble.querySelector(".clarif-item.clarif-focused")?.classList.remove("clarif-focused");
        el.classList.add("clarif-focused"); selectedIdx=parseInt(el.dataset.idx);
      });
    });
    bubble.querySelector(".clarif-freetext-wrap button")
      ?.addEventListener("click", () => submitClarificationFromInput(sid));
    const inp = bubble.querySelector(".clarif-input");
    if (inp) {
      inp.addEventListener("keydown", e => {if(e.key==="Enter"){e.preventDefault();submitClarificationFromInput(sid);}});
      requestAnimationFrame(() => inp.focus());
    }
  }
  const keyHandler = e => {
    if (!document.getElementById("clarification-row")){document.removeEventListener("keydown",keyHandler);return;}
    if (showingFreetext) return;
    if (e.key==="ArrowDown"||e.key==="ArrowUp") {
      e.preventDefault();
      bubble.querySelector(".clarif-item.clarif-focused")?.classList.remove("clarif-focused");
      selectedIdx=e.key==="ArrowDown"?(selectedIdx+1)%allOptions.length:(selectedIdx-1+allOptions.length)%allOptions.length;
      bubble.querySelector(`.clarif-item[data-idx="${selectedIdx}"]`)?.classList.add("clarif-focused");
    }
    if (e.key==="Enter"){e.preventDefault();const opt=allOptions[selectedIdx];if(opt===null){showingFreetext=true;render();}else submitClarification(opt,sid);}
    if (e.key==="Escape"){document.getElementById("clarification-row")?.remove();document.removeEventListener("keydown",keyHandler);}
  };
  bubble._keyHandler = keyHandler;
  document.addEventListener("keydown", keyHandler);
  row.appendChild(label); row.appendChild(bubble);
  chatBox.appendChild(row); chatBox.scrollTop=chatBox.scrollHeight;
  render();
  requestAnimationFrame(() => bubble.querySelector(".clarif-item")?.focus());
}

// ── Error bubble helper ───────────────────────────────────────────────────────
function _appendErrorBubble(msg) {
  document.getElementById("thinking-row")?.remove();
  const row = document.createElement("div"); row.className="msg-row bot";
  const lbl = document.createElement("div"); lbl.className="role-label"; lbl.textContent="Assistant";
  const bbl = document.createElement("div"); bbl.className="bubble bot";
  bbl.innerHTML=`<span style="color:var(--danger)">${escapeHtml(msg)}</span>`;
  row.appendChild(lbl); row.appendChild(bbl); chatBox.appendChild(row);
}

// ── Send ──────────────────────────────────────────────────────────────────────
async function sendMessage(e) {
  e.preventDefault();
  const message = msgInput.value.trim();
  if (!message || sendBtn.disabled) return;

  const readyFiles  = uploadedFiles.filter(f => f.status === "ready");
  const attachCards = readyFiles.map(f => createAttachCard(f.file.name));
  const active_documents = readyFiles
    .filter(f => f.document_id)
    .map(f => ({ document_id: f.document_id, filename: f.file.name, status: "PROCESSING" }));

  appendUserMessage(message, attachCards.length ? attachCards : null);
  msgInput.value=""; msgInput.style.height="auto";

  // Clear sent files from the tray (keep unsent ones)
  uploadedFiles = uploadedFiles.filter(f => f.status !== "ready");
  stagedDiv.querySelectorAll(".staged-chip.ready").forEach(el => el.remove());

  isStreaming = true; refreshSendBtn();

  if (window._onMessageSent) await window._onMessageSent(message);

  const fd = new FormData();
  fd.append("message", message);
  const activeSid = window.session_id || session_id;
  if (activeSid) fd.append("session_id", activeSid);
  if (active_documents.length)
    fd.append("active_documents", JSON.stringify(active_documents));

  try {
    const res = await fetch("/api/chat/stream", { method:"POST", body:fd, credentials:"include" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    await parseSSEStream(res);
  } catch (err) {
    console.error("[chat] error:", err);
    _appendErrorBubble("Failed to get a response. Please try again.");
  } finally {
    isStreaming=false; refreshSendBtn(); msgInput.focus();
  }
}

// ── Node labels ───────────────────────────────────────────────────────────────
const NODE_LABELS = {
  input_guardrails:        "Checking safety",
  summarize_conversation:  "Compacting conversation",
  document_context:        "Fetching session context",
  classify:                "Analyzing intent",
  clarification_node:      "Asking for clarification",
  rag_node:                "Searching documents",
  tool_node:               "Running tools",
  summarize_document_node: "Reading document",
  document_analysis_node:  "Analysing document",
  llm_node:                "Generating response",
  reject:                  "Checking policy",
};
const SKIP_NODES    = new Set(["persist_data","load_state"]);
const STREAM_STALL_MS = 30_000;

// ── SSE parser ────────────────────────────────────────────────────────────────
async function parseSSEStream(response) {
  const reader=response.body.getReader(), decoder=new TextDecoder();
  let fullText="", buffer="", progressBubble=null, textEl=null, tokenStarted=false;
  const cursorEl=document.createElement("span"); cursorEl.className="stream-cursor";
  progressBubble = createProgressBubble();
  let stallTimer=null;
  function resetStallTimer() {
    clearTimeout(stallTimer);
    stallTimer=setTimeout(()=>{
      reader.cancel(); cursorEl.remove();
      if(progressBubble) progressBubble.innerHTML=`<span style="color:var(--danger)">Response timed out. Please try again.</span>`;
    }, STREAM_STALL_MS);
  }
  resetStallTimer();
  try {
    while (true) {
      const {done,value}=await reader.read(); if(done) break;
      resetStallTimer();
      buffer+=decoder.decode(value,{stream:true});
      const parts=buffer.split(/\n\n|\r\n\r\n/); buffer=parts.pop();
      for (const part of parts) {
        const trimmed=part.trim();
        if(!trimmed||trimmed.startsWith(":")) continue;
        const dataLine=trimmed.split("\n").find(l=>l.startsWith("data:"));
        if(!dataLine) continue;
        const raw=dataLine.replace(/^data:\s*/,"").trim();
        if(!raw) continue;
        if(raw.startsWith("SESSION:")) {
          session_id=raw.replace("SESSION:","").trim();
          window.session_id=session_id;
          if(sessionLabel) sessionLabel.textContent="session: "+session_id.slice(0,8)+"…";
          continue;
        }
        let event;
        try{event=JSON.parse(raw);}catch{console.warn("[SSE] unrecognised:",raw);continue;}
        if(event.type==="session"&&event.session_id) {
          session_id=event.session_id; window.session_id=event.session_id;
          if(sessionLabel) sessionLabel.textContent="session: "+session_id.slice(0,8)+"…";
          continue;
        }
        if(event.type==="end"||event.type==="error") {
          clearTimeout(stallTimer); cursorEl.remove();
          document.getElementById("thinking-row")?.removeAttribute("id");
          if(event.type==="error") {
            if(progressBubble) progressBubble.innerHTML=`<span style="color:var(--danger)">An error occurred. Please try again.</span>`;
          } else if(!tokenStarted) {
            if(progressBubble) progressBubble.innerHTML=`<span style="color:var(--text-sub)">No response.</span>`;
          } else if(textEl) {
            textEl.innerHTML=marked.parse(fullText);
            finalizeHighlighting(textEl);
            chatBox.scrollTop=chatBox.scrollHeight;
          }
          return;
        }
        if(event.type==="progress"&&event.node) {
          if(!tokenStarted&&!SKIP_NODES.has(event.node)) {
            addProgressStep(progressBubble, NODE_LABELS[event.node]||event.node.replace(/_/g," "));
          }
          continue;
        }
        if(event.type==="clarification") {
          clearTimeout(stallTimer); cursorEl.remove();
          showClarificationWidget(event.question, event.options, window.session_id||session_id);
          return;
        }
        if(event.type==="chunk"&&event.content) {
          if(!tokenStarted){tokenStarted=true;textEl=convertToResponseBubble(progressBubble);}
          fullText+=event.content;
          renderChunk(textEl,fullText,cursorEl);
          continue;
        }
      }
    }
  } finally { clearTimeout(stallTimer); }
}

// ── Init ──────────────────────────────────────────────────────────────────────
window.addEventListener("load", () => {
  refreshSendBtn();
  msgInput.focus();
  const attachBtn=document.querySelector(".attach-btn");
  if(attachBtn&&!attachBtn.getAttribute("aria-label"))
    attachBtn.setAttribute("aria-label","Attach files");
});