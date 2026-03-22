"""SuperAI V11 — backend/config/settings.py — All 11 feature settings."""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR   = Path(__file__).parent.parent.parent
CONFIG_DIR = ROOT_DIR / "config"

def _yaml():
    p = CONFIG_DIR / "config.yaml"
    return yaml.safe_load(p.read_text()) if p.exists() else {}

_Y = _yaml()
def _y(s,k,d=None): return _Y.get(s,{}).get(k,d)

class ServerSettings(BaseSettings):
    model_config=SettingsConfigDict(env_prefix="SERVER__")
    host:str=Field(default_factory=lambda:_y("server","host","0.0.0.0"))
    port:int=Field(default_factory=lambda:_y("server","port",8000))
    environment:str=Field(default_factory=lambda:_y("server","environment","development"))
    reload:bool=Field(default_factory=lambda:_y("server","reload",False))
    workers:int=Field(default_factory=lambda:_y("server","workers",1))
    cors_origins:List[str]=Field(default_factory=lambda:_y("server","cors_origins",["*"]))

class ModelSettings(BaseSettings):
    model_config=SettingsConfigDict(env_prefix="MODELS__")
    device:str=Field(default_factory=lambda:_y("models","device","auto"))
    cache_size:int=Field(default_factory=lambda:_y("models","cache_size",2))
    idle_timeout:int=Field(default_factory=lambda:_y("models","idle_timeout",300))
    default_max_tokens:int=Field(default_factory=lambda:_y("models","default_max_tokens",512))
    default_temperature:float=Field(default_factory=lambda:_y("models","default_temperature",0.7))
    routing:Dict[str,str]=Field(default_factory=lambda:_y("models","routing",{}))

class MemorySettings(BaseSettings):
    model_config=SettingsConfigDict(env_prefix="MEMORY__")
    backend:str=Field(default_factory=lambda:_y("memory","backend","sqlite"))
    db_path:str=Field(default_factory=lambda:_y("memory","db_path","data/superai_v11.db"))
    vector_store:str=Field(default_factory=lambda:_y("memory","vector_store","faiss"))
    vector_db_path:str=Field(default_factory=lambda:_y("memory","vector_db_path","data/vector_db/"))
    embedding_model:str=Field(default_factory=lambda:_y("memory","embedding_model","BAAI/bge-small-en-v1.5"))
    max_history_turns:int=Field(default_factory=lambda:_y("memory","max_history_turns",50))
    context_window:int=Field(default_factory=lambda:_y("memory","context_window",10))
    top_k_retrieval:int=Field(default_factory=lambda:_y("memory","top_k_retrieval",5))
    chunk_size:int=Field(default_factory=lambda:_y("memory","chunk_size",512))
    chunk_overlap:int=Field(default_factory=lambda:_y("memory","chunk_overlap",64))
    priority_decay_days:int=Field(default_factory=lambda:_y("memory","priority_decay_days",30))
    max_memories_per_session:int=Field(default_factory=lambda:_y("memory","max_memories_per_session",200))
    high_priority_threshold:float=Field(default_factory=lambda:_y("memory","high_priority_threshold",0.8))

class VoiceSettings(BaseSettings):
    model_config=SettingsConfigDict(env_prefix="VOICE__")
    enabled:bool=Field(default_factory=lambda:_y("voice","enabled",False))
    stt_model:str=Field(default_factory=lambda:_y("voice","stt_model","base"))
    tts_engine:str=Field(default_factory=lambda:_y("voice","tts_engine","gtts"))
    tts_rate:int=Field(default_factory=lambda:_y("voice","tts_rate",175))
    tts_volume:float=Field(default_factory=lambda:_y("voice","tts_volume",0.9))
    sample_rate:int=Field(default_factory=lambda:_y("voice","sample_rate",16000))
    language:str=Field(default_factory=lambda:_y("voice","language","en"))
    vad_threshold:float=Field(default_factory=lambda:_y("voice","vad_threshold",0.3))

