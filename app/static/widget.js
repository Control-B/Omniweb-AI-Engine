(function () {
  "use strict";

  var SCRIPT = document.currentScript;
  if (!SCRIPT) {
    return;
  }

  var publicWidgetId = SCRIPT.getAttribute("data-tenant-id") || SCRIPT.dataset.tenantId || "";
  if (!publicWidgetId) {
    console.warn("[Omniweb] Missing data-tenant-id on widget script.");
    return;
  }

  var scriptUrl;
  try {
    scriptUrl = new URL(SCRIPT.src, window.location.href);
  } catch (error) {
    console.warn("[Omniweb] Invalid widget script URL.");
    return;
  }

  var apiBase = scriptUrl.origin;
  var storageKey = "omniweb_session_id";

  function uuid() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID();
    }
    return "ow_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
  }

  function getSessionId() {
    try {
      var existing = window.localStorage.getItem(storageKey);
      if (existing) return existing;
      var created = uuid();
      window.localStorage.setItem(storageKey, created);
      return created;
    } catch (error) {
      return uuid();
    }
  }

  function request(path, payload) {
    return fetch(apiBase + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(function (response) {
      return response.json().catch(function () {
        return {};
      }).then(function (data) {
        if (!response.ok) {
          throw new Error((data && data.error && data.error.message) || "Request failed");
        }
        return data;
      });
    });
  }

  function track(eventType, metadata) {
    return request("/api/widget/events", {
      publicWidgetId: publicWidgetId,
      sessionId: getSessionId(),
      eventType: eventType,
      domain: window.location.hostname,
      pageUrl: window.location.href,
      metadata: metadata || {},
    }).catch(function () {});
  }

  function installPing() {
    return request("/api/widget/install-ping", {
      publicWidgetId: publicWidgetId,
      domain: window.location.hostname,
      pageUrl: window.location.href,
    }).catch(function () {});
  }

  request("/api/widget/handshake", {
    publicWidgetId: publicWidgetId,
    domain: window.location.hostname,
    pageUrl: window.location.href,
    referrer: document.referrer || null,
  })
    .then(function (payload) {
      if (!payload || payload.success !== true || !payload.data) {
        console.warn("[Omniweb] Widget handshake blocked.");
        return;
      }

      var config = payload.data;
      var host = document.createElement("div");
      host.setAttribute("data-omniweb-widget-host", "true");
      document.body.appendChild(host);
      var root = host.attachShadow ? host.attachShadow({ mode: "open" }) : host;
      var sessionId = getSessionId();
      var isOpen = false;
      var voiceActive = false;

      var style = document.createElement("style");
      style.textContent = "\
        :host { all: initial; }\
        .omniweb-widget-root { position: fixed; z-index: 2147483647; bottom: 24px; font-family: Inter, Arial, sans-serif; color: #0f172a; }\
        .omniweb-widget-root.right { right: 24px; }\
        .omniweb-widget-root.left { left: 24px; }\
        .omniweb-widget-button { width: 60px; height: 60px; border: 0; border-radius: 9999px; background: var(--omniweb-color); color: #fff; cursor: pointer; box-shadow: 0 16px 35px rgba(15,23,42,.22); font-size: 24px; }\
        .omniweb-widget-panel { width: min(360px, calc(100vw - 32px)); max-height: min(560px, calc(100vh - 110px)); margin-top: 12px; border: 1px solid rgba(148,163,184,.24); border-radius: 24px; background: #fff; box-shadow: 0 24px 60px rgba(15,23,42,.18); overflow: hidden; display: none; }\
        .omniweb-widget-panel.open { display: flex; flex-direction: column; }\
        .omniweb-widget-header { padding: 16px 18px; background: linear-gradient(135deg, var(--omniweb-color), #1d4ed8); color: #fff; }\
        .omniweb-widget-header-title { font-size: 15px; font-weight: 700; margin: 0; }\
        .omniweb-widget-header-sub { font-size: 12px; opacity: .9; margin-top: 4px; }\
        .omniweb-widget-messages { padding: 16px; background: #f8fafc; display: flex; flex-direction: column; gap: 10px; overflow-y: auto; min-height: 220px; }\
        .omniweb-widget-message { max-width: 85%; border-radius: 18px; padding: 10px 12px; font-size: 14px; line-height: 1.45; white-space: pre-wrap; }\
        .omniweb-widget-message.assistant { background: #fff; color: #0f172a; border: 1px solid rgba(226,232,240,.9); }\
        .omniweb-widget-message.user { align-self: flex-end; background: var(--omniweb-color); color: #fff; }\
        .omniweb-widget-compose { padding: 14px; border-top: 1px solid rgba(226,232,240,.95); background: #fff; display: flex; flex-direction: column; gap: 10px; }\
        .omniweb-widget-input-row { display: flex; gap: 8px; }\
        .omniweb-widget-input { flex: 1; min-width: 0; border-radius: 14px; border: 1px solid #cbd5e1; padding: 12px 14px; font-size: 14px; outline: none; }\
        .omniweb-widget-send, .omniweb-widget-voice { border: 0; border-radius: 14px; padding: 0 14px; cursor: pointer; font-weight: 600; }\
        .omniweb-widget-send { background: var(--omniweb-color); color: #fff; }\
        .omniweb-widget-voice { align-self: flex-start; background: #eff6ff; color: #1d4ed8; padding: 10px 14px; }\
        .omniweb-widget-note { font-size: 11px; color: #64748b; }\
      ";
      root.appendChild(style);

      var wrapper = document.createElement("div");
      wrapper.className = "omniweb-widget-root " + (config.position === "bottom-left" ? "left" : "right");
      wrapper.style.setProperty("--omniweb-color", config.primaryColor || "#2563eb");

      var button = document.createElement("button");
      button.type = "button";
      button.className = "omniweb-widget-button";
      button.setAttribute("aria-label", "Open Omniweb chat widget");
      button.textContent = "✦";

      var panel = document.createElement("div");
      panel.className = "omniweb-widget-panel";

      var header = document.createElement("div");
      header.className = "omniweb-widget-header";
      header.innerHTML = '<div class="omniweb-widget-header-title"></div><div class="omniweb-widget-header-sub"></div>';
      header.querySelector(".omniweb-widget-header-title").textContent = config.businessName || "Omniweb";
      header.querySelector(".omniweb-widget-header-sub").textContent = config.agentMode ? String(config.agentMode).replace(/_/g, " ") : "AI assistant";

      var messages = document.createElement("div");
      messages.className = "omniweb-widget-messages";

      var compose = document.createElement("div");
      compose.className = "omniweb-widget-compose";
      var inputRow = document.createElement("div");
      inputRow.className = "omniweb-widget-input-row";

      var input = document.createElement("input");
      input.className = "omniweb-widget-input";
      input.type = "text";
      input.placeholder = "Type your message…";

      var send = document.createElement("button");
      send.type = "button";
      send.className = "omniweb-widget-send";
      send.textContent = "Send";

      inputRow.appendChild(input);
      inputRow.appendChild(send);

      var voice = null;
      if (config.voiceEnabled) {
        voice = document.createElement("button");
        voice.type = "button";
        voice.className = "omniweb-widget-voice";
        voice.textContent = "Start voice";
      }

      var note = document.createElement("div");
      note.className = "omniweb-widget-note";
      note.textContent = "Managed remotely from your Omniweb dashboard.";

      compose.appendChild(inputRow);
      if (voice) compose.appendChild(voice);
      compose.appendChild(note);

      panel.appendChild(header);
      panel.appendChild(messages);
      panel.appendChild(compose);
      wrapper.appendChild(button);
      wrapper.appendChild(panel);
      root.appendChild(wrapper);

      function addMessage(role, content) {
        var bubble = document.createElement("div");
        bubble.className = "omniweb-widget-message " + role;
        bubble.textContent = content;
        messages.appendChild(bubble);
        messages.scrollTop = messages.scrollHeight;
      }

      function openPanel() {
        if (isOpen) return;
        isOpen = true;
        panel.classList.add("open");
        track("widget_opened", {});
      }

      function closePanel() {
        isOpen = false;
        panel.classList.remove("open");
      }

      function sendMessage() {
        var text = (input.value || "").trim();
        if (!text) return;
        addMessage("user", text);
        input.value = "";
        request("/api/widget/chat", {
          publicWidgetId: publicWidgetId,
          sessionId: sessionId,
          message: text,
          domain: window.location.hostname,
          pageUrl: window.location.href,
        })
          .then(function (response) {
            var content = response && response.data && response.data.message && response.data.message.content;
            if (content) addMessage("assistant", content);
          })
          .catch(function () {
            addMessage("assistant", "Sorry — something went wrong. Please try again.");
          });
      }

      button.addEventListener("click", function () {
        if (isOpen) {
          closePanel();
        } else {
          openPanel();
        }
      });

      send.addEventListener("click", sendMessage);
      input.addEventListener("keydown", function (event) {
        if (event.key === "Enter") sendMessage();
      });

      if (voice) {
        voice.addEventListener("click", function () {
          voiceActive = !voiceActive;
          voice.textContent = voiceActive ? "End voice" : "Start voice";
          track(voiceActive ? "voice_started" : "voice_ended", {});
        });
      }

      addMessage("assistant", config.welcomeMessage || "Welcome! How can I help you today?");
      installPing();
      track("widget_loaded", { path: window.location.pathname });
    })
    .catch(function () {
      console.warn("[Omniweb] Widget handshake blocked.");
    });
})();