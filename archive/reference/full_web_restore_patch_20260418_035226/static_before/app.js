function token() {
  return localStorage.getItem("gh_token") || "";
}

function ghHeaders(withAuth = true) {
  const headers = { "Content-Type": "application/json" };
  if (withAuth && token()) headers["Authorization"] = "Bearer " + token();
  return headers;
}

async function ghApi(url, opts = {}) {
  const method = opts.method || "GET";
  const body = opts.body;
  const withAuth = opts.auth !== false;

  const resp = await fetch(url, {
    method,
    headers: ghHeaders(withAuth),
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

function pretty(elementId, value) {
  const el = document.getElementById(elementId);
  if (!el) return;
  el.textContent = JSON.stringify(value, null, 2);
}

function requireAuth() {
  if (!token()) {
    window.location.href = "/web/login";
    return false;
  }
  return true;
}

async function logout() {
  try {
    await ghApi("/api/auth/logout", { method: "POST", auth: false });
  } catch (_) {}
  localStorage.removeItem("gh_token");
  window.location.href = "/web/login";
}

async function ghTryGetVariants(urls) {
  for (const url of urls) {
    try {
      const { resp, data } = await ghApi(url, { method: "GET" });
      if (resp.ok) return { source: url, data };
    } catch (_) {}
  }
  return { ok: false, error: "no_get_variant_worked", tried: urls };
}

async function ghTryPostVariants(variants) {
  for (const item of variants) {
    try {
      const { resp, data } = await ghApi(item.url, {
        method: "POST",
        body: JSON.stringify(item.body || {})
      });
      if (resp.ok) return { source: item.url, data };
    } catch (_) {}
  }
  return {
    ok: false,
    error: "no_post_variant_worked",
    tried: variants.map(v => v.url)
  };
}
