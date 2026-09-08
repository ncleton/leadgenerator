"""Small self-contained MCP Apps bridge shared by Lead Studio interfaces."""

from __future__ import annotations

MCP_APP_BRIDGE_JS = r"""
(() => {
  const pending = new Map();
  let nextId = 1;
  let connected = false;
  let hostContext = null;
  let toolResult = null;

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
      reject(new Error(`MCP Apps request timed out: ${method}`));
    }, timeoutMs);
    pending.set(id, {resolve, reject, timeout});
    send({jsonrpc: "2.0", id, method, params});
  });
  const emit = (name, detail) => window.dispatchEvent(
    new CustomEvent(`lead-studio:${name}`, {detail})
  );

  window.addEventListener("message", event => {
    if(event.source !== window.parent) return;
    const message = event.data;
    if(!message || message.jsonrpc !== "2.0") return;

    if(message.id !== undefined && (message.result !== undefined || message.error)) {
      const waiter = pending.get(message.id);
      if(!waiter) return;
      pending.delete(message.id);
      window.clearTimeout(waiter.timeout);
      if(message.error) waiter.reject(new Error(message.error.message || "MCP Apps error"));
      else waiter.resolve(message.result);
      return;
    }

    if(message.method === "ui/notifications/tool-result") {
      toolResult = message.params || null;
      emit("tool-result", toolResult);
      return;
    }
    if(message.method === "ui/notifications/host-context-changed") {
      hostContext = {...(hostContext || {}), ...(message.params || {})};
      emit("host-context", hostContext);
      return;
    }
    if(message.method === "ui/resource-teardown" && message.id !== undefined) {
      send({jsonrpc: "2.0", id: message.id, result: {}});
    }
  });

  const bridge = {
    get connected() { return connected; },
    get hostContext() { return hostContext; },
    get toolResult() { return toolResult; },
    request,
    notify,
  };
  window.leadStudioMcpApp = bridge;

  void (async () => {
    try {
      const result = await request("ui/initialize", {
        appInfo: {name: "Lead Studio", version: "0.3.0"},
        appCapabilities: {availableDisplayModes: ["inline", "fullscreen"]},
        protocolVersion: "2026-01-26",
      });
      hostContext = result?.hostContext || {};
      emit("host-context", hostContext);
      notify("ui/notifications/initialized");
      connected = true;
    } catch(error) {
      // Older OpenAI hosts expose window.openai instead of the MCP Apps channel.
      console.debug("Lead Studio MCP Apps handshake unavailable", error);
    }
  })();
})();
""".strip()