class SecuritySettings(BaseSettings):
    model_config=SettingsConfigDict(env_prefix="SECURITY__")
    enabled:bool=Field(default_factory=lambda:_y("security","enabled",True))
    prompt_injection_guard:bool=Field(default_factory=lambda:_y("security","prompt_injection_guard",True))
    output_filter:bool=Field(default_factory=lambda:_y("security","output_filter",True))
    bandit_scan:bool=Field(default_factory=lambda:_y("security","bandit_scan",False))
    risk_threshold:str=Field(default_factory=lambda:_y("security","risk_threshold","medium"))
    rate_limit_per_minute:int=Field(default_factory=lambda:_y("security","rate_limit_per_minute",60))
    max_upload_size_mb:int=Field(default_factory=lambda:_y("security","max_upload_size_mb",50))
    secret_key:str=Field(default="change-me",validation_alias="SECRET_KEY")

class AgentSettings(BaseSettings):
    model_config=SettingsConfigDict(env_prefix="AGENT__")
    max_iterations:int=Field(default_factory=lambda:_y("agent","max_iterations",15))
    default_autonomy_level:int=Field(default_factory=lambda:_y("agent","default_autonomy_level",2))
    tool_timeout:int=Field(default_factory=lambda:_y("agent","tool_timeout",30))
    shared_context_enabled:bool=Field(default_factory=lambda:_y("agent","shared_context_enabled",True))
    context_bus_ttl:int=Field(default_factory=lambda:_y("agent","context_bus_ttl",3600))

class FeedbackSettings(BaseSettings):
    model_config=SettingsConfigDict(env_prefix="FEEDBACK__")
    enabled:bool=Field(default_factory=lambda:_y("feedback","enabled",True))
    min_score:int=Field(default_factory=lambda:_y("feedback","min_score",1))
    max_score:int=Field(default_factory=lambda:_y("feedback","max_score",5))
    store_path:str=Field(default_factory=lambda:_y("feedback","store_path","data/feedback.db"))
    learning_threshold:int=Field(default_factory=lambda:_y("feedback","learning_threshold",10))

class LoggingSettings(BaseSettings):
    model_config=SettingsConfigDict(env_prefix="LOGGING__")
    level:str=Field(default_factory=lambda:_y("logging","level","INFO"))
    format:str=Field(default_factory=lambda:_y("logging","format","text"))
    file:str=Field(default_factory=lambda:_y("logging","file","logs/superai_v11.log"))
    rotation:str=Field(default_factory=lambda:_y("logging","rotation","10 MB"))
    retention:str=Field(default_factory=lambda:_y("logging","retention","30 days"))

class PersonalitySettings(BaseSettings):
    model_config=SettingsConfigDict(env_prefix="PERSONALITY__")
    name:str=Field(default_factory=lambda:_y("personality","name","SuperAI"))
    version:str=Field(default_factory=lambda:_y("personality","version","11.0"))
    tone:str=Field(default_factory=lambda:_y("personality","tone","professional"))
    enabled:bool=Field(default_factory=lambda:_y("personality","enabled",True))
    emotional_intelligence:bool=Field(default_factory=lambda:_y("personality","emotional_intelligence",True))
    user_adaptation:bool=Field(default_factory=lambda:_y("personality","user_adaptation",True))
    traits:Dict[str,float]=Field(default_factory=lambda:_y("personality","traits",{}))
    system_prompt:str=Field(default_factory=lambda:_y("personality","system_prompt","You are SuperAI V11."))

class ReflectionSettings(BaseSettings):
    model_config=SettingsConfigDict(env_prefix="REFLECTION__")
    enabled:bool=Field(default_factory=lambda:_y("reflection","enabled",True))
    min_confidence_threshold:float=Field(default_factory=lambda:_y("reflection","min_confidence_threshold",0.6))
    max_reflection_rounds:int=Field(default_factory=lambda:_y("reflection","max_reflection_rounds",2))
    reflection_timeout_s:int=Field(default_factory=lambda:_y("reflection","reflection_timeout_s",30))

