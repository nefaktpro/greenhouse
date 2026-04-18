async function ghApi(url, options = {}) {
  const opts = {
    credentials: "same-origin",
    ...options,
  };

  opts.headers = {
    ...(opts.headers || {}),
  };

  const resp = await fetch(url, opts);

  let data = null;
  try {
    data = await resp.json();
  } catch (_) {
    data = { ok: false, error: "invalid_json_response" };
  }

  if (resp.status === 401) {
    if (!location.pathname.endsWith("/web/login")) {
      window.location.href = "/web/login";
    }
  }

  return { resp, data };
}

function pretty(id, data) {
  const el = document.getElementById(id);
  if (el) el.textContent = JSON.stringify(data, null, 2);
}

function esc(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function logout() {
  await ghApi("/api/auth/logout", {
    method: "POST",
    headers: { "Content-Type": "application/json" }
  });
  window.location.href = "/web/login";
}
