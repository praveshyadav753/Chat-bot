// app/static/session_manager.js
//
// Manages chat sessions — create, list, switch, rename, delete.
// Handles per-session document file tracking and chat history loading.
// Exposes window.sessionMgr for use by scripts.js and chat.html.

(function () {
  "use strict";

  // ── State ──────────────────────────────────────────────────────────────────
  let sessions      = [];   // [{session_id, title, created_at, updated_at}]
  let activeSession = null;

  // ── Per-session file store ─────────────────────────────────────────────────
  // Key: session_id → Value: uploadedFiles array for that session
  // This prevents docs from session A leaking into session B
  const sessionFiles = {};   // { [session_id]: [...uploadedFiles entries] }

  // ── Helpers ────────────────────────────────────────────────────────────────
  function esc(t) {
    return String(t).replace(/[&<>"']/g, m =>
      ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"})[m]);
  }
  function formatTime(iso) {
    if (!iso) return "";
    const d = new Date(iso), now = new Date(), diff = now - d;
    if (diff < 60_000)    return "just now";
    if (diff < 3_600_000) return Math.floor(diff / 60_000) + "m ago";
    if (diff < 86_400_000)return Math.floor(diff / 3_600_000) + "h ago";
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }
  function sessionIcon(title) {
    if (!title || title === "New Chat") return "💬";
    const t = title.toLowerCase();
    if (t.includes("news") || t.includes("latest"))  return "📰";
    if (t.includes("code") || t.includes("script"))  return "💻";
    if (t.includes("doc")  || t.includes("pdf"))     return "📄";
    if (t.includes("search")|| t.includes("find"))   return "🔍";
    if (t.includes("summar"))                         return "📝";
    if (t.includes("analys"))                         return "📊";
    return "💬";
  }

  // ── DOM helpers ────────────────────────────────────────────────────────────
  function setTopbar(title, sessionId) {
    const t = document.getElementById("topbar-title");
    const s = document.getElementById("session-label");
    if (t) t.textContent = title || "New Chat";
    if (s) s.textContent = sessionId
      ? "session: " + sessionId.slice(0, 10) + "…"
      : "no session";
  }

  function setChatBox(html) {
    const cb = document.getElementById("chat-box");
    if (cb) cb.innerHTML = html;
    window.placeholderHidden = false;
  }

  // ── API helpers ────────────────────────────────────────────────────────────
  async function apiGet(url) {
    const r = await fetch(url, { credentials: "include" });
    if (!r.ok) throw new Error(`GET ${url} → ${r.status}`);
    return r.json();
  }
  async function apiPost(url, body = {}) {
    const r = await fetch(url, {
      method: "POST", credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`POST ${url} → ${r.status}`);
    return r.json();
  }
  async function apiPatch(url, params = {}) {
    const qs = new URLSearchParams(params).toString();
    const r  = await fetch(`${url}?${qs}`, { method: "PATCH", credentials: "include" });
    if (!r.ok) throw new Error(`PATCH ${url} → ${r.status}`);
    return r.json();
  }
  async function apiDelete(url) {
    const r = await fetch(url, { method: "DELETE", credentials: "include" });
    if (!r.ok) throw new Error(`DELETE ${url} → ${r.status}`);
    return r.json();
  }

  // ── Per-session file management ────────────────────────────────────────────

  // Get the files array for a given session (creates if missing)
  function getSessionFiles(sessionId) {
    if (!sessionFiles[sessionId]) sessionFiles[sessionId] = [];
    return sessionFiles[sessionId];
  }

  // Restore the active session's files into scripts.js uploadedFiles
  // Also re-renders chips for any files that were uploading/processing
  function restoreSessionFiles(sessionId) {
    const files = getSessionFiles(sessionId);

    // Tell scripts.js to use this session's file array
    // scripts.js exposes window.setUploadedFiles for this
    if (window.setUploadedFiles) {
      window.setUploadedFiles(files, sessionId);
    }
  }

  // Save current session files before switching away
  function saveCurrentSessionFiles() {
    if (!activeSession) return;
    const sid = activeSession.session_id;
    // scripts.js exposes window.getUploadedFiles
    if (window.getUploadedFiles) {
      sessionFiles[sid] = window.getUploadedFiles();
    }
  }

  // ── Chat history loading ───────────────────────────────────────────────────

  async function loadChatHistory(sessionId) {
    try {
      const data = await apiGet(`/api/sessions/${sessionId}/messages`);
      const messages = data.messages || [];

      if (!messages.length) return;  // no history — placeholder stays

      const chatBox = document.getElementById("chat-box");
      if (!chatBox) return;

      // Clear placeholder
      chatBox.innerHTML = "";
      window.placeholderHidden = true;

      // Render each message
      messages.forEach(msg => {
        if (msg.role === "user") {
          if (window.appendUserMessage) window.appendUserMessage(msg.content, null);
        } else if (msg.role === "assistant") {
          _appendBotMessage(msg.content);
        }
      });

      chatBox.scrollTop = chatBox.scrollHeight;
    } catch (err) {
      console.warn("[session] could not load history:", err);
      // Non-fatal — just show placeholder
    }
  }

  function _appendBotMessage(content) {
    const chatBox = document.getElementById("chat-box");
    if (!chatBox) return;

    const row = document.createElement("div");
    row.className = "msg-row bot";

    const label = document.createElement("div");
    label.className = "role-label";
    label.textContent = "Assistant";

    const bubble = document.createElement("div");
    bubble.className = "bubble bot";

    // Render markdown — marked and hljs are already loaded globally
    bubble.innerHTML = marked.parse(content);
    bubble.querySelectorAll("pre code").forEach(block => {
      if (window.hljs) hljs.highlightElement(block);
    });

    row.appendChild(label);
    row.appendChild(bubble);
    chatBox.appendChild(row);
  }

  // ── Render sidebar ─────────────────────────────────────────────────────────
  function render() {
    const list  = document.getElementById("sessions-list");
    const empty = document.getElementById("sessions-empty");
    const count = document.getElementById("sessions-count");
    if (!list) return;

    if (count) count.textContent =
      sessions.length + " session" + (sessions.length !== 1 ? "s" : "");

    list.querySelectorAll(".session-item").forEach(el => el.remove());

    if (!sessions.length) {
      if (empty) empty.style.display = "block";
      return;
    }
    if (empty) empty.style.display = "none";

    sessions.forEach(s => {
      const el = document.createElement("div");
      el.className = "session-item" +
        (s.session_id === activeSession?.session_id ? " active" : "");
      el.setAttribute("role", "listitem");
      el.innerHTML = `
        <div class="session-icon">${sessionIcon(s.title)}</div>
        <div class="session-info">
          <div class="session-title" id="stitle-${s.session_id}">
            ${esc(s.title || "New Chat")}
          </div>
          <div class="session-meta">${formatTime(s.updated_at || s.created_at)}</div>
        </div>
        <button class="session-delete" title="Delete" aria-label="Delete session">✕</button>
      `;
      el.addEventListener("click", e => {
        if (e.target.classList.contains("session-delete")) return;
        switchTo(s.session_id);
      });
      el.querySelector(".session-title").addEventListener("dblclick", e => {
        e.stopPropagation(); startRename(s.session_id);
      });
      el.querySelector(".session-delete").addEventListener("click", e => {
        e.stopPropagation(); remove(s.session_id);
      });
      list.appendChild(el);
    });
  }

  // ── Session actions ────────────────────────────────────────────────────────

  async function init() {
    try {
      const data = await apiGet("/api/sessions");
      sessions = data.sessions || [];
      if (sessions.length > 0) {
        await switchTo(sessions[0].session_id);
      } else {
        await newChat();
      }
    } catch (err) {
      console.error("[sessions] init failed:", err);
      await newChat();
    }
  }

  async function newChat() {
    try {
      // Save current session's files before leaving
      saveCurrentSessionFiles();

      const s = await apiPost("/api/sessions");
      sessions.unshift(s);
      activeSession     = s;
      window.session_id = s.session_id;

      // New session starts with empty files
      sessionFiles[s.session_id] = [];
      restoreSessionFiles(s.session_id);

      setTopbar("New Chat", null);
      setChatBox(`
        <div class="chat-placeholder" id="chat-placeholder">
          <div class="ph-glyph">💬</div>
          <div class="ph-title">Start a conversation</div>
          <div class="ph-sub">or attach documents to analyse</div>
        </div>
      `);
      render();
      document.getElementById("message")?.focus();
    } catch (err) {
      console.error("[sessions] newChat failed:", err);
    }
  }

  async function switchTo(sessionId) {
    if (activeSession?.session_id === sessionId) return;  // already active

    // Save current session's files before switching
    saveCurrentSessionFiles();

    const s = sessions.find(x => x.session_id === sessionId);
    if (!s) return;

    activeSession     = s;
    window.session_id = s.session_id;

    setTopbar(s.title, s.session_id);

    // Show placeholder first, then load history
    setChatBox(`
      <div class="chat-placeholder" id="chat-placeholder">
        <div class="ph-glyph">💬</div>
        <div class="ph-title">${esc(s.title || "New Chat")}</div>
        <div class="ph-sub">Loading conversation…</div>
      </div>
    `);

    render();

    // Restore this session's uploaded file chips
    restoreSessionFiles(s.session_id);

    // Load chat history from backend
    await loadChatHistory(s.session_id);
  }

  async function remove(sessionId) {
    try {
      await apiDelete(`/api/sessions/${sessionId}`);
      sessions = sessions.filter(s => s.session_id !== sessionId);
      delete sessionFiles[sessionId];  // clean up file store

      if (activeSession?.session_id === sessionId) {
        if (sessions.length > 0) await switchTo(sessions[0].session_id);
        else await newChat();
      } else {
        render();
      }
    } catch (err) {
      console.error("[sessions] delete failed:", err);
    }
  }

  function startRename(sessionId) {
    const titleEl = document.getElementById("stitle-" + sessionId);
    if (!titleEl) return;
    const s       = sessions.find(x => x.session_id === sessionId);
    const current = s?.title || "New Chat";
    const input   = document.createElement("input");
    input.className = "session-rename";
    input.value = current;
    titleEl.replaceWith(input);
    input.focus(); input.select();
    const commit = async () => {
      const val = input.value.trim() || "New Chat";
      if (s) s.title = val;
      await apiPatch(`/api/sessions/${sessionId}`, { title: val }).catch(console.error);
      if (activeSession?.session_id === sessionId) {
        document.getElementById("topbar-title").textContent = val;
      }
      render();
    };
    input.addEventListener("blur", commit);
    input.addEventListener("keydown", e => {
      if (e.key === "Enter")  { e.preventDefault(); input.blur(); }
      if (e.key === "Escape") { input.value = current; input.blur(); }
    });
  }

  async function onMessageSent(message) {
    if (!activeSession) return;
    activeSession.updated_at = new Date().toISOString();

    // Auto-title on first message
    if (activeSession.title === "New Chat") {
      const title = message.length > 42 ? message.slice(0, 42) + "…" : message;
      activeSession.title = title;
      document.getElementById("topbar-title").textContent = title;
      await apiPatch(`/api/sessions/${activeSession.session_id}`, { title }).catch(console.error);
    }
    render();
  }

  // ── Expose public API ──────────────────────────────────────────────────────
  window.sessionMgr = {
    init,
    newChat,
    switchTo,
    remove,
    startRename,
    onMessageSent,
    getSessionFiles,     // used by scripts.js SSE handler
  };

  // Hook called by scripts.js before each message fetch
  window._onMessageSent = (message) => window.sessionMgr.onMessageSent(message);

})();