class LearningSettings(BaseSettings):
    model_config=SettingsConfigDict(env_prefix="LEARNING__")
    enabled:bool=Field(default_factory=lambda:_y("learning","enabled",True))
    auto_dataset_generation:bool=Field(default_factory=lambda:_y("learning","auto_dataset_generation",True))
    min_quality_score:int=Field(default_factory=lambda:_y("learning","min_quality_score",4))
    dataset_path:str=Field(default_factory=lambda:_y("learning","dataset_path","data/training/"))
    lora_output_dir:str=Field(default_factory=lambda:_y("learning","lora_output_dir","data/lora_checkpoints/"))
    retrain_threshold:int=Field(default_factory=lambda:_y("learning","retrain_threshold",50))
    scheduler_interval_hours:int=Field(default_factory=lambda:_y("learning","scheduler_interval_hours",6))

class AdvancedMemorySettings(BaseSettings):
    model_config=SettingsConfigDict(env_prefix="ADV_MEMORY__")
    episodic_enabled:bool=Field(default_factory=lambda:_y("advanced_memory","episodic_enabled",True))
    semantic_graph_enabled:bool=Field(default_factory=lambda:_y("advanced_memory","semantic_graph_enabled",True))
    emotional_tagging:bool=Field(default_factory=lambda:_y("advanced_memory","emotional_tagging",True))
    episodic_db_path:str=Field(default_factory=lambda:_y("advanced_memory","episodic_db_path","data/episodic.db"))
    semantic_graph_path:str=Field(default_factory=lambda:_y("advanced_memory","semantic_graph_path","data/knowledge_graph.json"))
    emotion_labels:List[str]=Field(default_factory=lambda:_y("advanced_memory","emotion_labels",["positive","negative","neutral"]))
    max_graph_nodes:int=Field(default_factory=lambda:_y("advanced_memory","max_graph_nodes",10000))

class ParallelAgentSettings(BaseSettings):
    model_config=SettingsConfigDict(env_prefix="PARALLEL__")
    enabled:bool=Field(default_factory=lambda:_y("parallel_agents","enabled",True))
    max_concurrent_agents:int=Field(default_factory=lambda:_y("parallel_agents","max_concurrent_agents",4))
    specializations:List[str]=Field(default_factory=lambda:_y("parallel_agents","specializations",["research","coding","reasoning","planning"]))
    collaboration_rounds:int=Field(default_factory=lambda:_y("parallel_agents","collaboration_rounds",2))
    conflict_resolution:str=Field(default_factory=lambda:_y("parallel_agents","conflict_resolution","confidence"))
    tool_timeout:int=Field(default_factory=lambda:_y("agent","tool_timeout",30))

class RAGSettings(BaseSettings):
    model_config=SettingsConfigDict(env_prefix="RAG__")
    enabled:bool=Field(default_factory=lambda:_y("rag","enabled",True))
    web_retrieval:bool=Field(default_factory=lambda:_y("rag","web_retrieval",True))
    chunk_size:int=Field(default_factory=lambda:_y("rag","chunk_size",400))
    chunk_overlap:int=Field(default_factory=lambda:_y("rag","chunk_overlap",80))
    top_k_chunks:int=Field(default_factory=lambda:_y("rag","top_k_chunks",5))
    max_web_results:int=Field(default_factory=lambda:_y("rag","max_web_results",5))
    cache_ttl_s:int=Field(default_factory=lambda:_y("rag","cache_ttl_s",3600))

class SelfImprovementSettings(BaseSettings):
    model_config=SettingsConfigDict(env_prefix="IMPROVE__")
    enabled:bool=Field(default_factory=lambda:_y("self_improvement","enabled",True))
    failure_log_path:str=Field(default_factory=lambda:_y("self_improvement","failure_log_path","data/improvement_logs/"))
    analysis_interval_hours:int=Field(default_factory=lambda:_y("self_improvement","analysis_interval_hours",12))
    min_failures_to_analyze:int=Field(default_factory=lambda:_y("self_improvement","min_failures_to_analyze",5))
    auto_prompt_optimization:bool=Field(default_factory=lambda:_y("self_improvement","auto_prompt_optimization",True))
    improvement_db_path:str=Field(default_factory=lambda:_y("self_improvement","improvement_db_path","data/improvements.db"))

