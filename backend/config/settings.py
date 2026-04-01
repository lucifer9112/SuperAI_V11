"""Application settings for the simplified SuperAI V11 runtime."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).parent.parent.parent
CONFIG_DIR = ROOT_DIR / "config"


def _load_yaml() -> dict[str, Any]:
    path = CONFIG_DIR / "config.yaml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


_YAML_CONFIG = _load_yaml()


def _yaml_value(section: str, key: str, default: Any = None) -> Any:
    return _YAML_CONFIG.get(section, {}).get(key, default)


def _default_model_routing() -> dict[str, str]:
    primary = _yaml_value("models", "primary", "Qwen/Qwen2.5-0.5B-Instruct")
    base = {
        "chat": primary,
        "code": primary,
        "math": primary,
        "search": primary,
        "document": primary,
        "agent": primary,
        "voice": primary,
    }
    yaml_routing = _yaml_value("models", "routing", {}) or {}
    base.update(yaml_routing)
    return base


def _default_model_fallbacks() -> list[str]:
    configured = _yaml_value("models", "fallback_models", None)
    if configured:
        return list(configured)
    return ["sshleifer/tiny-gpt2"]


def _build_feature_gates() -> "FeatureGates":
    env_features = FeatureGates()
    merged = env_features.model_dump()
    for key, value in _YAML_CONFIG.get("features", {}).items():
        env_key = f"FEATURES__{key.upper()}"
        if env_key not in os.environ:
            merged[key] = value
    return FeatureGates(**merged)


class ServerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SERVER__")

    host: str = Field(default_factory=lambda: _yaml_value("server", "host", "0.0.0.0"))
    port: int = Field(default_factory=lambda: _yaml_value("server", "port", 8000))
    reload: bool = Field(default_factory=lambda: _yaml_value("server", "reload", False))
    workers: int = Field(default_factory=lambda: _yaml_value("server", "workers", 1))
    cors_origins: list[str] = Field(default_factory=lambda: _yaml_value("server", "cors_origins", ["*"]))
    environment: str = Field(
        default_factory=lambda: _yaml_value(
            "server",
            "environment",
            _YAML_CONFIG.get("app", {}).get("environment", "development"),
        )
    )


class ModelSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MODELS__")

    device: str = Field(default_factory=lambda: _yaml_value("models", "device", "auto"))
    cache_size: int = Field(default_factory=lambda: _yaml_value("models", "cache_size", 1))
    idle_timeout: int = Field(default_factory=lambda: _yaml_value("models", "idle_timeout", 300))
    load_timeout_s: int = Field(default_factory=lambda: _yaml_value("models", "load_timeout_s", 180))
    default_max_tokens: int = Field(default_factory=lambda: _yaml_value("models", "default_max_tokens", 512))
    default_temperature: float = Field(
        default_factory=lambda: _yaml_value("models", "default_temperature", 0.7)
    )
    primary: str = Field(
        default_factory=lambda: _yaml_value("models", "primary", "Qwen/Qwen2.5-0.5B-Instruct")
    )
    routing: dict[str, str] = Field(default_factory=_default_model_routing)
    fallback_models: list[str] = Field(default_factory=_default_model_fallbacks)
    consensus_models: list[str] = Field(
        default_factory=lambda: _yaml_value("models", "consensus_models", [])
    )


class MemorySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEMORY__")

    enabled: bool = Field(default_factory=lambda: _yaml_value("memory", "enabled", True))
    backend: str = Field(default_factory=lambda: _yaml_value("memory", "backend", "sqlite"))
    db_path: str = Field(default_factory=lambda: _yaml_value("memory", "db_path", "data/superai.db"))
    context_window: int = Field(default_factory=lambda: _yaml_value("memory", "context_window", 5))
    max_history_turns: int = Field(default_factory=lambda: _yaml_value("memory", "max_history_turns", 20))


class FeedbackSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FEEDBACK__", populate_by_name=True)

    enabled: bool = Field(default_factory=lambda: _yaml_value("feedback", "enabled", False))
    store_path: str = Field(default_factory=lambda: _yaml_value("feedback", "store_path", "data/feedback.db"))
    min_score: int = Field(default_factory=lambda: _yaml_value("feedback", "min_score", 1))
    max_score: int = Field(default_factory=lambda: _yaml_value("feedback", "max_score", 5))
    learning_threshold: int = Field(default_factory=lambda: _yaml_value("feedback", "learning_threshold", 50))


class SecuritySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SECURITY__", populate_by_name=True)

    enabled: bool = Field(default_factory=lambda: _yaml_value("security", "enabled", True))
    require_auth: bool = Field(default_factory=lambda: _yaml_value("security", "require_auth", False))
    bandit_scan: bool = Field(default_factory=lambda: _yaml_value("security", "bandit_scan", True))
    prompt_injection_guard: bool = Field(
        default_factory=lambda: _yaml_value("security", "prompt_injection_guard", True)
    )
    output_filter: bool = Field(default_factory=lambda: _yaml_value("security", "output_filter", True))
    secret_key: str = Field(
        default="change-me-in-production",
        validation_alias=AliasChoices("SECRET_KEY", "secret_key"),
    )


class PersonalitySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PERSONALITY__")

    enabled: bool = Field(default_factory=lambda: _yaml_value("personality", "enabled", False))
    name: str = Field(default_factory=lambda: _yaml_value("personality", "name", "SuperAI"))
    version: str = Field(default_factory=lambda: _yaml_value("personality", "version", "11.0"))
    system_prompt: str = Field(
        default_factory=lambda: _yaml_value(
            "personality",
            "system_prompt",
            "You are SuperAI, a helpful and accurate AI assistant. Give clear, concise answers.",
        )
    )


class LoggingSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LOGGING__")

    level: str = Field(default_factory=lambda: _yaml_value("logging", "level", "INFO"))
    format: str = Field(default_factory=lambda: _yaml_value("logging", "format", "text"))
    file: str = Field(default_factory=lambda: _yaml_value("logging", "file", "logs/superai.log"))
    rotation: str = Field(default_factory=lambda: _yaml_value("logging", "rotation", "10 MB"))


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENT__")

    enabled: bool = Field(default_factory=lambda: _yaml_value("agent", "enabled", True))
    max_iterations: int = Field(default_factory=lambda: _yaml_value("agent", "max_iterations", 15))
    tool_timeout: int = Field(default_factory=lambda: _yaml_value("agent", "tool_timeout", 15))


class VoiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VOICE__")

    enabled: bool = Field(default_factory=lambda: _yaml_value("voice", "enabled", False))
    stt_model: str = Field(default_factory=lambda: _yaml_value("voice", "stt_model", "base"))
    tts_engine: str = Field(default_factory=lambda: _yaml_value("voice", "tts_engine", "gtts"))
    language: str = Field(default_factory=lambda: _yaml_value("voice", "language", "en"))
    tts_rate: int = Field(default_factory=lambda: _yaml_value("voice", "tts_rate", 180))
    tts_volume: float = Field(default_factory=lambda: _yaml_value("voice", "tts_volume", 1.0))


class SkillsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SKILLS__")

    builtin_dir: str = Field(
        default_factory=lambda: _yaml_value("skills", "builtin_dir", "backend/skills/builtin/")
    )
    custom_dir: str = Field(
        default_factory=lambda: _yaml_value("skills", "custom_dir", "data/custom_skills")
    )
    auto_activate_all: bool = Field(
        default_factory=lambda: _yaml_value("skills", "auto_activate_all", True)
    )


class FeatureGates(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FEATURES__",
        populate_by_name=True,
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    enable_workflow: bool = False
    enable_skills: bool = False
    enable_context: bool = False
    enable_judge: bool = False
    enable_cognitive: bool = False
    enable_reflection: bool = False
    enable_learning: bool = False
    enable_advanced_memory: bool = False
    enable_parallel_agents: bool = False
    enable_rag: bool = False
    enable_self_improvement: bool = False
    enable_model_registry: bool = False
    enable_ai_security: bool = False
    enable_multimodal: bool = False
    enable_distributed: bool = False
    enable_personality: bool = False
    enable_rlhf: bool = False
    enable_tools: bool = False
    enable_consensus: bool = False
    enable_code_review: bool = False
    enable_debugging: bool = False
    enable_voice: bool = False
    enable_vision: bool = False
    enable_feedback: bool = False
    enable_agent: bool = False


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    mode: str = Field(default_factory=lambda: _YAML_CONFIG.get("mode", "minimal"))
    server: ServerSettings = Field(default_factory=ServerSettings)
    models: ModelSettings = Field(default_factory=ModelSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    feedback: FeedbackSettings = Field(default_factory=FeedbackSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    personality: PersonalitySettings = Field(default_factory=PersonalitySettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    voice: VoiceSettings = Field(default_factory=VoiceSettings)
    skills: SkillsSettings = Field(default_factory=SkillsSettings)
    features: FeatureGates = Field(default_factory=_build_feature_gates)

    @model_validator(mode="after")
    def _validate_security_defaults(self):
        if self.server.environment == "production" and "change-me" in self.security.secret_key:
            raise ValueError("SECRET_KEY must be changed in production")
        return self

    @property
    def current_mode(self) -> str:
        return os.environ.get("SUPERAI_MODE", self.mode)

    @property
    def is_minimal(self) -> bool:
        return self.current_mode == "minimal"

    @property
    def enabled_features(self) -> dict[str, bool]:
        return {key: value for key, value in self.features.model_dump().items() if value}

    @property
    def active_features(self) -> dict[str, bool]:
        if self.is_minimal:
            return {}
        return self.enabled_features


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()


settings = get_settings()
