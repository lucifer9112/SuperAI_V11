"""SuperAI V11 - backend/api/ws/chat_ws.py - Real-time WebSocket chat."""
from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from backend.app.dependencies import container
from backend.models.schemas import ChatRequest, ChatResponse

ws_router = APIRouter()


class _ConnMgr:
    def __init__(self) -> None:
        self._conns: Dict[str, WebSocket] = {}

    async def connect(self, ws: WebSocket, cid: str) -> None:
        await ws.accept()
        self._conns[cid] = ws

    def disconnect(self, cid: str) -> None:
        self._conns.pop(cid, None)

    async def send(self, ws: WebSocket, msg: Dict[str, Any]) -> None:
        await ws.send_text(json.dumps(msg))

    @property
    def count(self) -> int:
        return len(self._conns)


_mgr = _ConnMgr()


@ws_router.websocket("/chat")
async def ws_chat(ws: WebSocket) -> None:
    cid = str(uuid.uuid4())[:8]
    await _mgr.connect(ws, cid)
    logger.info("WS connected", cid=cid, total=_mgr.count)
    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            t = msg.get("type", "")

            if t == "ping":
                await _mgr.send(ws, {"type": "pong"})
                continue

            if t == "chat":
                payload = msg.get("payload", {})
                try:
                    req = ChatRequest(**payload)
                except Exception as e:
                    await _mgr.send(ws, {"type": "error", "data": str(e)})
                    continue

                orch = container.orchestrator
                req.session_id = req.session_id or str(uuid.uuid4())[:8]
                task_type = req.force_task or orch._router.route(req.prompt)
                model_name = req.force_model or orch._router.select_model(task_type)
                started = time.perf_counter()
                chunks = []

                async for token in orch.chat_stream(req):
                    chunks.append(token)
                    await _mgr.send(ws, {"type": "token", "data": token})

                answer = "".join(chunks)
                final = ChatResponse(
                    answer=answer,
                    session_id=req.session_id,
                    task_type=task_type.value if hasattr(task_type, "value") else str(task_type),
                    model_used=model_name,
                    tokens_used=max(1, len(answer.split())) if answer else 0,
                    latency_ms=round((time.perf_counter() - started) * 1000, 2),
                )
                await _mgr.send(
                    ws,
                    {"type": "done", "data": final.model_dump() if hasattr(final, "model_dump") else final},
                )
                continue

            await _mgr.send(ws, {"type": "error", "data": f"Unknown type: '{t}'"})

    except WebSocketDisconnect:
        _mgr.disconnect(cid)
        logger.info("WS disconnected", cid=cid)
    except Exception:
        logger.exception("WS error", cid=cid)
        try:
            await _mgr.send(ws, {"type": "error", "data": "Internal error"})
        except Exception:
            pass
        _mgr.disconnect(cid)
