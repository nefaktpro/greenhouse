#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/mi/greenhouse_v17"
cd "$ROOT"

TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$ROOT/backups/fix_web_500_only_$TS"
mkdir -p "$BACKUP_DIR"

backup_if_exists() {
  local path="$1"
  if [ -e "$path" ]; then
    mkdir -p "$BACKUP_DIR/$(dirname "$path")"
    cp -R "$path" "$BACKUP_DIR/$path"
    echo "[backup] $path"
  fi
}

backup_if_exists "interfaces/web_admin/routes/web.py"
backup_if_exists "interfaces/web_admin/static"

mkdir -p interfaces/web_admin/routes
mkdir -p interfaces/web_admin/static

cat > interfaces/web_admin/routes/web.py <<'PY'
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter(prefix="/web", tags=["web"])


def render(request: Request, template_name: str):
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context={"request": request},
    )


@router.get("/", response_class=HTMLResponse)
def index_page(request: Request):
    # Безопасный root: если есть monitoring.html, он обычно самый живой.
    return render(request, "monitoring.html")


@router.get("/monitoring", response_class=HTMLResponse)
def monitoring_page(request: Request):
    return render(request, "monitoring.html")


@router.get("/registry", response_class=HTMLResponse)
def registry_page(request: Request):
    return render(request, "registry.html")


@router.get("/safety", response_class=HTMLResponse)
def safety_page(request: Request):
    return render(request, "safety.html")


@router.get("/modes", response_class=HTMLResponse)
def modes_page(request: Request):
    return render(request, "modes.html")


@router.get("/ask", response_class=HTMLResponse)
def ask_page(request: Request):
    return render(request, "ask.html")


@router.get("/control", response_class=HTMLResponse)
def control_page(request: Request):
    return render(request, "control.html")
PY

# Если старые шаблоны тянут /static/app.css, а его нет — создаем минимальный
if [ ! -f interfaces/web_admin/static/app.css ]; then
  cat > interfaces/web_admin/static/app.css <<'CSS'
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
CSS
  echo "[created] interfaces/web_admin/static/app.css"
fi

sudo systemctl restart greenhouse-web-admin.service
sleep 2

echo
echo "=== STATUS ==="
sudo systemctl status greenhouse-web-admin.service --no-pager

echo
echo "=== QUICK CHECKS ==="
for path in /web/ /web/monitoring /web/registry /web/safety /web/modes /web/ask /web/control; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8081$path" || true)
  echo "$path -> $code"
done

echo
echo "Backup: $BACKUP_DIR"
