"""System endpoints for the simplified SuperAI V11 runtime."""

from __future__ import annotations

import subprocess
import time

import psutil
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from backend.app.dependencies import get_master_controller, get_monitoring_service
from backend.config.settings import settings
from backend.models.schemas import APIResponse

router = APIRouter()
_STARTED_AT = time.time()


@router.get("/status", response_model=APIResponse)
async def status(mon=Depends(get_monitoring_service), ctrl=Depends(get_master_controller)):
    vm = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.1)
    gpu = None
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0:
            gpu = result.stdout.strip()
    except Exception:
        gpu = None

    controller_status = ctrl.get_status() if ctrl else {}
    return APIResponse(
        data={
            "status": "ok",
            "version": settings.personality.version,
            "mode": controller_status.get("mode", settings.current_mode),
            "is_minimal": controller_status.get("is_minimal", settings.is_minimal),
            "environment": settings.server.environment,
            "uptime_s": round(time.time() - _STARTED_AT, 1),
            "cpu_pct": cpu,
            "ram_pct": vm.percent,
            "gpu_info": gpu,
            "models_loaded": controller_status.get("model_loaded", []),
            "memory_enabled": controller_status.get("memory_enabled", False),
            "security_enabled": controller_status.get("security_enabled", True),
            "active_features": controller_status.get("features", []),
            "requests_total": mon.total_requests(),
            "avg_latency_ms": mon.avg_latency(),
        }
    )


@router.get("/metrics", summary="Prometheus metrics")
async def metrics():
    try:
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

        return PlainTextResponse(generate_latest().decode(), media_type=CONTENT_TYPE_LATEST)
    except ImportError:
        return PlainTextResponse("# Prometheus client not installed", media_type="text/plain")


@router.get("/config", response_model=APIResponse)
async def get_config():
    return APIResponse(
        data={
            "version": settings.personality.version,
            "mode": settings.current_mode,
            "server": {
                "host": settings.server.host,
                "port": settings.server.port,
                "environment": settings.server.environment,
            },
            "models": {"device": settings.models.device, "primary": settings.models.primary},
            "memory": {"enabled": settings.memory.enabled, "backend": settings.memory.backend},
            "security": {"enabled": settings.security.enabled},
            "logging": {"level": settings.logging.level},
            "enabled_features": list(settings.active_features.keys()),
        }
    )
