"""SuperAI V11 — backend/app/dependencies.py — Full DI container."""
from __future__ import annotations
from loguru import logger
from backend.config.settings import settings


class ServiceContainer:
    def __init__(self):
        # V9 core
        self._orchestrator=None; self._agent_service=None; self._memory_service=None
        self._voice_service=None; self._vision_service=None; self._monitoring_service=None
        self._security_engine=None; self._task_router=None; self._model_loader=None
        self._coordinator=None; self._feedback_service=None
        # V10 features
        self._reflection_engine=None; self._learning_pipeline=None; self._unified_memory=None
        self._parallel_executor=None; self._rag_engine=None; self._self_improvement=None
        self._model_registry=None; self._ai_security=None; self._fusion_engine=None
        self._task_queue=None; self._personality_engine=None
        # V11 new
        self._rlhf_pipeline=None; self._tool_engine=None; self._consensus_engine=None
        # V12 new
        self._workflow_engine=None; self._skill_registry=None
        self._code_review_engine=None; self._debugger=None
        # V12 context engineering
        self._context_compressor=None; self._llm_judge=None; self._bdi_engine=None

    async def startup(self):
        from backend.services.monitoring_service import MonitoringService
        from backend.memory.memory_v9            import MemoryServiceV9
        from backend.services.agent_service      import AgentService
        from backend.services.voice_service      import VoiceService
        from backend.services.vision_service     import VisionService
        from backend.services.feedback_service   import FeedbackService
        from backend.core.security               import SecurityEngine
        from backend.core.task_router            import TaskRouter
        from backend.models.loader               import ModelLoader
        from backend.agents.coordinator          import AgentCoordinator

        logger.info("SuperAI V11 starting — core services…")
        self._monitoring_service = MonitoringService()
        self._model_loader       = ModelLoader(cfg=settings.models)
        self._security_engine    = SecurityEngine(cfg=settings.security)
        self._memory_service     = MemoryServiceV9(cfg=settings.memory)
        self._task_router        = TaskRouter(routing_cfg=settings.models.routing)
        self._coordinator        = AgentCoordinator(context_ttl=settings.agent.context_bus_ttl)
        self._feedback_service   = FeedbackService(cfg=settings.feedback)
        await self._memory_service.init()
        await self._feedback_service.init()
        self._voice_service  = VoiceService(cfg=settings.voice)
        self._vision_service = VisionService(model_loader=self._model_loader, cfg=settings.models)
        self._agent_service  = AgentService(model_loader=self._model_loader,
            memory_svc=self._memory_service, coordinator=self._coordinator, cfg=settings.agent)
        logger.info("V11 core ready ✓")

        await self._load_v10_features()
        await self._load_v11_features()
        await self._load_v12_features()

        from backend.core.orchestrator import OrchestratorV11
        self._orchestrator = OrchestratorV11(
            model_loader=self._model_loader, memory_svc=self._memory_service,
            agent_svc=self._agent_service, voice_svc=self._voice_service,
            vision_svc=self._vision_service, security_engine=self._security_engine,
            task_router=self._task_router, monitoring_svc=self._monitoring_service,
            personality_cfg=settings.personality,
            reflection_engine=self._reflection_engine, learning_pipeline=self._learning_pipeline,
            unified_memory=self._unified_memory, parallel_executor=self._parallel_executor,
            rag_engine=self._rag_engine, self_improvement=self._self_improvement,
            model_registry=self._model_registry, ai_security=self._ai_security,
            fusion_engine=self._fusion_engine, task_queue=self._task_queue,
            personality_engine=self._personality_engine,
            rlhf_pipeline=self._rlhf_pipeline,
            tool_engine=self._tool_engine,
            consensus_engine=self._consensus_engine,
        )
        logger.info("SuperAI V11 fully operational ✓")

    async def _load_v10_features(self):
        cfg = settings
        _try = self._try_load

        await _try("F1 Reflection",    self._load_reflection,   cfg)
        await _try("F2 Learning",      self._load_learning,     cfg)
        await _try("F3 AdvMemory",     self._load_adv_memory,   cfg)
        await _try("F4 ParallelAgent", self._load_parallel,     cfg)
        await _try("F5 RAG++",         self._load_rag,          cfg)
        await _try("F6 SelfImprove",   self._load_self_improve, cfg)
        await _try("F7 Registry",      self._load_registry,     cfg)
        await _try("F8 AISecurity",    self._load_ai_security,  cfg)
        await _try("F9 Multimodal",    self._load_fusion,       cfg)
        await _try("F10 TaskQueue",    self._load_task_queue,   cfg)
        await _try("F11 Personality",  self._load_personality,  cfg)

    async def _load_v11_features(self):
        cfg = settings
        await self._try_load("V11-S1 RLHF",      self._load_rlhf,      cfg)
        await self._try_load("V11-S2 Tools",      self._load_tools,     cfg)
        await self._try_load("V11-S3 Consensus",  self._load_consensus, cfg)

    async def _load_v12_features(self):
        cfg = settings
        await self._try_load("V12-S4 Workflow",    self._load_workflow,     cfg)
        await self._try_load("V12-S5 Skills",      self._load_skills,       cfg)
        await self._try_load("V12-S5 CodeReview",  self._load_code_review,  cfg)
        await self._try_load("V12-S5 Debugging",   self._load_debugging,    cfg)
        await self._try_load("V12-S6 Context",     self._load_context,      cfg)
        await self._try_load("V12-S6 Evaluation",  self._load_evaluation,   cfg)
        await self._try_load("V12-S6 Cognitive",   self._load_cognitive,    cfg)

    async def _try_load(self, name, fn, cfg):
        try:
            await fn(cfg)
            logger.info(f"{name} ✓")
        except Exception as e:
            logger.warning(f"{name} skipped", error=str(e))

    # ── V10 loaders ────────────────────────────────────────────────
    async def _load_reflection(self, cfg):
        from backend.intelligence.reflection_engine import ReflectionEngine
        self._reflection_engine = ReflectionEngine(cfg=cfg.reflection, model_loader=self._model_loader)

    async def _load_learning(self, cfg):
        from backend.intelligence.learning_pipeline import LearningPipeline
        self._learning_pipeline = LearningPipeline(cfg=cfg.learning,
            feedback_db=cfg.feedback.store_path, conv_db=cfg.memory.db_path)
        await self._learning_pipeline.start_scheduler()

    async def _load_adv_memory(self, cfg):
        from backend.memory.advanced_memory import EpisodicMemory,SemanticGraph,UnifiedMemoryRetriever
        adv=cfg.advanced_memory
        ep=EpisodicMemory(db_path=adv.episodic_db_path); await ep.init()
        gr=SemanticGraph(graph_path=adv.semantic_graph_path,max_nodes=adv.max_graph_nodes)
        self._unified_memory=UnifiedMemoryRetriever(
            base_memory=self._memory_service,episodic=ep,graph=gr,
            emotional_tagging=adv.emotional_tagging)

    async def _load_parallel(self, cfg):
        from backend.agents.parallel_executor import ParallelAgentExecutor
        self._parallel_executor=ParallelAgentExecutor(model_loader=self._model_loader,cfg=cfg.parallel_agents)

    async def _load_rag(self, cfg):
        from backend.knowledge.rag_engine import RAGEngine
        self._rag_engine=RAGEngine(cfg=cfg.rag)

    async def _load_self_improve(self, cfg):
        from backend.intelligence.self_improvement import SelfImprovementEngine
        self._self_improvement=SelfImprovementEngine(cfg=cfg.self_improvement,model_loader=self._model_loader)
        await self._self_improvement.init()

    async def _load_registry(self, cfg):
        from backend.intelligence.model_registry import ModelRegistry
        self._model_registry=ModelRegistry(cfg=cfg.model_registry,model_loader=self._model_loader)
        for task,mid in cfg.models.routing.items():
            if mid: self._model_registry.register(model_id=mid,source="huggingface",tasks=[task])

    async def _load_ai_security(self, cfg):
        from backend.security_ai.ai_security import AISecurityEngine
        self._ai_security=AISecurityEngine(cfg=cfg.ai_security)
        await self._ai_security.init()

    async def _load_fusion(self, cfg):
        from backend.multimodal.fusion_engine import MultimodalFusionEngine
        self._fusion_engine=MultimodalFusionEngine(cfg=cfg.multimodal,
            vision_svc=self._vision_service,voice_svc=self._voice_service)

    async def _load_task_queue(self, cfg):
        from backend.distributed.task_queue import create_task_queue
        self._task_queue=create_task_queue(cfg.distributed)
        await self._task_queue.start()

    async def _load_personality(self, cfg):
        from backend.personality.personality_engine import PersonalityEngine
        self._personality_engine=PersonalityEngine(cfg=cfg.personality)

    # ── V11 loaders ────────────────────────────────────────────────
    async def _load_rlhf(self, cfg):
        from backend.rlhf.rlhf_pipeline import RLHFPipeline
        self._rlhf_pipeline=RLHFPipeline(cfg.rlhf,
            feedback_db=cfg.feedback.store_path, conv_db=cfg.memory.db_path)
        await self._rlhf_pipeline.init()

    async def _load_tools(self, cfg):
        from backend.tools.tool_executor      import create_tool_registry
        from backend.tools.tool_calling_engine import ToolCallingEngine
        registry        = create_tool_registry()
        use_llm         = cfg.tools.use_llm_selection if hasattr(cfg,"tools") else False
        model_for_tools = list(cfg.models.routing.values())[0] if cfg.models.routing else ""
        self._tool_engine = ToolCallingEngine(registry, self._model_loader,
                                               model_for_tools, use_llm)

    async def _load_consensus(self, cfg):
        consensus_cfg = getattr(cfg,"consensus",None)
        if not consensus_cfg: return
        models = getattr(consensus_cfg,"models",[])
        if len(models) < 2: return
        from backend.consensus.consensus_engine import ConsensusEngine, VotingStrategy
        self._consensus_engine = ConsensusEngine(
            loader=self._model_loader, model_names=models,
            strategy=VotingStrategy(getattr(consensus_cfg,"strategy","auto")),
            conflict_threshold=getattr(consensus_cfg,"conflict_threshold",0.30),
            use_meta_evaluator=getattr(consensus_cfg,"use_meta_evaluator",False),
            timeout_s=getattr(consensus_cfg,"timeout_s",60))

    # ── V12 loaders ────────────────────────────────────────────────
    async def _load_workflow(self, cfg):
        from backend.workflow.engine import WorkflowEngine
        wf_cfg = getattr(cfg, "workflow", None)
        max_wf = getattr(wf_cfg, "max_active_workflows", 5) if wf_cfg else 5
        self._workflow_engine = WorkflowEngine(
            model_loader=self._model_loader,
            parallel_executor=self._parallel_executor,
            max_workflows=max_wf)

    async def _load_skills(self, cfg):
        from backend.skills.skill_registry import SkillRegistry
        sk_cfg = getattr(cfg, "skills", None)
        skills_dir = getattr(sk_cfg, "skills_dir", "backend/skills/builtin/") if sk_cfg else ""
        self._skill_registry = SkillRegistry(skills_dir=skills_dir, auto_load=bool(skills_dir))

    async def _load_code_review(self, cfg):
        from backend.code_review.code_review import CodeReviewEngine
        self._code_review_engine = CodeReviewEngine(model_loader=self._model_loader)

    async def _load_debugging(self, cfg):
        from backend.debugging.debugger import SystematicDebugger
        self._debugger = SystematicDebugger(model_loader=self._model_loader)

    async def _load_context(self, cfg):
        from backend.context.context_compressor import ContextCompressor
        ctx_cfg = getattr(cfg, "context", None)
        max_tok = getattr(ctx_cfg, "max_tokens", 3000) if ctx_cfg else 3000
        self._context_compressor = ContextCompressor(model_loader=self._model_loader, max_tokens=max_tok)

    async def _load_evaluation(self, cfg):
        from backend.evaluation.llm_judge import LLMJudge
        self._llm_judge = LLMJudge(model_loader=self._model_loader)

    async def _load_cognitive(self, cfg):
        from backend.cognitive.bdi_engine import BDICognitiveEngine
        self._bdi_engine = BDICognitiveEngine(model_loader=self._model_loader)

    # ── Shutdown ────────────────────────────────────────────────────
    async def shutdown(self):
        if self._memory_service:   await self._memory_service.close()
        if self._feedback_service: await self._feedback_service.close()
        if self._learning_pipeline: await self._learning_pipeline.stop_scheduler()
        if self._self_improvement: await self._self_improvement.close()
        if self._task_queue:       await self._task_queue.stop()
        if self._rlhf_pipeline:    await self._rlhf_pipeline.stop()
        if self._unified_memory and hasattr(self._unified_memory,"_graph"):
            self._unified_memory._graph.save()
        logger.info("V11 shutdown complete")

    # ── Getters ─────────────────────────────────────────────────────
    def _get(self,a,n):
        v=getattr(self,a)
        if v is None: raise RuntimeError(f"{n} not initialised")
        return v

    @property
    def orchestrator(self):       return self._get("_orchestrator","Orchestrator")
    @property
    def agent_service(self):      return self._get("_agent_service","AgentService")
    @property
    def memory_service(self):     return self._get("_memory_service","MemoryService")
    @property
    def voice_service(self):      return self._get("_voice_service","VoiceService")
    @property
    def vision_service(self):     return self._get("_vision_service","VisionService")
    @property
    def monitoring_service(self): return self._get("_monitoring_service","MonitoringService")
    @property
    def security_engine(self):    return self._get("_security_engine","SecurityEngine")
    @property
    def feedback_service(self):   return self._get("_feedback_service","FeedbackService")
    @property
    def coordinator(self):        return self._get("_coordinator","AgentCoordinator")
    # Optional V10
    @property
    def reflection_engine(self):  return self._reflection_engine
    @property
    def learning_pipeline(self):  return self._learning_pipeline
    @property
    def rag_engine(self):         return self._rag_engine
    @property
    def self_improvement(self):   return self._self_improvement
    @property
    def model_registry(self):     return self._model_registry
    @property
    def ai_security(self):        return self._ai_security
    @property
    def parallel_executor(self):  return self._parallel_executor
    @property
    def personality_engine(self): return self._personality_engine
    @property
    def task_queue(self):         return self._task_queue
    # Optional V11
    @property
    def rlhf_pipeline(self):      return self._rlhf_pipeline
    @property
    def tool_engine(self):        return self._tool_engine
    @property
    def consensus_engine(self):   return self._consensus_engine
    # Optional V12
    @property
    def workflow_engine(self):    return self._workflow_engine
    @property
    def skill_registry(self):    return self._skill_registry
    @property
    def code_review_engine(self): return self._code_review_engine
    @property
    def debugger(self):           return self._debugger
    @property
    def context_compressor(self): return self._context_compressor
    @property
    def llm_judge(self):          return self._llm_judge
    @property
    def bdi_engine(self):         return self._bdi_engine


