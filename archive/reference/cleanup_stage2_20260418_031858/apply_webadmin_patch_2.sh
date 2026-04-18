#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/mi/greenhouse_v17"
TPL="$ROOT/interfaces/web_admin/templates"
BACKUP_DIR="$ROOT/backups/web_admin_$(date +%Y%m%d_%H%M%S)_patch2"

mkdir -p "$BACKUP_DIR"
mkdir -p "$TPL"

[ -f "$TPL/registry.html" ] && cp "$TPL/registry.html" "$BACKUP_DIR/registry.html.bak" || true

cat > "$TPL/registry.html" <<'HTML'
{% set page_id = 'registry' %}
{% extends "base.html" %}

{% block title %}Greenhouse v17 — Registry{% endblock %}

{% block content %}
<div class="two-col">
  <section class="card">
    <div class="eyebrow">Registry</div>
    <h2 style="font-size:24px;">Devices</h2>
    <input id="deviceSearch" class="search" placeholder="Поиск по id / name / zone / role / entity_id" style="margin:16px 0;" />
    <div id="deviceMeta" class="chips" style="margin-bottom:14px;"></div>
    <div id="devicesList" class="list">Загрузка...</div>
  </section>

  <section class="card">
    <div class="eyebrow">Registry</div>
    <h2 style="font-size:24px;">Capabilities</h2>
    <input id="capSearch" class="search" placeholder="Поиск по capability / action / mode" style="margin:16px 0;" />
    <div id="capMeta" class="chips" style="margin-bottom:14px;"></div>
    <div id="capsList" class="list">Загрузка...</div>
  </section>
</div>
{% endblock %}

{% block scripts %}
<script>
  let DEVICES = [];
  let CAPS = [];

  function deviceText(x) {
    return [
      x.device_id, x.parent_id, x.name, x.type, x.zone, x.location,
      x.logical_role, x.entity_id, x.criticality, x.source, x.notes
    ].join(" ").toLowerCase();
  }

  function capText(key, x) {
    return [
      key,
      ...(x.allowed_actions || []),
      ...(x.allowed_modes || []),
      ...(x.pre_checks || []),
      ...(x.post_checks || []),
      ...(x.safety_flags || [])
    ].join(" ").toLowerCase();
  }

  function renderDevices() {
    const q = document.getElementById("deviceSearch").value.trim().toLowerCase();
    const items = DEVICES.filter(x => !q || deviceText(x).includes(q));
    document.getElementById("deviceMeta").innerHTML = `
      <span class="chip ok">count: ${DEVICES.length}</span>
      <span class="chip">filtered: ${items.length}</span>
    `;

    const root = document.getElementById("devicesList");
    if (!items.length) {
      root.innerHTML = `<div class="empty">По этому фильтру устройств не найдено.</div>`;
      return;
    }

    root.innerHTML = items.slice(0, 200).map(x => `
      <div class="row" style="align-items:flex-start;">
        <div style="width:100%;">
          <div class="name">${x.device_id || "—"} — ${x.name || "Без названия"}</div>
          <div class="sub">${x.type || "—"} · zone: ${x.zone || "—"} · role: ${x.logical_role || "—"}</div>
          <div class="kv" style="margin-top:10px;">
            <div>entity_id</div><div class="mono">${x.entity_id || "—"}</div>
            <div>location</div><div>${x.location || "—"}</div>
            <div>criticality</div><div>${x.criticality || "—"}</div>
            <div>enabled</div><div>${x.is_enabled || "—"}</div>
            <div>virtual</div><div>${x.is_virtual || "—"}</div>
            <div>source</div><div>${x.source || "—"}</div>
          </div>
          ${x.notes ? `<div class="sub" style="margin-top:10px;">notes: ${x.notes}</div>` : ""}
        </div>
      </div>
    `).join("");
  }

  function renderCaps() {
    const q = document.getElementById("capSearch").value.trim().toLowerCase();
    const entries = Object.entries(CAPS).filter(([k, v]) => !q || capText(k, v).includes(q));
    document.getElementById("capMeta").innerHTML = `
      <span class="chip ok">count: ${Object.keys(CAPS).length}</span>
      <span class="chip">filtered: ${entries.length}</span>
    `;

    const root = document.getElementById("capsList");
    if (!entries.length) {
      root.innerHTML = `<div class="empty">По этому фильтру capability не найдено.</div>`;
      return;
    }

    root.innerHTML = entries.map(([k, v]) => `
      <div class="row" style="align-items:flex-start;">
        <div style="width:100%;">
          <div class="name">${k}</div>
          <div class="chips" style="margin-top:10px;">
            ${(v.allowed_actions || []).map(x => `<span class="chip ok">${x}</span>`).join("") || `<span class="chip">no actions</span>`}
          </div>
          <div class="kv" style="margin-top:12px;">
            <div>allowed_modes</div><div>${(v.allowed_modes || []).join(", ") || "—"}</div>
            <div>dependencies</div><div>${(v.dependencies || []).join(", ") || "—"}</div>
            <div>pre_checks</div><div>${(v.pre_checks || []).join(", ") || "—"}</div>
            <div>post_checks</div><div>${(v.post_checks || []).join(", ") || "—"}</div>
            <div>safety_flags</div><div>${(v.safety_flags || []).join(", ") || "—"}</div>
            <div>fallback</div><div>${v.fallback_behavior || "—"}</div>
            <div>constraints</div><div class="mono">${JSON.stringify(v.constraints || {})}</div>
          </div>
        </div>
      </div>
    `).join("");
  }

  async function loadRegistry() {
    const devicesRoot = document.getElementById("devicesList");
    const capsRoot = document.getElementById("capsList");

    try {
      const [devices, caps] = await Promise.all([
        GH.api("/api/registry/devices"),
        GH.api("/api/registry/capabilities")
      ]);

      DEVICES = Array.isArray(devices.items) ? devices.items : [];
      CAPS = caps.items || {};

      renderDevices();
      renderCaps();
    } catch (e) {
      devicesRoot.innerHTML = `<div class="empty">Ошибка загрузки devices: ${e.message}</div>`;
      capsRoot.innerHTML = `<div class="empty">Ошибка загрузки capabilities: ${e.message}</div>`;
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("deviceSearch").addEventListener("input", renderDevices);
    document.getElementById("capSearch").addEventListener("input", renderCaps);
    loadRegistry();
  });
</script>
{% endblock %}
HTML

echo "Patch 2 applied."
echo "Backup: $BACKUP_DIR"
