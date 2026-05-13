from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from greenhouse_v17.services.memory_summary_service import (
    get_summary_status,
    run_summary_cycle,
    generate_weekly_if_ready,
    generate_ai_weekly_if_ready,
    generate_monthly_if_ready,
    generate_ai_monthly_if_ready,
    generate_rolling_week_ai,
    generate_rolling_month_ai,
    run_summary_for_latest_activity,
    read_summary_file,
    generate_ai_summary_for_latest_daily,
    read_summary_file,
    generate_ai_summary_for_latest_daily,
)

router = APIRouter()


@router.get("/api/memory/summaries/status")
def memory_summaries_status():
    return JSONResponse(get_summary_status())


@router.post("/api/memory/summaries/run")
async def memory_summaries_run(request: Request):
    payload = await request.json()
    return JSONResponse(
        run_summary_cycle(
            target_date=payload.get("date"),
            force=bool(payload.get("force", False)),
        )
    )


@router.post("/api/memory/summaries/weekly")
def memory_summaries_weekly():
    return JSONResponse(generate_rolling_week_ai(force=True))


@router.post("/api/memory/summaries/monthly")
def memory_summaries_monthly():
    return JSONResponse(generate_rolling_month_ai(force=True))


@router.post("/api/memory/summaries/run_latest")
def memory_summaries_run_latest():
    return JSONResponse(run_summary_for_latest_activity(force=True))


@router.post("/api/memory/summaries/read")
async def memory_summaries_read(request: Request):
    payload = await request.json()
    return JSONResponse(read_summary_file(payload.get("path")))


@router.post("/api/memory/summaries/ai_latest")
def memory_summaries_ai_latest():
    return JSONResponse(generate_ai_summary_for_latest_daily())
