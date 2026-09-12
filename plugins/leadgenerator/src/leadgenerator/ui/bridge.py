"""Small self-contained MCP Apps bridge shared by Lead Generator interfaces."""

from __future__ import annotations

MCP_APP_BRIDGE_JS = r"""
(() => {
  const pending = new Map();
  let nextId = 1;
  let connected = false;
  let hostContext = null;
  let hostCapabilities = null;
  let toolResult = null;
  let toolError = false;
  let resizeObserver = null;
  const states = new Map();

  const send = message => window.parent.postMessage(message, "*");
  const notify = (method, params) => {
    const message = {jsonrpc: "2.0", method};
    if(params !== undefined) message.params = params;
    send(message);
  };
  const request = (method, params, timeoutMs = 10000) => new Promise((resolve, reject) => {
    const id = nextId++;
    const timeout = window.setTimeout(() => {
      pending.delete(id);
      reject(Object.assign(new Error(`MCP Apps request timed out: ${method}`), {code:"TIMEOUT"}));
    }, timeoutMs);
    pending.set(id, {resolve, reject, timeout});
    send({jsonrpc: "2.0", id, method, params});
  });
  const emit = (name, detail) => window.dispatchEvent(
    new CustomEvent(`leadgenerator:${name}`, {detail})
  );
  const showFallback = (text, reason, retry) => {
    let panel = document.getElementById("leadgenerator-host-fallback");
    if(!panel) {
      panel = document.createElement("aside");
      panel.id = "leadgenerator-host-fallback";
      panel.setAttribute("role", "status");
      panel.style.cssText = "position:fixed;bottom:12px;left:12px;right:12px;z-index:9999;padding:16px;background:var(--surface,#fff);color:var(--ink,#17211f);border:1px solid #888;border-radius:12px;box-shadow:0 4px 24px #0003";
      document.body.append(panel);
    }
    panel.replaceChildren();
    const label = document.createElement("p");
    label.textContent = reason || "Cette action n’a pas été transmise. Copiez cette demande dans le chat :";
    const input = document.createElement("textarea");
    input.readOnly = true; input.value = text; input.style.width = "100%";
    input.setAttribute("aria-label", "Demande à reprendre dans le chat");
    const close = document.createElement("button");
    close.textContent = "Fermer"; close.onclick = () => panel.remove();
    panel.append(label);
    if(retry) {
      const button = document.createElement("button");
      button.textContent = "Réessayer la transmission";
      button.onclick = () => { button.disabled = true; void retry(); };
      panel.append(button);
      const details = document.createElement("details");
      const summary = document.createElement("summary");
      summary.textContent = "Reprendre manuellement dans le chat";
      details.append(summary, input); panel.append(details);
    } else if(text) panel.append(input);
    panel.append(close);
  };
  const showStatus = text => showFallback("", text);
  const stateKey = (surface, payload) => `leadgenerator:${surface}:${payload?.management_only ? "manager" : "leads"}:${payload?.objective_id || payload?.active_objective_id || "unscoped"}`;
  const extractPayload = (value, kind) => {
    if(!value || value.isError) return null;
    const candidates = [value, value.structuredContent, value.structured_content, value.output];
    for(const block of Array.isArray(value.content) ? value.content : []) {
      if(block.type !== "text" || typeof block.text !== "string") continue;
      try { candidates.push(JSON.parse(block.text)); } catch {}
    }
    return candidates.find(item => item?.kind === kind && Array.isArray(item.leads)) || null;
  };
  const reportSize = () => {
    if(!connected || !document.body) return;
    const height = Math.ceil(document.body.getBoundingClientRect().height);
    if(height > 0 && height !== reportSize.lastHeight) {
      reportSize.lastHeight = height;
      notify("ui/notifications/size-changed", {height});
    }
  };
  const observeSize = () => {
    if(!document.body || resizeObserver || typeof ResizeObserver !== "function") return;
    resizeObserver = new ResizeObserver(reportSize);
    resizeObserver.observe(document.body); reportSize();
  };
  document.addEventListener("DOMContentLoaded", observeSize, {once:true});
  document.addEventListener("click", event => {
    const link = event.target.closest?.("a[href]");
    if(!link || event.defaultPrevented || !connected || !hostCapabilities?.openLinks || link.hasAttribute("download")) return;
    const url = new URL(link.href, document.baseURI);
    if(!["https:", "http:"].includes(url.protocol)) return;
    event.preventDefault();
    void request("ui/open-link", {url:url.href}).then(result => {
      if(result?.isError) throw new Error("Link rejected");
    }).catch(() => showFallback(url.href, "Le lien n’a pas pu être ouvert. Copiez cette adresse dans votre navigateur :"));
  });

  window.addEventListener("message", event => {
    if(event.source !== window.parent) return;
    const message = event.data;
    if(!message || message.jsonrpc !== "2.0") return;

    if(message.id !== undefined && (message.result !== undefined || message.error)) {
      const waiter = pending.get(message.id);
      if(!waiter) return;
      pending.delete(message.id);
      window.clearTimeout(waiter.timeout);
      if(message.error) waiter.reject(Object.assign(new Error(message.error.message || "MCP Apps error"), {code:message.error.code}));
      else waiter.resolve(message.result);
      return;
    }

    if(message.method === "ui/notifications/tool-result") {
      toolResult = message.params || null;
      toolError = Boolean(toolResult?.isError);
      if(toolError) { emit("tool-error", toolResult); return; }
      emit("tool-result", toolResult);
      return;
    }
    if(message.method === "ui/notifications/host-context-changed") {
      hostContext = {...(hostContext || {}), ...(message.params || {})};
      emit("host-context", hostContext);
      return;
    }
    if(message.method === "ui/resource-teardown" && message.id !== undefined) {
      connected = false;
      resizeObserver?.disconnect();
      for(const waiter of pending.values()) {
        window.clearTimeout(waiter.timeout);
        waiter.reject(new Error("MCP Apps resource closed"));
      }
      pending.clear();
      send({jsonrpc: "2.0", id: message.id, result: {}});
    }
  });

  const bridge = {
    get connected() { return connected; },
    get hostContext() { return hostContext; },
    get hostCapabilities() { return hostCapabilities; },
    get toolResult() { return toolResult; },
    get toolError() { return toolError; },
    extractPayload,
    async sendMessage(text) {
      try {
        if(!connected || (hostCapabilities && !hostCapabilities.message)) throw Object.assign(new Error("Messaging unavailable"), {code:"UNAVAILABLE"});
        // Send synchronously from the user's click; never manufacture activation,
        // delay a request to evade host checks, or retry without a new user action.
        const result = await request("ui/message", {role:"user", content:[{type:"text", text}]});
        if(result?.isError) {
          showFallback(text, "L’application n’a pas accepté cette action. Réessayez avec le bouton ci-dessous.", () => bridge.sendMessage(text));
          return result;
        }
        showStatus("Demande transmise à l’application. Si elle apparaît dans la zone de saisie, cliquez sur Envoyer pour la lancer.");
        return result;
      } catch(error) {
        const reason = error.code === "TIMEOUT"
          ? "L’application n’a pas confirmé la transmission. Vérifiez le chat avant de renvoyer cette demande pour éviter un doublon :"
          : error.code === "UNAVAILABLE"
            ? "La transmission au chat n’est pas disponible dans cette session. Copiez cette demande dans le chat :"
            : "L’application a signalé une erreur de transmission. Vérifiez le chat avant de reprendre cette demande :";
        showFallback(text, reason);
        return {isError:true};
      }
    },
    async requestDisplayMode(mode) {
      const modes = hostContext?.availableDisplayModes;
      if(Array.isArray(modes) && !modes.includes(mode)) throw new Error("Display mode unavailable");
      const result = await request("ui/request-display-mode", {mode});
      if(!["inline", "fullscreen", "pip"].includes(result?.mode)) throw new Error("Invalid display mode response");
      hostContext = {...(hostContext || {}), displayMode:result.mode};
      emit("host-context", hostContext);
      if(result.mode !== mode) throw new Error("Display mode declined");
      return result;
    },
    updateDisplayModeControls(buttons) {
      const modes = hostContext?.availableDisplayModes;
      const unsupported = connected && typeof window.openai?.requestDisplayMode !== "function"
        && Array.isArray(modes) && !modes.includes("fullscreen")
        && document.documentElement.dataset.displayMode !== "fullscreen";
      for(const button of buttons) {
        button.disabled = unsupported;
        if(unsupported) {
          const label = "Plein écran indisponible dans cette interface de l’application";
          button.title = label; button.setAttribute("aria-label", label);
        }
      }
    },
    loadState(surface, payload) {
      if(window.openai?.widgetState) return window.openai.widgetState;
      const key = stateKey(surface, payload);
      try { return JSON.parse(window.sessionStorage.getItem(key)) || states.get(key) || {}; }
      catch { return states.get(key) || {}; }
    },
    saveState(surface, payload, state) {
      if(typeof window.openai?.setWidgetState === "function") {
        Promise.resolve(window.openai.setWidgetState(state)).catch(() => undefined);
        return;
      }
      const key = stateKey(surface, payload);
      states.set(key, state);
      // Only transient view/selection state, never leads, credentials or geolocation.
      try { window.sessionStorage.setItem(key, JSON.stringify(state)); } catch {}
    },
    showFallback,
    showStatus,
    request,
    notify,
  };
  window.leadGeneratorMcpApp = bridge;

  void (async () => {
    try {
      const result = await request("ui/initialize", {
        appInfo: {name: "Lead Generator", version: "0.4.0"},
        appCapabilities: {availableDisplayModes: ["inline", "fullscreen"]},
        protocolVersion: "2026-01-26",
      });
      hostContext = result?.hostContext || {};
      hostCapabilities = result?.hostCapabilities || null;
      connected = true;
      emit("host-context", hostContext);
      notify("ui/notifications/initialized");
      observeSize(); reportSize();
    } catch(error) {
      // Older OpenAI hosts expose window.openai instead of the MCP Apps channel.
      console.debug("Lead Generator MCP Apps handshake unavailable", error);
    }
  })();
})();
""".strip()
