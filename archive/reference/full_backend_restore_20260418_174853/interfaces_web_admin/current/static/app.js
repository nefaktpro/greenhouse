function ghToken() {
  return localStorage.getItem("gh_token") || "";
}

function ghHeaders(withAuth = true, extra = {}) {
  const headers = { ...extra };
  if (withAuth && ghToken()) headers["Authorization"] = "Bearer " + ghToken();
  return headers;
}

async function ghApi(url, opts = {}) {
  const method = opts.method || "GET";
  const body = opts.body;
  const withAuth = opts.auth !== false;
  const headers = ghHeaders(withAuth, opts.headers || {});

  const resp = await fetch(url, {
    method,
    headers,
    body,
    credentials: "same-origin",
  });

  let data = null;
  try {
    data = await resp.json();
  } catch (_) {
    data = { ok: false, error: "non_json_response", status: resp.status };
  }

  if (resp.status === 401 && !location.pathname.endsWith("/web/login")) {
    localStorage.removeItem("gh_token");
    window.location.href = "/web/login";
  }

  return { resp, data };
}

function requireAuth() {
  if (!ghToken()) {
    window.location.href = "/web/login";
    return false;
  }
  return true;
}

function pretty(id, value) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = JSON.stringify(value, null, 2);
}

async function logout() {
  try {
    await ghApi("/api/auth/logout", { method: "POST", auth: false });
  } catch (_) {}
  localStorage.removeItem("gh_token");
  window.location.href = "/web/login";
}

async function ghTryGetVariants(urls) {
  const tried = [];
  for (const url of urls) {
    tried.push(url);
    try {
      const { resp, data } = await ghApi(url, { method: "GET" });
      if (resp.ok) return { ok: true, source: url, data };
    } catch (_) {}
  }
  return { ok: false, error: "no_get_variant_worked", tried };
}

async function ghTryPostVariants(variants) {
  const tried = [];
  for (const item of variants) {
    tried.push(item.url);
    try {
      const headers = item.headers || { "Content-Type": "application/json" };
      const body = item.rawBody !== undefined ? item.rawBody : JSON.stringify(item.body || {});
      const { resp, data } = await ghApi(item.url, {
        method: "POST",
        body,
        headers
      });
      if (resp.ok) return { ok: true, source: item.url, data };
    } catch (_) {}
  }
  return { ok: false, error: "no_post_variant_worked", tried };
}

async function ghLoadCurrentMode() {
  return ghTryGetVariants([
    "/api/modes/current",
    "/api/modes",
  ]);
}

async function ghSetMode(modeName) {
  return ghTryPostVariants([
    { url: "/api/modes/set", body: { mode: modeName } },
    { url: "/api/modes/switch", body: { mode: modeName } },
    { url: "/api/modes/set", body: { mode_name: modeName } },
    { url: "/api/modes/" + encodeURIComponent(modeName), body: {} },
  ]);
}

async function ghLoadAskCurrent() {
  return ghTryGetVariants([
    "/api/ask/current",
    "/api/ask",
  ]);
}

async function ghAskConfirm() {
  return ghTryPostVariants([
    { url: "/api/ask/confirm", body: {} },
    { url: "/api/ask/confirm", body: { confirm: true } },
  ]);
}

async function ghAskCancel() {
  return ghTryPostVariants([
    { url: "/api/ask/cancel", body: {} },
    { url: "/api/ask/cancel", body: { cancel: true } },
  ]);
}

async function ghRunAction(actionKey) {
  return ghTryPostVariants([
    { url: "/api/actions/execute", body: { action_key: actionKey } },
    { url: "/api/actions/run", body: { action_key: actionKey } },
    { url: "/api/actions/execute", body: { key: actionKey } },
    { url: "/api/actions/" + encodeURIComponent(actionKey), body: {} },
  ]);
}

async function ghLoadRegistryDevices() {
  return ghTryGetVariants([
    "/api/registry/devices",
    "/api/registry/list_devices",
    "/api/registry/items",
  ]);
}

async function ghLoadRegistryActions() {
  return ghTryGetVariants([
    "/api/registry/actions",
    "/api/registry/action_map",
  ]);
}

async function ghLoadRegistryCapabilities() {
  return ghTryGetVariants([
    "/api/registry/capabilities",
    "/api/registry/device_capabilities",
  ]);
}

async function ghLoadRegistryScenarios() {
  return ghTryGetVariants([
    "/api/registry/scenarios",
  ]);
}

async function ghLoadOverview() {
  return ghApi("/api/monitoring/overview", { method: "GET" });
}

async function ghLoadSafety() {
  return ghApi("/api/monitoring/safety", { method: "GET" });
}
