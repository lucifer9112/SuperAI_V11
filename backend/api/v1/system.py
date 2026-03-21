"""SuperAI V11 — backend/api/v1/system.py"""
import time, subprocess, psutil
from fastapi import APIRouter, Depends
from backend.app.dependencies import get_monitoring_service, get_feedback_service
from backend.config.settings import settings
from backend.models.schemas import APIResponse

router = APIRouter()
_START = time.time()

@router.get("/status", response_model=APIResponse)
async def status(mon=Depends(get_monitoring_service), fb=Depends(get_feedback_service)):
    vm, cpu, gpu = psutil.virtual_memory(), psutil.cpu_percent(interval=0.1), None
    try:
        r = subprocess.run(["nvidia-smi","--query-gpu=name,memory.used,memory.total",
            "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=3)
        if r.returncode == 0: gpu = r.stdout.strip()
    except Exception: pass
    return APIResponse(data={"status":"ok","version":settings.personality.version,
        "environment":settings.server.environment,
        "uptime_s":round(time.time()-_START,1),"cpu_pct":cpu,"ram_pct":vm.percent,
        "gpu_info":gpu,"models_loaded":mon.loaded_models(),"requests_total":mon.total_requests(),
        "avg_latency_ms":mon.avg_latency(),"feedback_count":fb.total_count() if fb else 0})

@router.get("/metrics", summary="Prometheus metrics")
async def metrics():
    from fastapi.responses import PlainTextResponse
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    return PlainTextResponse(generate_latest().decode(), media_type=CONTENT_TYPE_LATEST)

@router.get("/config", response_model=APIResponse)
async def get_config():
    return APIResponse(data={"version":settings.personality.version,
        "server":{"host":settings.server.host,"port":settings.server.port},
        "models":{"device":settings.models.device,"routing":settings.models.routing},
        "memory":{"backend":settings.memory.backend},"logging":{"level":settings.logging.level}})
