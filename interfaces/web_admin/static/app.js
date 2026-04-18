function ghToken() {
  return localStorage.getItem("gh_token") || "";
}

function ghHeaders(withAuth = true, extra = {}) {
  const headers = { ...extra };
  if (withAuth && ghToken()) headers["Authorization"] = "Bearer " + ghToken();
  if (!headers["Content-Type"] && !headers["content-type"]) {
    headers["Content-Type"] = "application/json";
  }
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
    data = { ok: false, error: "non_json_response", status: resp.status, url };
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


function ghJsonCount(value) {
  if (Array.isArray(value)) return value.length;
  if (value && typeof value === "object") return Object.keys(value).length;
  return 0;
}
