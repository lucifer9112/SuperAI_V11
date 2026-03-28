from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def load_launcher_module():
    script_path = ROOT / "scripts" / "run_colab_v11.py"
    spec = importlib.util.spec_from_file_location("run_colab_v11_test", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_base_config(path: Path) -> None:
    config = {
        "mode": "minimal",
        "server": {
            "host": "0.0.0.0",
            "port": 8000,
            "reload": False,
            "workers": 1,
            "environment": "development",
            "cors_origins": ["*"],
        },
        "models": {
            "device": "auto",
            "cache_size": 1,
            "idle_timeout": 300,
            "default_max_tokens": 512,
            "default_temperature": 0.7,
            "primary": "Qwen/Qwen2.5-0.5B-Instruct",
        },
        "logging": {
            "level": "INFO",
            "format": "text",
            "file": "logs/superai.log",
            "rotation": "10 MB",
        },
        "memory": {
            "enabled": True,
            "backend": "sqlite",
            "db_path": "data/superai.db",
            "context_window": 5,
            "max_history_turns": 20,
        },
        "features": {
            "enable_rag": False,
            "enable_tools": False,
            "enable_voice": False,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")


def test_patch_config_sets_minimal_mode_and_colab_paths(tmp_path):
    launcher = load_launcher_module()
    project = tmp_path / "project"
    config_path = project / "config" / "config.yaml"
    data_dir = tmp_path / "colab_data"
    log_dir = data_dir / "logs"

    write_base_config(config_path)

    launcher.PROJECT = project
    launcher.CONFIG_PATH = config_path
    launcher.DATA = data_dir
    launcher.LOG_DIR = log_dir

    launcher.patch_config("cpu", "Qwen/Test", 8123, False, [], mode="minimal")

    updated = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert updated["mode"] == "minimal"
    assert updated["server"]["port"] == 8123
    assert updated["models"]["device"] == "cpu"
    assert updated["models"]["primary"] == "Qwen/Test"
    assert updated["memory"]["db_path"] == str(data_dir / "superai_v11.db")
    assert updated["logging"]["file"] == str(log_dir / "superai_v11.log")
    assert all(value is False for value in updated["features"].values())

    env_text = (project / ".env").read_text(encoding="utf-8")
    assert "SERVER__PORT=8123" in env_text
    assert "MODELS__DEVICE=cpu" in env_text


def test_patch_config_maps_advanced_feature_ids(tmp_path):
    launcher = load_launcher_module()
    project = tmp_path / "project"
    config_path = project / "config" / "config.yaml"
    data_dir = tmp_path / "colab_data"
    log_dir = data_dir / "logs"

    write_base_config(config_path)

    launcher.PROJECT = project
    launcher.CONFIG_PATH = config_path
    launcher.DATA = data_dir
    launcher.LOG_DIR = log_dir

    launcher.patch_config(
        "cuda",
        "Qwen/Test",
        8000,
        False,
        ["F5", "S2", "enable_voice"],
        mode="advanced",
    )

    updated = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert updated["mode"] == "advanced"
    assert updated["features"]["enable_rag"] is True
    assert updated["features"]["enable_tools"] is True
    assert updated["features"]["enable_voice"] is True
    assert updated["features"]["enable_learning"] is False


def test_write_frontend_env_points_to_backend_url(tmp_path):
    launcher = load_launcher_module()
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir(parents=True, exist_ok=True)
    launcher.FRONTEND_DIR = frontend_dir

    launcher.write_frontend_env("https://demo.ngrok-free.app", enable_advanced_tabs=False)

    env_text = (frontend_dir / ".env.local").read_text(encoding="utf-8")
    assert "NEXT_PUBLIC_API_URL=https://demo.ngrok-free.app" in env_text
    assert "NEXT_PUBLIC_WS_URL=https://demo.ngrok-free.app" in env_text
    assert "NEXT_PUBLIC_ENABLE_ADVANCED_TABS=false" in env_text
