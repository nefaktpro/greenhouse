from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates

from greenhouse_v17.services.cleanup_service import (
    get_cleanup_sources,
    get_cleanup_status,
    scan_cleanup_sources,
    update_cleanup_policy,
    save_candidate_decision,
    get_candidate_decisions,
    preview_cleanup_file,
    save_candidate_decisions_batch,
)

router = APIRouter()
templates = Jinja2Templates(directory="interfaces/web_admin/templates")


@router.get("/web/cleanup", response_class=HTMLResponse)
def cleanup_page(request: Request):
    return templates.TemplateResponse(request, "cleanup.html", {})


@router.get("/api/cleanup/status")
def cleanup_status():
    return JSONResponse(get_cleanup_status())


@router.get("/api/cleanup/sources")
def cleanup_sources():
    return JSONResponse(get_cleanup_sources())


@router.post("/api/cleanup/scan")
def cleanup_scan():
    return JSONResponse(scan_cleanup_sources(save=True))


@router.get("/api/cleanup/scan")
def cleanup_scan_get():
    return JSONResponse(scan_cleanup_sources(save=True))


@router.post("/api/cleanup/policy")
async def cleanup_policy(request: Request):
    payload = await request.json()

    return JSONResponse(
        update_cleanup_policy(
            payload.get("source_id"),
            ai_scan_allowed=payload.get("ai_scan_allowed"),
            local_cleanup_allowed=payload.get("local_cleanup_allowed"),
            auto_delete_allowed=payload.get("auto_delete_allowed"),
            archive_allowed=payload.get("archive_allowed"),
            protected=payload.get("protected"),
            default_schedule=payload.get("default_schedule"),
            retention_days=payload.get("retention_days"),
        )
    )


@router.post("/api/cleanup/candidate/decision")
async def cleanup_candidate_decision(request: Request):
    payload = await request.json()
    return JSONResponse(
        save_candidate_decision(
            path=payload.get("path"),
            source_id=payload.get("source_id"),
            group_name=payload.get("group"),
            candidate_type=payload.get("candidate_type"),
            decision=payload.get("decision"),
            actor=payload.get("actor", "user"),
            reason=payload.get("reason"),
            payload=payload,
        )
    )


@router.get("/api/cleanup/candidate/decisions")
def cleanup_candidate_decisions():
    return JSONResponse(get_candidate_decisions())


@router.post("/api/cleanup/file/preview")
async def cleanup_file_preview(request: Request):
    payload = await request.json()
    return JSONResponse(
        preview_cleanup_file(
            path=payload.get("path"),
            max_bytes=int(payload.get("max_bytes") or 24000),
        )
    )


@router.get("/api/cleanup/file/view")
def cleanup_file_view(path: str):
    root = Path("/home/mi/greenhouse_v17").resolve()
    target = (root / path).resolve()

    try:
        target.relative_to(root)
    except Exception:
        return JSONResponse({"ok": False, "error": "path_outside_project"}, status_code=403)

    allowed_ext = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    allowed_roots = {
        (root / "data" / "photos").resolve(),
        (root / "data" / "camera").resolve(),
    }

    if target.suffix.lower() not in allowed_ext:
        return JSONResponse({"ok": False, "error": "not_allowed_ext"}, status_code=403)

    if not any(str(target).startswith(str(ar)) for ar in allowed_roots):
        return JSONResponse({"ok": False, "error": "not_allowed_path"}, status_code=403)

    if not target.exists() or not target.is_file():
        return JSONResponse({"ok": False, "error": "file_not_found"}, status_code=404)

    return FileResponse(target)


@router.post("/api/cleanup/candidate/decisions/batch")
async def cleanup_candidate_decisions_batch(request: Request):
    payload = await request.json()
    return JSONResponse(
        save_candidate_decisions_batch(
            items=payload.get("items") or [],
            decision=payload.get("decision"),
            actor=payload.get("actor", "user"),
            reason=payload.get("reason", "batch_review_from_cleanup_ui"),
        )
    )
