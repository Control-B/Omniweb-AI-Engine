(function () {
  "use strict";

  var SCRIPT = document.currentScript;
  if (!SCRIPT) return;

  var shop = SCRIPT.getAttribute("data-shop") || "";
  var engine = SCRIPT.getAttribute("data-engine") || "";
  if (!engine) {
    try {
      engine = new URL(SCRIPT.src, window.location.href).origin;
    } catch (error) {
      return;
    }
  }
  engine = engine.replace(/\/+$/, "");
  if (!shop || !engine) return;

  var sessionId = null;
  var publicToken = null;
  var endpoints = {};
  var history = [];

  function request(path, options) {
    options = options || {};
    var headers = options.headers || {};
    if (options.body) headers["Content-Type"] = "application/json";
    if (publicToken) headers.Authorization = "Bearer " + publicToken;
    return fetch(engine + path, {
      method: options.method || "GET",
      headers: headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
    }).then(function (response) {
      return response.json().catch(function () {
        return {};
      }).then(function (data) {
        if (!response.ok) throw new Error(data.detail || "Request failed");
        return data;
      });
    });
  }

  function storefrontContext() {
    return {
      shop_domain: shop,
      storefront_session_id: getStorefrontSessionId(),
      current_page_url: window.location.href,
      referrer: document.referrer || null,
      shopper_locale: document.documentElement.lang || navigator.language || "en",
      currency: window.Shopify && window.Shopify.currency ? window.Shopify.currency.active : undefined,
    };
  }

  function getStorefrontSessionId() {
    var key = "omniweb_shopify_session_id";
    try {
      var existing = window.localStorage.getItem(key);
      if (existing) return existing;
      var created = window.crypto && window.crypto.randomUUID
        ? window.crypto.randomUUID()
        : "ows_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
      window.localStorage.setItem(key, created);
      return created;
    } catch (error) {
      return "ows_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
    }
  }

  function el(tag, attrs, text) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (key) {
      node.setAttribute(key, attrs[key]);
    });
    if (text) node.textContent = text;
    return node;
  }

  function mountWidget(bootstrap) {
    var root = el("div", { "data-omniweb-shopify-widget": "true" });
    document.body.appendChild(root);

    var style = el("style", {});
    style.textContent = "\
      .ow-shopify-root{position:fixed;right:20px;bottom:20px;z-index:2147483647;font-family:system-ui,-apple-system,BlinkMacSystemFont,sans-serif;color:#111827}\
      .ow-shopify-panel{display:none;width:min(380px,calc(100vw - 32px));max-height:min(560px,calc(100vh - 110px));margin-bottom:12px;background:#fff;border:1px solid #e5e7eb;border-radius:18px;box-shadow:0 20px 55px rgba(15,23,42,.22);overflow:hidden}\
      .ow-shopify-panel.open{display:flex;flex-direction:column}\
      .ow-shopify-head{padding:14px 16px;background:#111827;color:#fff;font-weight:700}\
      .ow-shopify-messages{min-height:220px;overflow:auto;padding:14px;display:flex;flex-direction:column;gap:10px;background:#f9fafb}\
      .ow-shopify-msg{max-width:85%;padding:10px 12px;border-radius:14px;font-size:14px;line-height:1.4;white-space:pre-wrap}\
      .ow-shopify-msg.assistant{align-self:flex-start;background:#fff;border:1px solid #e5e7eb}\
      .ow-shopify-msg.user{align-self:flex-end;background:#2563eb;color:#fff}\
      .ow-shopify-form{display:flex;gap:8px;padding:12px;border-top:1px solid #e5e7eb}\
      .ow-shopify-input{flex:1;min-width:0;border:1px solid #d1d5db;border-radius:12px;padding:10px 12px;font-size:14px}\
      .ow-shopify-send{border:0;border-radius:12px;background:#2563eb;color:#fff;font-weight:700;padding:0 14px;cursor:pointer}\
      .ow-shopify-launcher{width:58px;height:58px;border:0;border-radius:999px;background:#2563eb;color:#fff;font-size:22px;box-shadow:0 12px 32px rgba(37,99,235,.35);cursor:pointer}\
    ";

    var shell = el("div", { class: "ow-shopify-root" });
    var panel = el("div", { class: "ow-shopify-panel" });
    var head = el("div", { class: "ow-shopify-head" }, "Shopping Assistant");
    var messages = el("div", { class: "ow-shopify-messages" });
    var form = el("form", { class: "ow-shopify-form" });
    var input = el("input", { class: "ow-shopify-input", type: "text", placeholder: "Ask a question..." });
    var send = el("button", { class: "ow-shopify-send", type: "submit" }, "Send");
    var launcher = el("button", { class: "ow-shopify-launcher", type: "button", "aria-label": "Open Omniweb assistant" }, "Chat");

    function addMessage(role, text) {
      var bubble = el("div", { class: "ow-shopify-msg " + role }, text);
      messages.appendChild(bubble);
      messages.scrollTop = messages.scrollHeight;
    }

    function ensureSession() {
      if (sessionId) return Promise.resolve(sessionId);
      return request(endpoints.start_session || "/api/shopify/public/sessions", {
        method: "POST",
        body: { context: storefrontContext() },
      }).then(function (data) {
        sessionId = data.session_id;
        if (data.welcome_message) addMessage("assistant", data.welcome_message);
        return sessionId;
      });
    }

    launcher.addEventListener("click", function () {
      panel.classList.toggle("open");
      ensureSession().catch(function () {});
    });

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var text = (input.value || "").trim();
      if (!text) return;
      input.value = "";
      addMessage("user", text);
      history.push({ role: "user", content: text });
      send.disabled = true;
      ensureSession()
        .then(function () {
          var path = (endpoints.send_message || "/api/shopify/public/sessions/{session_id}/reply").replace("{session_id}", sessionId);
          return request(path, {
            method: "POST",
            body: { message: text, context: storefrontContext(), history: history.slice(-20) },
          });
        })
        .then(function (data) {
          var reply = data.message || data.reply || data.content || "Thanks. How else can I help?";
          history.push({ role: "assistant", content: reply });
          addMessage("assistant", reply);
        })
        .catch(function () {
          addMessage("assistant", "Sorry, I could not answer right now. Please try again.");
        })
        .finally(function () {
          send.disabled = false;
        });
    });

    form.appendChild(input);
    form.appendChild(send);
    panel.appendChild(head);
    panel.appendChild(messages);
    panel.appendChild(form);
    shell.appendChild(panel);
    shell.appendChild(launcher);
    root.appendChild(style);
    root.appendChild(shell);

    if (bootstrap.greeting) {
      addMessage("assistant", bootstrap.greeting);
      history.push({ role: "assistant", content: bootstrap.greeting });
    }
  }

  request("/api/shopify/public/bootstrap?shop=" + encodeURIComponent(shop))
    .then(function (bootstrap) {
      if (!bootstrap || bootstrap.assistant_enabled === false) return;
      publicToken = bootstrap.public_token;
      endpoints = bootstrap.endpoints || {};
      mountWidget(bootstrap);
    })
    .catch(function () {});
})();
