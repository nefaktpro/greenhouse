from fastapi import APIRouter
from greenhouse_v17.services.webadmin_execution_service import list_ai_timers

router = APIRouter()

@router.get("/api/ai/timers")
def api_ai_timers():
    return {"ok": True, "items": list_ai_timers()}



from fastapi.responses import HTMLResponse

@router.get("/web/ai/timers", response_class=HTMLResponse)
def web_ai_timers_plain():
    return HTMLResponse("""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>AI Timers</title>
</head>
<body style="background:#071022;color:#eaf1ff;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;padding:24px;">
  <h1>AI Timers</h1>
  <p>Активные и завершённые таймеры после AI/ASK-команд.</p>
  <button onclick="loadTimers()" style="padding:10px 14px;border-radius:10px;">Обновить</button>
  <div id="box" style="margin-top:18px;">Загрузка...</div>

<script>
function fmt(ts){ return ts ? new Date(ts*1000).toLocaleString() : "—"; }
async function loadTimers(){
  const box = document.getElementById("box");
  const r = await fetch("/api/ai/timers?ts=" + Date.now(), {cache:"no-store"});
  const data = await r.json();
  const items = data.items || [];
  if(!items.length){ box.innerHTML = "Таймеров пока нет."; return; }

  box.innerHTML = items.map(t => `
    <div style="border:1px solid rgba(120,160,220,.35);border-radius:16px;padding:14px;margin:12px 0;background:rgba(2,8,23,.45);">
      <b>${t.status}</b> — ${t.action_key} → ${t.followup_action_key}<br>
      duration: ${t.duration_seconds} сек<br>
      created: ${fmt(t.created_at)}<br>
      due: ${fmt(t.due_at)}<br>
      command: ${t.source_text || "—"}<br>
      verified: ${t.result && t.result.verified ? "true" : "—"}<br>
      ${t.error ? "error: " + t.error : ""}
      ${t.result ? `<details><summary>result</summary><pre>${JSON.stringify(t.result,null,2)}</pre></details>` : ""}
    </div>
  `).join("");
}
window.addEventListener("load", loadTimers);
setInterval(loadTimers, 3000);
</script>
</body>
</html>
""")
