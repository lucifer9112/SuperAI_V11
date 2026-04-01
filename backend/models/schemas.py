"""SuperAI V11 - backend/models/schemas.py - Shared Pydantic schemas."""
from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SchemaModel(BaseModel):
    model_config = ConfigDict(protected_namespaces=())


class APIResponse(SchemaModel):
    success: bool = True
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    data: Optional[Any] = None
    error: Optional[str] = None
    meta: Optional[Dict] = None

    def __init__(self, **data):
        if data.get("error"):
            data.setdefault("success", False)
        super().__init__(**data)


class TaskType(str, Enum):
    CHAT = "chat"
    CODE = "code"
    MATH = "math"
    SEARCH = "search"
    DOCUMENT = "document"
    AGENT = "agent"
    VISION = "vision"
    VOICE = "voice"


class ChatRequest(SchemaModel):
    prompt: str
    session_id: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 512
    force_model: Optional[str] = None
    force_task: Optional[TaskType] = None
    stream: bool = False


class ChatResponse(SchemaModel):
    answer: str
    session_id: str
    task_type: str
    model_used: str
    tokens_used: int
    latency_ms: float
    response_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])


class AgentRunRequest(SchemaModel):
    goal: str
    session_id: Optional[str] = None
    autonomy_level: int = 2
    max_iterations: int = 15
    tools: List[str] = []
    share_context: bool = True


class AgentStep(SchemaModel):
    step: int
    action: str
    thought: str = ""
    result: str
    success: bool = True


class AgentRunResponse(SchemaModel):
    agent_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    goal: str
    session_id: str = ""
    status: str = "completed"
    steps: List[AgentStep] = []
    final_answer: Optional[str] = None
    iterations: int = 0


class MemoryEntry(SchemaModel):
    id: str
    content: str
    score: float = 0.0
    priority: float = 1.0
    decay: float = 1.0
    timestamp: float = Field(default_factory=time.time)
    source: str = "conversation"


class MemorySearchRequest(SchemaModel):
    query: str
    session_id: Optional[str] = None
    top_k: int = 5


class MemorySearchResponse(SchemaModel):
    entries: List[MemoryEntry] = []
    query: str = ""
    total_found: int = 0


class MemoryStoreRequest(SchemaModel):
    content: str
    session_id: Optional[str] = None
    tags: List[str] = []
    priority: float = 1.0


class TTSRequest(SchemaModel):
    text: str
    engine: Optional[str] = None
    speed: float = 1.0


class STTResponse(SchemaModel):
    transcript: str
    language: str = "en"
    confidence: float = 0.0


class VisionRequest(SchemaModel):
    image_base64: str
    question: str = "Describe this image."
    session_id: Optional[str] = None


class VisionResponse(SchemaModel):
    description: str


class CodeAction(str, Enum):
    GENERATE = "generate"
    DEBUG = "debug"
    EXPLAIN = "explain"
    REVIEW = "review"
    OPTIMIZE = "optimize"
    TEST = "test"


class CodeRequest(SchemaModel):
    action: CodeAction = CodeAction.GENERATE
    language: str = "python"
    code: str = ""
    description: str = ""
    session_id: Optional[str] = None


class CodeResponse(SchemaModel):
    result: str
    action: str
    language: str


class FileProcessResponse(SchemaModel):
    file_id: str = ""
    filename: str
    file_type: str
    summary: str
    content: str = ""


class FeedbackRequest(SchemaModel):
    response_id: str
    score: int
    comment: str = ""
    session_id: Optional[str] = None


class FeedbackResponse(SchemaModel):
    feedback_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    response_id: str
    score: int
    recorded: bool = True


class SystemStatusResponse(SchemaModel):
    status: str
    version: str
    environment: str = "development"
    uptime_s: float = 0.0
    cpu_pct: float = 0.0
    ram_pct: float = 0.0
    gpu_info: Optional[str] = None
    models_loaded: List[str] = []
    requests_total: int = 0
    avg_latency_ms: float = 0.0
    feedback_count: int = 0


class RLHFDPORequest(SchemaModel):
    model_name: str = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
    epochs: int = 2
    beta: float = 0.1
    lr: float = 1e-5


class RLHFGRPORequest(SchemaModel):
    model_name: str
    prompts: List[str]
    epochs: int = 2


class RLHFTrainRunResponse(SchemaModel):
    run_id: str
    method: str
    status: str
    metrics: Dict[str, Any] = {}
    checkpoint: Optional[str] = None


class ToolInfo(SchemaModel):
    name: str
    description: str
    category: str
    safe: bool


class ToolCallRequest(SchemaModel):
    prompt: str
    autonomy_level: int = 2
    max_tools: int = 3


class ToolExecuteRequest(SchemaModel):
    tool_name: str
    arguments: Dict[str, Any] = {}


class ToolResultSchema(SchemaModel):
    tool_name: str
    success: bool
    output: str
    error: Optional[str] = None
    exec_ms: float = 0.0


class ToolCallResponse(SchemaModel):
    tools_used: List[str]
    tool_results: List[ToolResultSchema] = []
    enriched_prompt: str
    total_ms: float


class ConsensusRequest(SchemaModel):
    prompt: str
    max_tokens: int = 256
    temperature: float = 0.7
    strategy: str = "auto"


class ModelVoteResult(SchemaModel):
    model_name: str
    quality: float
    latency_ms: float
    error: Optional[str] = None


class ConsensusResponse(SchemaModel):
    final_answer: str
    winner_model: str
    strategy: str
    agreement: float
    conflict: bool
    latency_ms: float
    run_id: str
    all_responses: List[ModelVoteResult] = []
