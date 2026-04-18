function ghToken() {
  return localStorage.getItem("gh_token");
}

function ghHeaders(json = true) {
  const headers = {};
  const token = ghToken();
  if (token) headers["Authorization"] = "Bearer " + token;
  if (json) headers["Content-Type"] = "application/json";
  return headers;
}

async function ghApi(url, options = {}) {
  const opts = { ...options };
  if (!opts.headers) opts.headers = ghHeaders(!opts.formData);
  if (opts.formData) delete opts.headers["Content-Type"];

  const resp = await fetch(url, opts);
  let data = null;
  try {
    data = await resp.json();
  } catch (_) {
    data = { ok: false, error: "invalid_json_response" };
  }

  if (resp.status === 401) {
    localStorage.removeItem("gh_token");
    if (!location.pathname.endsWith("/web/login")) {
      window.location.href = "/web/login";
    }
  }

  return { resp, data };
}

function pretty(elId, data) {
  const el = document.getElementById(elId);
  if (el) el.textContent = JSON.stringify(data, null, 2);
}

function logout() {
  localStorage.removeItem("gh_token");
  window.location.href = "/web/login";
}

function requireAuth() {
  if (!ghToken()) {
    window.location.href = "/web/login";
    return false;
  }
  return true;
}

function esc(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