class ModelRegistrySettings(BaseSettings):
    model_config=SettingsConfigDict(env_prefix="REGISTRY__")
    enabled:bool=Field(default_factory=lambda:_y("model_registry","enabled",True))
    registry_path:str=Field(default_factory=lambda:_y("model_registry","registry_path","data/model_registry.json"))
    benchmark_on_load:bool=Field(default_factory=lambda:_y("model_registry","benchmark_on_load",False))
    auto_select_best:bool=Field(default_factory=lambda:_y("model_registry","auto_select_best",True))

class AISecuritySettings(BaseSettings):
    model_config=SettingsConfigDict(env_prefix="AI_SEC__")
    enabled:bool=Field(default_factory=lambda:_y("ai_security","enabled",True))
    anomaly_detection:bool=Field(default_factory=lambda:_y("ai_security","anomaly_detection",True))
    embedding_threat_model:bool=Field(default_factory=lambda:_y("ai_security","embedding_threat_model",True))
    threat_similarity_threshold:float=Field(default_factory=lambda:_y("ai_security","threat_similarity_threshold",0.82))
    block_on_anomaly:bool=Field(default_factory=lambda:_y("ai_security","block_on_anomaly",True))
    anomaly_log_path:str=Field(default_factory=lambda:_y("ai_security","anomaly_log_path","data/security_logs/"))

class MultimodalSettings(BaseSettings):
    model_config=SettingsConfigDict(env_prefix="MULTIMODAL__")
    enabled:bool=Field(default_factory=lambda:_y("multimodal","enabled",True))
    fusion_strategy:str=Field(default_factory=lambda:_y("multimodal","fusion_strategy","sequential"))
    text_weight:float=Field(default_factory=lambda:_y("multimodal","text_weight",0.6))
    image_weight:float=Field(default_factory=lambda:_y("multimodal","image_weight",0.25))
    audio_weight:float=Field(default_factory=lambda:_y("multimodal","audio_weight",0.15))

class DistributedSettings(BaseSettings):
    model_config=SettingsConfigDict(env_prefix="DISTRIBUTED__")
    enabled:bool=Field(default_factory=lambda:_y("distributed","enabled",False))
    task_queue:str=Field(default_factory=lambda:_y("distributed","task_queue","async"))
    max_workers:int=Field(default_factory=lambda:_y("distributed","max_workers",4))
    task_retention_s:int=Field(default_factory=lambda:_y("distributed","task_retention_s",3600))
    gpu_ids:List[int]=Field(default_factory=lambda:_y("distributed","gpu_ids",[0]))
    load_balance_strategy:str=Field(default_factory=lambda:_y("distributed","load_balance_strategy","round_robin"))

