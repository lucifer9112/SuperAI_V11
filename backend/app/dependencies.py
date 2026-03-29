"""Dependency container for the simplified SuperAI V11 runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from backend.config.settings import settings


@dataclass
class ReflectionConfig:
    enabled: bool = True
    min_confidence_threshold: float = 0.6
    max_reflection_rounds: int = 2
    reflection_timeout_s: int = 30


class ServiceContainer:
    def __init__(self) -> None:
        self._master_controller = None
        self._model_loader = None
        self._memory_service = None
        self._security_engine = None
        self._monitoring_service = None
        self._orchestrator = None

    async def startup(self) -> None:
        mode_label = "MINIMAL" if settings.is_minimal else "ADVANCED"
        logger.info("SuperAI runtime startup", mode=mode_label)

        from backend.controllers.master_controller import MasterController
        from backend.core.security import SecurityEngine
        from backend.models.loader import ModelLoader
        from backend.services.monitoring_service import MonitoringService
        from backend.services.simple_memory_service import SimpleMemoryService

        self._monitoring_service = MonitoringService()
        self._model_loader = ModelLoader(cfg=settings.models)
        self._security_engine = SecurityEngine(cfg=settings.security)

        if settings.memory.enabled:
            self._memory_service = SimpleMemoryService(cfg=settings.memory)
            await self._memory_service.init()

        self._master_controller = MasterController(
            model_loader=self._model_loader,
            memory_svc=self._memory_service,
            security_engine=self._security_engine,
            monitoring_svc=self._monitoring_service,
        )

        if not settings.is_minimal:
            await self._load_advanced_features()
            self._wire_orchestrator()

        logger.info(
            "SuperAI runtime ready",
            mode=settings.current_mode,
            active_features=list(settings.active_features.keys()),
        )

    async def _load_advanced_features(self) -> None:
        enabled = settings.active_features
        loaders = [
            ("enable_reflection", "Reflection", self._load_reflection),
            ("enable_learning", "Learning", self._load_learning),
            ("enable_advanced_memory", "AdvancedMemory", self._load_adv_memory),
            ("enable_parallel_agents", "ParallelAgents", self._load_parallel),
            ("enable_rag", "RAG", self._load_rag),
            ("enable_self_improvement", "SelfImprovement", self._load_self_improve),
            ("enable_model_registry", "ModelRegistry", self._load_registry),
            ("enable_ai_security", "AISecurity", self._load_ai_security),
            ("enable_multimodal", "Multimodal", self._load_fusion),
            ("enable_distributed", "Distributed", self._load_distributed),
            ("enable_personality", "Personality", self._load_personality),
            ("enable_rlhf", "RLHF", self._load_rlhf),
            ("enable_tools", "Tools", self._load_tools),
            ("enable_consensus", "Consensus", self._load_consensus),
            ("enable_workflow", "Workflow", self._load_workflow),
            ("enable_skills", "Skills", self._load_skills),
            ("enable_code_review", "CodeReview", self._load_code_review),
            ("enable_debugging", "Debugging", self._load_debugging),
            ("enable_context", "Context", self._load_context),
            ("enable_judge", "Judge", self._load_judge),
            ("enable_cognitive", "Cognitive", self._load_cognitive),
        ]
        for flag, label, fn in loaders:
            if enabled.get(flag):
                await self._try_load(label, fn)

    async def _try_load(self, name: str, fn) -> None:
        try:
            await fn()
            logger.info("Advanced module loaded", module=name)
        except Exception as exc:
            logger.warning("Advanced module skipped", module=name, reason=str(exc))

    async def _load_reflection(self) -> None:
        from backend.intelligence.reflection_engine import ReflectionEngine

        self._reflection_engine = ReflectionEngine(cfg=ReflectionConfig(), model_loader=self._model_loader)

    async def _load_learning(self) -> None:
        from backend.intelligence.learning_pipeline import LearningPipeline

        feedback_db, conv_db = self._db_paths()
        self._learning_pipeline = LearningPipeline(cfg=None, feedback_db=feedback_db, conv_db=conv_db)

    async def _load_adv_memory(self) -> None:
        data_dir = self._data_dir()
        from backend.memory.advanced_memory import EpisodicMemory, SemanticGraph, UnifiedMemoryRetriever

        episodic = EpisodicMemory(str(data_dir / "episodic.db"))
        await episodic.init()
        graph = SemanticGraph(str(data_dir / "knowledge_graph.json"))
        self._unified_memory = UnifiedMemoryRetriever(
            base_memory=self._memory_service,
            episodic=episodic,
            graph=graph,
            emotional_tagging=True,
        )

    async def _load_parallel(self) -> None:
        from backend.agents.parallel_executor import ParallelAgentExecutor

        self._parallel_executor = ParallelAgentExecutor(model_loader=self._model_loader, cfg=None)

    async def _load_rag(self) -> None:
        from backend.knowledge.rag_engine import RAGEngine

        self._rag_engine = RAGEngine(cfg=None, monitoring=self._monitoring_service)

    async def _load_self_improve(self) -> None:
        from backend.intelligence.self_improvement import SelfImprovementEngine

        self._self_improvement = SelfImprovementEngine(cfg=None, model_loader=self._model_loader)
        await self._self_improvement.init()

    async def _load_registry(self) -> None:
        from backend.intelligence.model_registry import ModelRegistry

        self._model_registry = ModelRegistry(cfg=None, model_loader=self._model_loader)

    async def _load_ai_security(self) -> None:
        from backend.security_ai.ai_security import AISecurityEngine

        self._ai_security = AISecurityEngine(cfg=None, monitoring=self._monitoring_service)
        await self._ai_security.init()

    async def _load_fusion(self) -> None:
        from backend.multimodal.fusion_engine import MultimodalFusionEngine

        self._fusion_engine = MultimodalFusionEngine(cfg=None, vision_svc=None, voice_svc=None)

    async def _load_distributed(self) -> None:
        from backend.distributed.task_queue import create_task_queue

        self._task_queue = create_task_queue(None)
        await self._task_queue.start()

    async def _load_personality(self) -> None:
        from backend.personality.personality_engine import PersonalityEngine

        self._personality_engine = PersonalityEngine(cfg=None)

    async def _load_rlhf(self) -> None:
        from backend.rlhf.rlhf_pipeline import RLHFPipeline

        feedback_db, conv_db = self._db_paths()
        self._rlhf_pipeline = RLHFPipeline(
            None,
            feedback_db=feedback_db,
            conv_db=conv_db,
            monitoring=self._monitoring_service,
        )
        await self._rlhf_pipeline.init()

    async def _load_tools(self) -> None:
        from backend.tools.tool_executor import create_tool_registry
        from backend.tools.tool_calling_engine import ToolCallingEngine

        self._tool_engine = ToolCallingEngine(
            create_tool_registry(),
            self._model_loader,
            settings.models.primary,
            False,
            monitoring=self._monitoring_service,
        )

    async def _load_consensus(self) -> None:
        from backend.consensus.consensus_engine import ConsensusEngine

        self._consensus_engine = ConsensusEngine(loader=self._model_loader, model_names=[], strategy=None)

    async def _load_workflow(self) -> None:
        from backend.workflow.engine import WorkflowEngine

        self._workflow_engine = WorkflowEngine(
            model_loader=self._model_loader,
            parallel_executor=getattr(self, "_parallel_executor", None),
            max_workflows=5,
        )

    async def _load_skills(self) -> None:
        from backend.skills.skill_registry import SkillRegistry

        self._skill_registry = SkillRegistry(skills_dir="backend/skills/builtin/", auto_load=True)

    async def _load_code_review(self) -> None:
        from backend.code_review.code_review import CodeReviewEngine

        self._code_review_engine = CodeReviewEngine(model_loader=self._model_loader)

    async def _load_debugging(self) -> None:
        from backend.debugging.debugger import SystematicDebugger

        self._debugger = SystematicDebugger(model_loader=self._model_loader)

    async def _load_context(self) -> None:
        from backend.context.context_compressor import ContextCompressor

        self._context_compressor = ContextCompressor(model_loader=self._model_loader, max_tokens=3000)

    async def _load_judge(self) -> None:
        from backend.evaluation.llm_judge import LLMJudge

        self._llm_judge = LLMJudge(model_loader=self._model_loader)

    async def _load_cognitive(self) -> None:
        from backend.cognitive.bdi_engine import BDICognitiveEngine

        self._bdi_engine = BDICognitiveEngine(model_loader=self._model_loader)

    async def shutdown(self) -> None:
        if self._memory_service:
            await self._memory_service.close()
        if getattr(self, "_unified_memory", None):
            episodic = getattr(self._unified_memory, "_episodic", None)
            if episodic:
                await episodic.close()
            graph = getattr(self._unified_memory, "_graph", None)
            if graph and hasattr(graph, "save"):
                graph.save()
        if getattr(self, "_self_improvement", None):
            await self._self_improvement.close()
        if getattr(self, "_task_queue", None):
            await self._task_queue.stop()
        if getattr(self, "_rlhf_pipeline", None):
            await self._rlhf_pipeline.stop()
        if getattr(self, "_ai_security", None):
            await self._ai_security.close()
        logger.info("SuperAI runtime shutdown complete")

    def _get(self, attr: str, name: str):
        value = getattr(self, attr, None)
        if value is None:
            raise RuntimeError(f"{name} not initialized")
        return value

    def _data_dir(self) -> Path:
        db_path = Path(settings.memory.db_path)
        return db_path.parent if db_path.parent != Path(".") else Path("data")

    def _db_paths(self) -> tuple[str, str]:
        conv_db = Path(settings.memory.db_path)
        feedback_db = conv_db.with_name("feedback.db")
        return str(feedback_db), str(conv_db)

    def _wire_orchestrator(self) -> None:
        from backend.core.orchestrator import OrchestratorV11
        from backend.core.task_router import TaskRouter

        task_router = TaskRouter()
        self._orchestrator = OrchestratorV11(
            model_loader=self._model_loader,
            memory_svc=self._memory_service,
            agent_svc=getattr(self, "_coordinator", None),
            voice_svc=getattr(self, "_voice_service", None),
            vision_svc=getattr(self, "_vision_service", None),
            security_engine=self._security_engine,
            task_router=task_router,
            monitoring_svc=self._monitoring_service,
            personality_cfg=settings.personality,
            reflection_engine=getattr(self, "_reflection_engine", None),
            learning_pipeline=getattr(self, "_learning_pipeline", None),
            unified_memory=getattr(self, "_unified_memory", None),
            parallel_executor=getattr(self, "_parallel_executor", None),
            rag_engine=getattr(self, "_rag_engine", None),
            self_improvement=getattr(self, "_self_improvement", None),
            model_registry=getattr(self, "_model_registry", None),
            ai_security=getattr(self, "_ai_security", None),
            fusion_engine=getattr(self, "_fusion_engine", None),
            task_queue=getattr(self, "_task_queue", None),
            personality_engine=getattr(self, "_personality_engine", None),
            rlhf_pipeline=getattr(self, "_rlhf_pipeline", None),
            tool_engine=getattr(self, "_tool_engine", None),
            consensus_engine=getattr(self, "_consensus_engine", None),
        )
        setattr(self._master_controller, "_orchestrator", self._orchestrator)
        logger.info("Advanced orchestrator wired")

    @property
    def master_controller(self):
        return self._get("_master_controller", "MasterController")

    @property
    def model_loader(self):
        return self._get("_model_loader", "ModelLoader")

    @property
    def memory_service(self):
        return getattr(self, "_memory_service", None)

    @property
    def security_engine(self):
        return self._get("_security_engine", "SecurityEngine")

    @property
    def monitoring_service(self):
        return self._get("_monitoring_service", "MonitoringService")

    @property
    def orchestrator(self):
        return self._get("_orchestrator", "OrchestratorV11")


container = ServiceContainer()


def get_master_controller():
    return container.master_controller


def get_memory_service():
    return container.memory_service


def get_security_engine():
    return container.security_engine


def get_monitoring_service():
    return container.monitoring_service


def get_model_loader():
    return container.model_loader


def get_feedback_service():
    return None


def get_orchestrator():
    return _optional_get("_orchestrator")


def _optional_get(attr: str):
    return getattr(container, attr, None)


def get_learning_pipeline():
    return _optional_get("_learning_pipeline")


def get_reflection_engine():
    return _optional_get("_reflection_engine")


def get_self_improvement():
    return _optional_get("_self_improvement")


def get_model_registry():
    return _optional_get("_model_registry")


def get_task_queue():
    return _optional_get("_task_queue")


def get_tool_engine():
    return _optional_get("_tool_engine")


def get_rlhf_pipeline():
    return _optional_get("_rlhf_pipeline")


def get_context_compressor():
    return _optional_get("_context_compressor")


def get_consensus_engine():
    return _optional_get("_consensus_engine")


def get_bdi_engine():
    return _optional_get("_bdi_engine")


def get_llm_judge():
    return _optional_get("_llm_judge")


def get_debugger():
    return _optional_get("_debugger")


def get_agent_service():
    return _optional_get("_agent_service")


def get_coordinator():
    return _optional_get("_coordinator")


def get_rag_engine():
    return _optional_get("_rag_engine")


def get_personality_engine():
    return _optional_get("_personality_engine")


def get_ai_security():
    return _optional_get("_ai_security")


def get_code_review_engine():
    return _optional_get("_code_review_engine")


def get_skill_registry():
    return _optional_get("_skill_registry")


def get_voice_service():
    return _optional_get("_voice_service")


def get_vision_service():
    return _optional_get("_vision_service")


def get_workflow_engine():
    return _optional_get("_workflow_engine")
