/**
 * Omniweb SaaS widget — loads config from the engine (no private prompts in JS).
 * Usage:
 * <script src="https://YOUR_ENGINE/widget.js" data-widget-key="..." async></script>
 */
(function () {
  var script = document.currentScript;
  if (!script) return;
  var key = script.getAttribute("data-widget-key");
  if (!key) return;

  var srcUrl = script.src ? new URL(script.src) : null;
  var apiOrigin = script.getAttribute("data-api-base") || (srcUrl ? srcUrl.origin : "");
  if (!apiOrigin) return;

  var z = 2147483640;
  var root = document.createElement("div");
  root.setAttribute("data-omniweb-widget", "1");
  document.body.appendChild(root);

  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        e.setAttribute(k, attrs[k]);
      });
    }
    if (text) e.textContent = text;
    return e;
  }

  var panel = el("div", {
    style:
      "position:fixed;font-family:system-ui,-apple-system,sans-serif;font-size:14px;box-sizing:border-box;" +
      "z-index:" +
      z +
      ";",
  });
  var pos = "bottom-right";
  var theme = "#6366f1";

  function place() {
    panel.style.bottom = "16px";
    panel.style[pos.indexOf("left") >= 0 ? "left" : "right"] = "16px";
    panel.style[pos.indexOf("left") >= 0 ? "right" : "left"] = "auto";
  }

  var card = el("div", {
    style:
      "width:min(100vw - 32px,380px);max-height:min(70vh,520px);display:none;flex-direction:column;" +
      "background:#0f0f12;border:1px solid rgba(255,255,255,.12);border-radius:16px;" +
      "box-shadow:0 16px 48px rgba(0,0,0,.45);overflow:hidden;margin-bottom:12px;",
  });

  var head = el("div", {
    style:
      "padding:12px 14px;font-weight:600;color:#fff;display:flex;align-items:center;justify-content:space-between;" +
      "border-bottom:1px solid rgba(255,255,255,.08);",
  });
  var title = el("span", {}, "Assistant");
  var closeBtn = el(
    "button",
    {
      type: "button",
      style:
        "background:transparent;border:none;color:#aaa;cursor:pointer;font-size:18px;line-height:1;padding:4px;",
    },
    "×"
  );
  head.appendChild(title);
  head.appendChild(closeBtn);

  var msgs = el("div", {
    style: "flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:10px;min-height:200px;",
  });

  var inputRow = el("div", {
    style: "display:flex;gap:8px;padding:10px;border-top:1px solid rgba(255,255,255,.08);",
  });
  var input = el("input", {
    type: "text",
    placeholder: "Message…",
    style:
      "flex:1;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:10px;" +
      "padding:10px 12px;color:#fff;outline:none;",
  });
  var send = el(
    "button",
    {
      type: "button",
      style:
        "background:" +
        theme +
        ";color:#fff;border:none;border-radius:10px;padding:0 14px;font-weight:600;cursor:pointer;",
    },
    "Send"
  );
  inputRow.appendChild(input);
  inputRow.appendChild(send);

  card.appendChild(head);
  card.appendChild(msgs);
  card.appendChild(inputRow);

  var launcher = el(
    "button",
    {
      type: "button",
      style:
        "width:56px;height:56px;border-radius:50%;border:none;cursor:pointer;color:#fff;font-size:22px;" +
        "box-shadow:0 8px 24px rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center;",
    },
    "💬"
  );

  panel.appendChild(card);
  panel.appendChild(launcher);
  root.appendChild(panel);

  var open = false;
  var history = [];

  function appendBubble(role, text) {
    var wrap = el("div", {
      style:
        "align-self:" +
        (role === "user" ? "flex-end" : "flex-start") +
        ";max-width:85%;padding:10px 12px;border-radius:12px;" +
        (role === "user"
          ? "background:" + theme + ";color:#fff;"
          : "background:rgba(255,255,255,.08);color:#eee;"),
    });
    wrap.textContent = text;
    msgs.appendChild(wrap);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function setLauncherColor(c) {
    theme = c || theme;
    launcher.style.background = theme;
    send.style.background = theme;
  }

  function showInactive(msg) {
    launcher.textContent = "!";
    launcher.style.background = "#6b7280";
    launcher.onclick = function () {
      alert(msg || "This assistant is not available.");
    };
  }

  function toggle() {
    open = !open;
    card.style.display = open ? "flex" : "none";
  }

  closeBtn.onclick = function () {
    open = false;
    card.style.display = "none";
  };
  launcher.onclick = function () {
    toggle();
  };

  function sendMessage() {
    var t = (input.value || "").trim();
    if (!t) return;
    input.value = "";
    appendBubble("user", t);
    history.push({ role: "user", content: t });
    send.disabled = true;
    fetch(apiOrigin + "/api/public/widget/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ widget_key: key, messages: history }),
    })
      .then(function (r) {
        if (!r.ok) throw new Error("chat failed");
        return r.json();
      })
      .then(function (data) {
        var reply = data.content || "";
        history.push({ role: "assistant", content: reply });
        appendBubble("assistant", reply);
      })
      .catch(function () {
        appendBubble("assistant", "Sorry — something went wrong. Please try again.");
      })
      .finally(function () {
        send.disabled = false;
      });
  }

  send.onclick = sendMessage;
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter") sendMessage();
  });

  fetch(apiOrigin + "/api/public/widget/bootstrap?widget_key=" + encodeURIComponent(key))
    .then(function (r) {
      if (!r.ok) throw new Error("bootstrap failed");
      return r.json();
    })
    .then(function (data) {
      if (!data.active) {
        showInactive(data.message || "Assistant unavailable.");
        return;
      }
      title.textContent = data.agent_name || "Assistant";
      setLauncherColor(data.theme_color);
      pos = data.position || pos;
      place();
      launcher.textContent = "💬";
      if (data.welcome_message) {
        appendBubble("assistant", data.welcome_message);
        history.push({ role: "assistant", content: data.welcome_message });
      }
    })
    .catch(function () {
      showInactive("Could not load the assistant.");
    });
})();