class AppSettings(BaseSettings):
    model_config=SettingsConfigDict(env_file=str(ROOT_DIR/".env"),
                                    env_file_encoding="utf-8",case_sensitive=False,extra="ignore")
    redis_url:str=Field(default="redis://localhost:6379/0",validation_alias="REDIS_URL")
    sentry_dsn:Optional[str]=Field(default=None,validation_alias="SENTRY_DSN")
    hf_token:Optional[str]=Field(default=None,validation_alias="HF_TOKEN")
    server:ServerSettings=Field(default_factory=ServerSettings)
    models:ModelSettings=Field(default_factory=ModelSettings)
    memory:MemorySettings=Field(default_factory=MemorySettings)
    voice:VoiceSettings=Field(default_factory=VoiceSettings)
    security:SecuritySettings=Field(default_factory=SecuritySettings)
    agent:AgentSettings=Field(default_factory=AgentSettings)
    feedback:FeedbackSettings=Field(default_factory=FeedbackSettings)
    logging:LoggingSettings=Field(default_factory=LoggingSettings)
    personality:PersonalitySettings=Field(default_factory=PersonalitySettings)
    reflection:ReflectionSettings=Field(default_factory=ReflectionSettings)
    learning:LearningSettings=Field(default_factory=LearningSettings)
    advanced_memory:AdvancedMemorySettings=Field(default_factory=AdvancedMemorySettings)
    parallel_agents:ParallelAgentSettings=Field(default_factory=ParallelAgentSettings)
    rag:RAGSettings=Field(default_factory=RAGSettings)
    self_improvement:SelfImprovementSettings=Field(default_factory=SelfImprovementSettings)
    model_registry:ModelRegistrySettings=Field(default_factory=ModelRegistrySettings)
    ai_security:AISecuritySettings=Field(default_factory=AISecuritySettings)
    multimodal:MultimodalSettings=Field(default_factory=MultimodalSettings)
    distributed:DistributedSettings=Field(default_factory=DistributedSettings)
    # V11
    rlhf:RLHFSettings=Field(default_factory=lambda: RLHFSettings())
    tools:ToolSettings=Field(default_factory=lambda: ToolSettings())
    consensus:ConsensusSettings=Field(default_factory=lambda: ConsensusSettings())

    @model_validator(mode="after")
    def validate_runtime_security(self):
        weak = {"change-me", "change-in-production", "changeme", "colab-v11-key", "colab-v10-secret"}
        env = (self.server.environment or "development").lower()
        if env not in {"development", "dev", "test"} and self.security.secret_key.strip().lower() in weak:
            raise ValueError("SECRET_KEY must be set to a strong non-default value outside development/test")
        return self


# ── V11 Settings ──────────────────────────────────────────────────

class RLHFSettings(BaseSettings):
    model_config=SettingsConfigDict(env_prefix="RLHF__")
    enabled:              bool  = Field(default_factory=lambda:_y("rlhf","enabled",True))
    rlhf_output_dir:      str   = Field(default_factory=lambda:_y("rlhf","rlhf_output_dir","data/rlhf_checkpoints/"))
    rlhf_log_db:          str   = Field(default_factory=lambda:_y("rlhf","rlhf_log_db","data/rlhf_logs.db"))
    rlhf_scheduler_hours: int   = Field(default_factory=lambda:_y("rlhf","rlhf_scheduler_hours",24))
    rlhf_min_pairs:       int   = Field(default_factory=lambda:_y("rlhf","rlhf_min_pairs",10))
    reward_model_path:    str   = Field(default_factory=lambda:_y("rlhf","reward_model_path","data/reward_model/reward_head.pt"))


class ToolSettings(BaseSettings):
    model_config=SettingsConfigDict(env_prefix="TOOLS__")
    enabled:                    bool = Field(default_factory=lambda:_y("tools","enabled",True))
    use_llm_selection:          bool = Field(default_factory=lambda:_y("tools","use_llm_selection",False))
    max_tools_per_query:        int  = Field(default_factory=lambda:_y("tools","max_tools_per_query",3))
    safe_tools_only_below_autonomy: int = Field(default_factory=lambda:_y("tools","safe_tools_only_below_autonomy",3))


class ConsensusSettings(BaseSettings):
    model_config=SettingsConfigDict(env_prefix="CONSENSUS__")
    enabled:             bool      = Field(default_factory=lambda:_y("consensus","enabled",False))
    models:              List[str] = Field(default_factory=lambda:_y("consensus","models",[]))
    strategy:            str       = Field(default_factory=lambda:_y("consensus","strategy","auto"))
    conflict_threshold:  float     = Field(default_factory=lambda:_y("consensus","conflict_threshold",0.30))
    use_meta_evaluator:  bool      = Field(default_factory=lambda:_y("consensus","use_meta_evaluator",False))
    timeout_s:           int       = Field(default_factory=lambda:_y("consensus","timeout_s",60))


AppSettings.model_rebuild()

@lru_cache(maxsize=1)
def get_settings()->AppSettings: return AppSettings()

settings=get_settings()