container = ServiceContainer()

def get_orchestrator():       return container.orchestrator
def get_agent_service():      return container.agent_service
def get_memory_service():     return container.memory_service
def get_voice_service():      return container.voice_service
def get_vision_service():     return container.vision_service
def get_monitoring_service(): return container.monitoring_service
def get_security_engine():    return container.security_engine
def get_feedback_service():   return container.feedback_service
def get_coordinator():        return container.coordinator
def get_reflection_engine():  return container.reflection_engine
def get_learning_pipeline():  return container.learning_pipeline
def get_rag_engine():         return container.rag_engine
def get_self_improvement():   return container.self_improvement
def get_model_registry():     return container.model_registry
def get_ai_security():        return container.ai_security
def get_parallel_executor():  return container.parallel_executor
def get_personality_engine(): return container.personality_engine
def get_task_queue():         return container.task_queue
def get_rlhf_pipeline():      return container.rlhf_pipeline
def get_tool_engine():        return container.tool_engine
def get_consensus_engine():   return container.consensus_engine
def get_workflow_engine():    return container.workflow_engine
def get_skill_registry():     return container.skill_registry
def get_code_review_engine(): return container.code_review_engine
def get_debugger():           return container.debugger
def get_context_compressor(): return container.context_compressor
def get_llm_judge():          return container.llm_judge
def get_bdi_engine():         return container.bdi_engine
