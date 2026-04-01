"""SuperAI V11 - backend/api/ws/chat_ws.py - Real-time WebSocket chat."""
from __future__ import annotations

import json
import time
import uuid
from collections import deque
from typing import Any, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from backend.app.dependencies import container
from backend.models.schemas import ChatRequest, ChatResponse
from backend.config.settings import settings

ws_router = APIRouter()
MAX_CONNECTIONS = 100
MAX_MSG_PER_MIN = 20


class _ConnMgr:
    def __init__(self) -> None:
        self._conns: Dict[str, WebSocket] = {}
        self._messages: Dict[str, deque[float]] = {}

    async def connect(self, ws: WebSocket, cid: str) -> None:
        if self.count >= MAX_CONNECTIONS:
            await ws.close(code=1008, reason="Too many connections")
            raise RuntimeError("Connection limit reached")
        await ws.accept()
        self._conns[cid] = ws
        self._messages[cid] = deque()

    def disconnect(self, cid: str) -> None:
        self._conns.pop(cid, None)
        self._messages.pop(cid, None)

    async def send(self, ws: WebSocket, msg: Dict[str, Any]) -> None:
        await ws.send_text(json.dumps(msg))

    def allow_message(self, cid: str) -> bool:
        now = time.time()
        bucket = self._messages.setdefault(cid, deque())
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
        if len(bucket) >= MAX_MSG_PER_MIN:
            return False
        bucket.append(now)
        return True

    @property
    def count(self) -> int:
        return len(self._conns)


_mgr = _ConnMgr()


@ws_router.websocket("/chat")
async def ws_chat(ws: WebSocket) -> None:
    cid = str(uuid.uuid4())[:8]
    if settings.server.environment == "production":
        api_key = ws.headers.get("x-api-key")
        if not api_key or api_key != settings.security.secret_key:
            await ws.close(code=1008, reason="Invalid API key")
            return

    try:
        await _mgr.connect(ws, cid)
    except RuntimeError:
        return
    logger.info("WS connected", cid=cid, total=_mgr.count)
    try:
        while True:
            raw = await ws.receive_text()
            if not _mgr.allow_message(cid):
                await _mgr.send(ws, {"type": "error", "data": "Rate limit exceeded"})
                await ws.close(code=1008, reason="Rate limit exceeded")
                break
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await _mgr.send(ws, {"type": "error", "data": "Invalid JSON"})
                continue
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

                controller = container.master_controller
                req.session_id = req.session_id or str(uuid.uuid4())[:8]
                orchestrator = getattr(controller, "_orchestrator", None)

                if orchestrator is not None:
                    task_type = req.force_task or orchestrator.route_prompt(req.prompt)
                    model_name = orchestrator.select_model_for_task(task_type, req.force_model)
                    started = time.perf_counter()
                    chunks = []

                    async for token in orchestrator.chat_stream(req):
                        chunks.append(token)
                        await _mgr.send(ws, {"type": "token", "data": token})

                    answer = "".join(chunks)
                    model_name = orchestrator._resolved_model_name(model_name)
                    tokens_used = await orchestrator.count_text_tokens(model_name, answer)
                    final = ChatResponse(
                        answer=answer,
                        session_id=req.session_id,
                        task_type=task_type.value if hasattr(task_type, "value") else str(task_type),
                        model_used=model_name,
                        tokens_used=tokens_used,
                        latency_ms=round((time.perf_counter() - started) * 1000, 2),
                    )
                else:
                    result = await controller.process(req)
                    await _mgr.send(ws, {"type": "token", "data": result.answer})
                    final = result

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
