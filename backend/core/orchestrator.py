"""
SuperAI V11 — backend/core/orchestrator.py

V11 FULL PIPELINE (15 steps):
  [F8]  AI Security assessment
  [F11] Personality emotion update
  [F6]  Correction detection
  [Task Router] classify + select model
  [F3]  Unified memory retrieval
  [F5]  RAG++ web knowledge
  [V11-S2] Tool Calling Engine — enrich prompt with tool outputs
  [Prompt Build] assemble full context
  [F10] Task queue OR direct inference
  [V11-S3] Consensus — run N models if configured
  [F1]  Self-reflection — confidence + critique
  [F6]  Log low-confidence
  [F11] Personalize response
  [V11-S1] Score with reward model
  [Memory] persist turn + episodic
"""
from __future__ import annotations
import asyncio, time, uuid
from typing import AsyncGenerator, List, Optional
from loguru import logger
from backend.config.settings import PersonalitySettings
from backend.core.exceptions import SecurityViolationError, ModelInferenceError
from backend.models.schemas import (
    ChatRequest,
    ChatResponse,
    CodeRequest,
    CodeResponse,
    FileProcessResponse,
    MemoryStoreRequest,
    TaskType,
)


class OrchestratorV11:
    def __init__(
        self,
        model_loader, memory_svc, agent_svc, voice_svc, vision_svc,
        security_engine, task_router, monitoring_svc, personality_cfg: PersonalitySettings,
        # V10 features
        reflection_engine=None, learning_pipeline=None, unified_memory=None,
        parallel_executor=None, rag_engine=None, self_improvement=None,
        model_registry=None, ai_security=None, fusion_engine=None,
        task_queue=None, personality_engine=None,
        # V11 new features
        rlhf_pipeline=None,        # S1: RLHF
        tool_engine=None,          # S2: Tool Calling
        consensus_engine=None,     # S3: Multi-Model Consensus
    ) -> None:
        # V9/V10 core
        self._models=model_loader; self._memory=memory_svc; self._agents=agent_svc
        self._voice=voice_svc; self._vision=vision_svc; self._security=security_engine
        self._router=task_router; self._monitoring=monitoring_svc
        self._personality_cfg=personality_cfg
        # V10
        self._reflection=reflection_engine; self._learning=learning_pipeline
        self._uni_memory=unified_memory; self._parallel=parallel_executor
        self._rag=rag_engine; self._improve=self_improvement
        self._registry=model_registry; self._ai_security=ai_security
        self._fusion=fusion_engine; self._task_queue=task_queue
        self._personality=personality_engine
        # V11
        self._rlhf      = rlhf_pipeline
        self._tools     = tool_engine
        self._consensus = consensus_engine

        active = self._active_features()
        logger.info("OrchestratorV11 ready", features=active, count=len(active))

    def route_prompt(self, prompt: str):
        return self._router.route(prompt)

    def select_model_for_task(self, task_type, forced_model: Optional[str] = None) -> str:
        if forced_model:
            return forced_model
        if self._registry and hasattr(task_type, "value"):
            model_name = self._registry.best_for_task(task_type.value)
            if model_name:
                return model_name
        return self._router.select_model(task_type)

    async def count_text_tokens(self, model_name: str, text: str) -> int:
        if not text:
            return 0
        if hasattr(self._models, "count_tokens"):
            return await self._models.count_tokens(model_name, text)
        return max(1, len(text.split()))

    def _resolved_model_name(self, model_name: str) -> str:
        if hasattr(self._models, "resolve_model_name"):
            return self._models.resolve_model_name(model_name)
        return model_name

    def _should_fast_path(self, req: ChatRequest, task_type: TaskType) -> bool:
        if task_type != TaskType.CHAT:
            return False
        if req.force_model or req.force_task:
            return False
        prompt = req.prompt.strip()
        if not prompt or len(prompt) > 160:
            return False
        if prompt.count("\n") > 1:
            return False
        lower = prompt.lower()
        complex_markers = (
            "search",
            "latest",
            "today",
            "news",
            "document",
            "pdf",
            "file",
            "image",
            "audio",
            "tool",
            "agent",
            "workflow",
            "compare",
            "research",
            "analyze",
            "http://",
            "https://",
        )
        return not any(marker in lower for marker in complex_markers)

    async def _fast_chat(self, req: ChatRequest, sid: str, rid: str, t0: float, task_type: TaskType) -> ChatResponse:
        if self._personality:
            from backend.memory.advanced_memory import detect_emotion

            self._personality.update_session(sid, req.prompt, detect_emotion(req.prompt))
        pa = self._personality.get_system_prompt_addon(sid) if self._personality else ""
        context = []
        if self._memory:
            try:
                context = await self._memory.get_context(session_id=sid, prompt=req.prompt)
            except Exception as exc:
                logger.warning("Fast path context lookup failed", error=str(exc))
        prompt = self._build_prompt(req.prompt, task_type, context, pa=pa)
        model_name = self.select_model_for_task(task_type, req.force_model)
        answer, tokens = await self._models.infer(model_name, prompt, req.max_tokens, req.temperature)
        resolved_model_name = self._resolved_model_name(model_name)

        if self._security and self._security.cfg.output_filter:
            answer = self._security.filter_output(answer)
        if self._personality:
            answer = self._personality.personalize_response(answer, sid)

        if self._memory:
            await self._memory.save_turn(sid, req.prompt, answer, response_id=rid)
        ms = (time.perf_counter() - t0) * 1000
        if self._monitoring:
            self._monitoring.record_request(task_type=task_type.value, model=resolved_model_name, latency_ms=ms, tokens=tokens)
        logger.debug("Orchestrator fast path used", session_id=sid, model=resolved_model_name)
        return ChatResponse(
            answer=answer,
            session_id=sid,
            task_type=task_type.value,
            model_used=resolved_model_name,
            tokens_used=tokens,
            latency_ms=round(ms, 2),
            response_id=rid,
        )

    async def _fast_chat_stream(self, req: ChatRequest, sid: str, rid: str, t0: float, task_type: TaskType) -> AsyncGenerator[str, None]:
        if self._personality:
            from backend.memory.advanced_memory import detect_emotion

            self._personality.update_session(sid, req.prompt, detect_emotion(req.prompt))
        pa = self._personality.get_system_prompt_addon(sid) if self._personality else ""
        context = []
        if self._memory:
            try:
                context = await self._memory.get_context(session_id=sid, prompt=req.prompt)
            except Exception as exc:
                logger.warning("Fast stream context lookup failed", error=str(exc))
        prompt = self._build_prompt(req.prompt, task_type, context, pa=pa)
        model_name = self.select_model_for_task(task_type, req.force_model)
        full: list[str] = []
        async for tok in self._models.stream(model_name, prompt, req.max_tokens, req.temperature):
            full.append(tok)
            yield tok

        full_text = "".join(full)
        resolved_model_name = self._resolved_model_name(model_name)
        if self._security and self._security.cfg.output_filter:
            full_text = self._security.filter_output(full_text)
        if self._personality:
            full_text = self._personality.personalize_response(full_text, sid)

        if self._memory:
            await self._memory.save_turn(sid, req.prompt, full_text, response_id=rid)
        tokens = await self.count_text_tokens(resolved_model_name, full_text)
        if self._monitoring:
            self._monitoring.record_request(
                task_type=task_type.value,
                model=resolved_model_name,
                latency_ms=(time.perf_counter() - t0) * 1000,
                tokens=tokens,
            )
        logger.debug("Orchestrator fast stream path used", session_id=sid, model=resolved_model_name)

    async def chat(self, req: ChatRequest) -> ChatResponse:
        t0=time.perf_counter(); sid=req.session_id or str(uuid.uuid4())[:8]
        rid=str(uuid.uuid4())[:8]

        # [F8] AI Security
        if self._ai_security:
            a=await self._ai_security.assess(req.prompt, sid)
            if a.blocked: raise SecurityViolationError("AI security blocked",
                detail={"threat_type":a.threat_type,"confidence":a.confidence})
        elif self._security and self._security.cfg.enabled:
            v=self._security.validate(req.prompt)
            if v: raise SecurityViolationError("Input blocked",detail=v)

        task_type=req.force_task or self.route_prompt(req.prompt)
        if self._should_fast_path(req, task_type):
            return await self._fast_chat(req, sid, rid, t0, task_type)

        # [F6] Correction check
        if self._improve: await self._improve.check_correction(req.prompt, sid)

        # [F11] Personality emotion
        emotion="neutral"
        if self._personality:
            from backend.memory.advanced_memory import detect_emotion
            emotion=detect_emotion(req.prompt)
            self._personality.update_session(sid, req.prompt, emotion)

        # [F3] Memory
        mem_ctx={}
        if self._uni_memory:
            try: mem_ctx=await self._uni_memory.retrieve(sid, req.prompt)
            except Exception as e: logger.warning("UniMemory failed",error=str(e))
        context=mem_ctx.get("recent_turns") or \
                await self._memory.get_context(session_id=sid,prompt=req.prompt)

        # [F5] RAG++
        rag_ctx=""
        if self._rag and task_type in (TaskType.SEARCH,TaskType.CHAT,TaskType.DOCUMENT):
            try: rag_ctx=await self._rag.retrieve_context(req.prompt)
            except Exception as e: logger.warning("RAG failed",error=str(e))

        # [V11-S2] Tool Calling — enrich prompt with live tool outputs
        tool_prompt = req.prompt
        tools_used  = []
        if self._tools:
            try:
                tr = await self._tools.process(req.prompt, autonomy_level=2)
                if tr.tools_used:
                    tool_prompt = tr.enriched_prompt
                    tools_used  = tr.tools_used
                    logger.info("Tools used", tools=tools_used)
            except Exception as e: logger.warning("Tool calling failed",error=str(e))

        # Personality addon
        pa=""
        if self._personality: pa=self._personality.get_system_prompt_addon(sid)

        prompt=self._build_prompt(tool_prompt, task_type, context, rag_ctx,
                                   mem_ctx.get("enriched_prompt",""), pa)

        # Model selection
        model_name=self.select_model_for_task(task_type, req.force_model)

        # [V11-S3] Consensus OR direct inference
        consensus_result = None
        if self._consensus and self._consensus.model_count > 1:
            try:
                consensus_result = await self._consensus.run(
                    prompt, req.max_tokens, req.temperature)
                answer = consensus_result.final_answer
                tokens = sum(r.tokens for r in consensus_result.all_responses)
                model_name = consensus_result.winner_model
            except Exception as e:
                logger.warning("Consensus failed, falling back", error=str(e))
                if self._monitoring:
                    self._monitoring.record_error("consensus")
                consensus_result = None

        if consensus_result is None:
            # Direct inference (or task queue)
            try:
                if self._task_queue:
                    tid=await self._task_queue.submit(self._models.infer,model_name,prompt,
                                                       req.max_tokens,req.temperature,
                                                       name=f"infer_{task_type.value}",priority=3)
                    answer,tokens=await self._task_queue.wait(tid,timeout=120)
                else:
                    answer,tokens=await self._models.infer(model_name,prompt,req.max_tokens,req.temperature)
            except Exception as e:
                logger.exception("Inference failed",model=model_name)
                if self._monitoring:
                    self._monitoring.record_error("inference")
                raise ModelInferenceError(str(e)) from e
            model_name = self._resolved_model_name(model_name)

        # [F1] Self-reflection
        confidence=1.0; reflection_notes=""
        if self._reflection:
            try:
                r=await self._reflection.reflect(req.prompt,answer,task_type.value,model_name)
                answer=r.final_answer; confidence=r.confidence; reflection_notes=r.reflection_notes
                if self._improve and confidence<0.5:
                    await self._improve.record_low_confidence(confidence,req.prompt,answer,sid)
            except Exception as e: logger.warning("Reflection failed",error=str(e))

        # V9 output filter
        if self._security and self._security.cfg.output_filter:
            answer=self._security.filter_output(answer)

        # [F11] Personalize
        if self._personality: answer=self._personality.personalize_response(answer,sid)

        # [V11-S1] RLHF reward score (non-blocking, log only)
        reward_score=0.0
        if self._rlhf:
            try: reward_score=await self._rlhf.score_response(req.prompt,answer)
            except Exception: pass

        # Persist
        await self._memory.save_turn(sid,req.prompt,answer,response_id=rid)
        if self._uni_memory and hasattr(self._uni_memory,"_episodic"):
            try: await self._uni_memory._episodic.store(sid,req.prompt,answer,importance=confidence)
            except Exception: pass

        # Metrics
        ms=(time.perf_counter()-t0)*1000
        self._monitoring.record_request(task_type=task_type.value,model=model_name,
                                         latency_ms=ms,tokens=tokens)

        return ChatResponse(answer=answer,session_id=sid,task_type=task_type.value,
            model_used=model_name,tokens_used=tokens,latency_ms=round(ms,2),
            response_id=rid)

    async def chat_stream(self, req: ChatRequest) -> AsyncGenerator[str,None]:
        sid=req.session_id or str(uuid.uuid4())[:8]
        rid=str(uuid.uuid4())[:8]
        t0=time.perf_counter()

        if self._ai_security:
            a=await self._ai_security.assess(req.prompt, sid)
            if a.blocked:
                raise SecurityViolationError(
                    "AI security blocked",
                    detail={"threat_type": a.threat_type, "confidence": a.confidence},
                )
        elif self._security and self._security.cfg.enabled:
            v=self._security.validate(req.prompt)
            if v: raise SecurityViolationError("Input blocked",detail=v)

        task_type=req.force_task or self.route_prompt(req.prompt)
        if self._should_fast_path(req, task_type):
            async for tok in self._fast_chat_stream(req, sid, rid, t0, task_type):
                yield tok
            return

        if self._improve:
            await self._improve.check_correction(req.prompt, sid)

        emotion="neutral"
        if self._personality:
            from backend.memory.advanced_memory import detect_emotion
            emotion=detect_emotion(req.prompt)
            self._personality.update_session(sid, req.prompt, emotion)

        mem_ctx={}
        if self._uni_memory:
            try:
                mem_ctx=await self._uni_memory.retrieve(sid, req.prompt)
            except Exception as e:
                logger.warning("UniMemory failed", error=str(e))
        context=mem_ctx.get("recent_turns") or await self._memory.get_context(sid,req.prompt)
        rag_ctx=""
        if self._rag and task_type in (TaskType.SEARCH,TaskType.CHAT,TaskType.DOCUMENT):
            try:
                rag_ctx=await self._rag.retrieve_context(req.prompt)
            except Exception as e:
                logger.warning("RAG failed", error=str(e))

        tool_prompt=req.prompt
        if self._tools:
            try:
                tr=await self._tools.process(req.prompt,autonomy_level=2)
                if tr.tools_used: tool_prompt=tr.enriched_prompt
            except Exception as e:
                logger.warning("Tool calling failed", error=str(e))

        pa=""
        if self._personality:
            pa=self._personality.get_system_prompt_addon(sid)

        prompt=self._build_prompt(
            tool_prompt,
            task_type,
            context,
            rag_ctx,
            mem_ctx.get("enriched_prompt",""),
            pa,
        )
        model_name=self.select_model_for_task(task_type, req.force_model)
        full=[]
        async for tok in self._models.stream(model_name,prompt,req.max_tokens,req.temperature):
            full.append(tok); yield tok
        full_text="".join(full)
        model_name=self._resolved_model_name(model_name)

        # [F1] Self-reflection on completed stream
        confidence=1.0
        if self._reflection:
            try:
                r=await self._reflection.reflect(req.prompt,full_text,
                    task_type.value if hasattr(task_type,"value") else str(task_type),model_name)
                full_text=r.final_answer; confidence=r.confidence
                if self._improve and confidence<0.5:
                    await self._improve.record_low_confidence(confidence,req.prompt,full_text,sid)
            except Exception as e: logger.warning("Stream reflection failed",error=str(e))

        # Output safety filter
        if self._security and self._security.cfg.output_filter:
            full_text=self._security.filter_output(full_text)

        if self._personality:
            full_text=self._personality.personalize_response(full_text,sid)

        if self._rlhf:
            try:
                await self._rlhf.score_response(req.prompt,full_text)
            except Exception:
                pass

        await self._memory.save_turn(sid,req.prompt,full_text,response_id=rid)
        if self._uni_memory and hasattr(self._uni_memory,"_episodic"):
            try:
                await self._uni_memory._episodic.store(sid,req.prompt,full_text,importance=confidence)
            except Exception:
                pass

        tokens=await self.count_text_tokens(model_name, full_text)
        self._monitoring.record_request(
            task_type=task_type.value if hasattr(task_type, "value") else str(task_type),
            model=model_name,
            latency_ms=(time.perf_counter()-t0)*1000,
            tokens=tokens,
        )

    async def code(self, req: CodeRequest) -> CodeResponse:
        model=self._router.select_model(TaskType.CODE)
        action=req.action.value if hasattr(req.action,"value") else str(req.action)
        am={"generate":f"Generate {req.language} code for: {req.description}",
            "debug":f"Debug:\n```{req.language}\n{req.code}\n```",
            "explain":f"Explain:\n```{req.language}\n{req.code}\n```",
            "review":f"Review:\n```{req.language}\n{req.code}\n```",
            "optimize":f"Optimize:\n```{req.language}\n{req.code}\n```",
            "test":f"Write tests for:\n```{req.language}\n{req.code}\n```"}
        prompt=f"Expert {req.language} developer.\n{am.get(action,req.code)}\n\nResponse:"
        answer,_=await self._models.infer(model,prompt,max_tokens=2048,temperature=0.2)
        return CodeResponse(result=answer,action=action,language=req.language)

    async def security_scan(self,code:str,language:str)->List[str]:
        return await self._security.scan_code(code=code,language=language)

    async def run_parallel_agents(self,goal,mode="parallel",agents=None,session_id="",model_name=""):
        if not self._parallel:
            if not self._agents:
                answer, _ = await self._models.infer(
                    model_name or self._router.select_model(TaskType.AGENT),
                    f"Goal: {goal}\n\nRespond with a concise execution plan and final recommendation.",
                    max_tokens=512,
                    temperature=0.3,
                )
                from backend.models.schemas import AgentRunResponse
                return AgentRunResponse(
                    goal=goal,
                    session_id=session_id or "",
                    final_answer=answer,
                    iterations=1,
                )
            from backend.models.schemas import AgentRunRequest
            return await self._agents.run(AgentRunRequest(goal=goal,session_id=session_id or None))
        from backend.agents.parallel_executor import ExecutionMode
        mode_enum=ExecutionMode.PARALLEL if mode=="parallel" else ExecutionMode.SINGLE
        return await self._parallel.execute(goal=goal,mode=mode_enum,
            selected_agents=agents,model_name=model_name or self._router.select_model(TaskType.AGENT))

    async def process_file(self,filename,file_bytes,question,session_id)->FileProcessResponse:
        file_id = str(uuid.uuid4())[:8]
        text=await self._extract_file_text(filename,file_bytes)
        prompt=f"Document:\n{text[:3000]}\n\nQuestion: {question}\nAnswer:"
        model=self._router.select_model(TaskType.DOCUMENT)
        answer,_=await self._models.infer(model,prompt,max_tokens=512)
        if self._looks_degraded_answer(answer):
            answer = self._fallback_file_answer(filename, text, question)
        if self._memory and text and not text.startswith("[Cannot extract"):
            await self._memory.store(
                MemoryStoreRequest(
                    content=text[:20000],
                    session_id=session_id,
                    tags=[f"file:{file_id}", f"filename:{filename}"],
                    priority=1.2,
                )
            )
        return FileProcessResponse(
            file_id=file_id,
            filename=filename,
            file_type=filename.rsplit(".",1)[-1].lower(),
            summary=answer,
            content=text[:2000],
        )

    async def file_qa(self,file_id,question):
        if hasattr(self._memory, "search_by_tag"):
            ctx = await self._memory.search_by_tag(tag=f"file:{file_id}", top_k=5)
            ct = "\n".join(e.content for e in ctx)
        else:
            ct = ""
        if not ct:
            return "No stored document context was found for this file. Upload the file again to start a Q&A session."
        answer,_=await self._models.infer(
            self._router.select_model(TaskType.DOCUMENT),
            f"Context:\n{ct}\n\nQuestion: {question}\nAnswer:")
        if self._looks_degraded_answer(answer):
            return self._fallback_file_answer(file_id, ct, question)
        return answer

    def _build_prompt(self,prompt,task_type,context,rag_ctx="",enriched="",pa=""):
        sys=self._personality_cfg.system_prompt+(f" {pa}" if pa else "")
        hint={TaskType.CODE:"\n[Provide clean code]",TaskType.MATH:"\n[Show reasoning]",
              TaskType.DOCUMENT:"\n[Cite sources]",TaskType.SEARCH:"\n[Use retrieved facts]"}.get(task_type,"")
        hist="".join(f"User: {t.get('user','')}\nAssistant: {t.get('assistant','')}\n" for t in context[-6:])
        parts=[sys,hint]
        if enriched:
            parts.append(enriched)
        if hist:
            parts.append(hist)
        if rag_ctx:
            parts.append(rag_ctx)
        parts.append(f"User: {prompt}\nAssistant:")
        return "\n".join(p for p in parts if p)

    async def _extract_file_text(self,filename,data):
        ext=filename.rsplit(".",1)[-1].lower()
        try:
            if ext=="pdf":
                import pdfplumber,io
                with pdfplumber.open(io.BytesIO(data)) as pdf:
                    return "\n".join(p.extract_text() or "" for p in pdf.pages[:10])
            if ext=="docx":
                import docx,io
                return "\n".join(p.text for p in docx.Document(io.BytesIO(data)).paragraphs)
            if ext in("txt","py","md"):
                return data.decode("utf-8",errors="replace")
        except Exception as e:
            logger.warning("File extract failed",ext=ext,error=str(e))
        return f"[Cannot extract from {filename}]"

    @staticmethod
    def _looks_degraded_answer(text: str) -> bool:
        lowered = text.lower()
        return "degraded model mode" in lowered or "server is healthy" in lowered

    @staticmethod
    def _fallback_file_answer(filename: str, text: str, question: str) -> str:
        if text.startswith("[Cannot extract"):
            return text

        cleaned_lines = [line.strip() for line in text.splitlines() if line.strip()]
        snippet = " ".join(cleaned_lines[:4])[:500] if cleaned_lines else text[:500]
        question_lower = question.lower()

        if any(token in question_lower for token in ("summarize", "summary", "summarise", "overview")):
            return f"Summary of {filename}: {snippet}" if snippet else f"{filename} was uploaded successfully."

        if any(token in question_lower for token in ("what", "which", "who", "when", "where", "why", "how")):
            return (
                f"Based on the extracted content from {filename}, the most relevant text is: {snippet}"
                if snippet
                else f"{filename} was uploaded, but no readable text was extracted."
            )

        return f"Document processed for {filename}. Key content: {snippet}" if snippet else f"{filename} was uploaded successfully."

    def _active_features(self):
        return [k for k,v in {
            "F1:Reflection":self._reflection,"F2:Learning":self._learning,
            "F3:AdvMemory":self._uni_memory,"F4:Parallel":self._parallel,
            "F5:RAG++":self._rag,"F6:SelfImprove":self._improve,
            "F7:Registry":self._registry,"F8:AISecurity":self._ai_security,
            "F9:Multimodal":self._fusion,"F10:TaskQueue":self._task_queue,
            "F11:Personality":self._personality,"V11-S1:RLHF":self._rlhf,
            "V11-S2:Tools":self._tools,"V11-S3:Consensus":self._consensus,
        }.items() if v]

Orchestrator=OrchestratorV11
