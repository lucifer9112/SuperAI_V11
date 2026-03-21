#!/usr/bin/env python3
"""
SuperAI V11 - scripts/run_colab_v11.py

One-command Colab launcher.

Usage:
  !python scripts/run_colab_v11.py --token YOUR_NGROK_TOKEN

Options:
  --token TOKEN     ngrok authtoken
  --model MODEL     override default model
  --no-install      skip pip install
  --safe-mode       disable V11 features and skip optional heavy installs
  --features F1,S2  enable specific features only
"""

import argparse
import importlib
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import yaml

PROJECT = Path(__file__).parent.parent.resolve()
DATA = Path("/content/superai_v11_data")
LOG = DATA / "logs" / "server.log"


def p_ok(message: str) -> None:
    print(f"  \033[32mOK {message}\033[0m")


def p_info(message: str) -> None:
    print(f"  \033[34mINFO {message}\033[0m")


def p_warn(message: str) -> None:
    print(f"  \033[33mWARN {message}\033[0m")


def p_fail(message: str) -> None:
    print(f"  \033[31mFAIL {message}\033[0m")
    sys.exit(1)


def p_head(message: str) -> None:
    line = "-" * 55
    print(f"\n\033[1;36m{line}\n  {message}\n{line}\033[0m")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", default=os.getenv("NGROK_TOKEN", ""))
    parser.add_argument("--port", default=8000, type=int)
    parser.add_argument("--model", default="TinyLlama/TinyLlama-1.1B-Chat-v1.0")
    parser.add_argument("--no-install", action="store_true")
    parser.add_argument(
        "--safe-mode",
        action="store_true",
        help="Disable V10+V11 features and skip optional heavy installs",
    )
    parser.add_argument(
        "--features",
        default="",
        help="Comma-separated feature IDs e.g. F1,F5,S1,S2",
    )
    return parser.parse_args()


def check_gpu() -> str:
    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        p_ok(f"GPU: {result.stdout.strip()}")
        return "cuda"
    p_warn("No GPU detected - using CPU mode")
    return "cpu"


def _run_command(command: list[str], fatal: bool, label: str):
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode == 0:
        return result

    error_text = (result.stderr or result.stdout or "").strip()
    error_text = error_text[-1200:] if error_text else "No output captured."
    if fatal:
        p_fail(f"{label} failed:\n{error_text}")
    p_warn(f"{label} failed (optional):\n{error_text}")
    return result


def _pip_install(args: list[str], label: str, fatal: bool) -> bool:
    result = _run_command([sys.executable, "-m", "pip", "install", "-q", *args], fatal, label)
    if result.returncode == 0:
        p_ok(label)
        return True
    return False


def install_deps(safe_mode: bool) -> None:
    p_head("Installing dependencies")

    _run_command(["apt-get", "update", "-qq"], fatal=True, label="apt-get update")
    _run_command(
        ["apt-get", "install", "-y", "-qq", "ffmpeg", "libsndfile1"],
        fatal=True,
        label="System package install",
    )
    p_ok("System packages")

    _pip_install(["--upgrade", "pip", "setuptools", "wheel"], "Build tooling", fatal=True)
    _pip_install(
        ["-r", str(PROJECT / "requirements" / "base.txt")],
        "Core Python packages",
        fatal=True,
    )
    _pip_install(
        ["pyngrok==7.2.0", "nest-asyncio==1.6.0"],
        "Tunnel packages",
        fatal=True,
    )

    if safe_mode:
        p_info("Safe mode selected - skipping optional Colab packages")
        return

    optional_groups = [
        (
            "Model packages",
            [
                "transformers==4.45.2",
                "accelerate==0.34.2",
                "sentence-transformers==3.1.1",
            ],
        ),
        ("Vector packages", ["faiss-cpu==1.8.0"]),
        (
            "Voice packages",
            ["openai-whisper==20240930", "gtts==2.5.3", "soundfile==0.12.1"],
        ),
        (
            "Document packages",
            ["pdfplumber==0.11.4", "python-docx==1.1.2", "openpyxl==3.1.5"],
        ),
    ]

    for label, packages in optional_groups:
        _pip_install(packages, label, fatal=False)

    if sys.version_info < (3, 12):
        _pip_install(["bitsandbytes==0.43.3"], "Quantization package", fatal=False)
    else:
        p_warn("Skipping bitsandbytes on Python 3.12+ because Colab wheels are unreliable")


def verify_runtime_deps() -> None:
    required_modules = [
        "fastapi",
        "uvicorn",
        "yaml",
        "loguru",
        "aiosqlite",
        "pydantic_settings",
        "httpx",
        "prometheus_client",
        "pyngrok",
    ]
    missing = []

    for module_name in required_modules:
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover - defensive import guard
            missing.append(f"{module_name}: {exc}")

    if missing:
        joined = "\n".join(f"  - {item}" for item in missing)
        p_fail(f"Runtime dependency check failed:\n{joined}")

    p_ok("Runtime imports verified")


def create_dirs() -> None:
    for directory in [
        DATA / "logs",
        DATA / "uploads",
        DATA / "vector_db",
        DATA / "training",
        DATA / "rlhf_checkpoints",
        DATA / "reward_model",
        DATA / "improvement_logs",
        DATA / "security_logs",
    ]:
        directory.mkdir(parents=True, exist_ok=True)
    p_ok(f"Data dirs: {DATA}")


def patch_config(device: str, model: str, port: int, safe_mode: bool, features: list[str]) -> None:
    p_head("Patching config.yaml for Colab")
    cfg_path = PROJECT / "config" / "config.yaml"
    with open(cfg_path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)

    cfg["server"].update(
        {
            "host": "0.0.0.0",
            "port": port,
            "reload": False,
            "workers": 1,
            "cors_origins": ["*"],
        }
    )

    cfg["models"]["device"] = device
    cfg["models"]["cache_size"] = 1
    for key in ["chat", "code", "reasoning", "agent", "fast", "reflection"]:
        cfg["models"]["routing"][key] = model
    cfg["models"]["routing"]["vision"] = ""

    path_map = {
        ("memory", "db_path"): str(DATA / "superai_v11.db"),
        ("memory", "vector_db_path"): str(DATA / "vector_db/"),
        ("advanced_memory", "episodic_db_path"): str(DATA / "episodic.db"),
        ("advanced_memory", "semantic_graph_path"): str(DATA / "knowledge_graph.pkl"),
        ("feedback", "store_path"): str(DATA / "feedback.db"),
        ("files", "upload_dir"): str(DATA / "uploads/"),
        ("logging", "file"): str(DATA / "logs/superai_v11.log"),
        ("self_improvement", "failure_log_path"): str(DATA / "improvement_logs/"),
        ("self_improvement", "improvement_db_path"): str(DATA / "improvements.db"),
        ("ai_security", "anomaly_log_path"): str(DATA / "security_logs/"),
        ("learning", "dataset_path"): str(DATA / "training/"),
        ("learning", "lora_output_dir"): str(DATA / "lora_checkpoints/"),
        ("model_registry", "registry_path"): str(DATA / "model_registry.json"),
    }
    if "rlhf" in cfg:
        cfg["rlhf"]["rlhf_output_dir"] = str(DATA / "rlhf_checkpoints/")
        cfg["rlhf"]["rlhf_log_db"] = str(DATA / "rlhf_logs.db")

    for (section, key), value in path_map.items():
        if section in cfg and isinstance(cfg[section], dict):
            cfg[section][key] = value

    if "voice" in cfg and isinstance(cfg["voice"], dict):
        cfg["voice"]["enabled"] = False
    cfg["logging"]["format"] = "text"
    cfg["logging"]["level"] = "INFO"

    if safe_mode:
        for section in [
            "reflection",
            "learning",
            "advanced_memory",
            "parallel_agents",
            "rag",
            "self_improvement",
            "model_registry",
            "ai_security",
            "multimodal",
            "distributed",
            "rlhf",
            "tools",
            "consensus",
        ]:
            if section in cfg and isinstance(cfg[section], dict):
                cfg[section]["enabled"] = False
        p_warn("Safe mode enabled - V10/V11 advanced features disabled")
    elif features:
        feat_map = {
            "F1": "reflection",
            "F2": "learning",
            "F3": "advanced_memory",
            "F4": "parallel_agents",
            "F5": "rag",
            "F6": "self_improvement",
            "F7": "model_registry",
            "F8": "ai_security",
            "F9": "multimodal",
            "F10": "distributed",
            "F11": "reflection",
            "S1": "rlhf",
            "S2": "tools",
            "S3": "consensus",
        }
        enabled_sections = {feat_map[item] for item in features if item in feat_map}
        for section in set(feat_map.values()):
            if section in cfg and isinstance(cfg[section], dict):
                cfg[section]["enabled"] = section in enabled_sections
        p_info(f"Features enabled: {', '.join(features)}")

    with open(cfg_path, "w", encoding="utf-8") as fh:
        yaml.dump(cfg, fh, default_flow_style=False, sort_keys=False)

    (PROJECT / ".env").write_text(
        "\n".join(
            [
                "SECRET_KEY=colab-v11-key",
                f"MODELS__DEVICE={device}",
                "LOGGING__LEVEL=INFO",
                f"SERVER__PORT={port}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    p_ok(f"Config patched - device={device}, model={model.split('/')[-1]}")


def start_server(port: int):
    p_head("Starting SuperAI V11 backend")
    subprocess.run(["pkill", "-f", "uvicorn"], capture_output=True)
    time.sleep(1)

    sys.path.insert(0, str(PROJECT))
    os.chdir(PROJECT)
    LOG.parent.mkdir(parents=True, exist_ok=True)

    with open(LOG, "w", encoding="utf-8") as log_fh:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "backend.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                str(port),
                "--log-level",
                "info",
                "--no-access-log",
            ],
            cwd=str(PROJECT),
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONPATH": str(PROJECT)},
        )

    for attempt in range(90):
        time.sleep(2)
        try:
            urllib.request.urlopen(f"http://localhost:{port}/health", timeout=3)
            p_ok(f"Server ready after {attempt * 2}s")
            return proc
        except Exception:
            if proc.poll() is not None:
                server_log = LOG.read_text(encoding="utf-8", errors="ignore")
                print(server_log[-3000:])
                p_fail("Server died - check logs above")
            if attempt % 10 == 9:
                p_info(f"Still starting... ({attempt * 2}s)")

    p_fail("Server timeout after 180s")


def open_tunnel(token: str, port: int) -> str:
    p_head("Opening ngrok tunnel")
    try:
        from pyngrok import ngrok

        if token:
            ngrok.set_auth_token(token)
        else:
            p_warn("No token provided - using anonymous ngrok tunnel")
        tunnel = ngrok.connect(port, "http")
        url = tunnel.public_url
        p_ok(f"Tunnel: {url}")
        return url
    except ImportError:
        p_fail("pyngrok not found - install tunnel packages first")
    except Exception as exc:
        p_fail(f"ngrok error: {exc}")


def print_summary(url: str) -> None:
    p_head("SuperAI V11 is LIVE")
    endpoints = [
        ("Public URL", url),
        ("API Docs", f"{url}/docs"),
        ("Health", f"{url}/health"),
        ("Chat", f"{url}/api/v1/chat/"),
        ("", ""),
        ("-- V11 Step 1 RLHF --", ""),
        ("RLHF Status", f"{url}/api/v1/rlhf/status"),
        ("Train DPO", f"{url}/api/v1/rlhf/train/dpo"),
        ("Train GRPO", f"{url}/api/v1/rlhf/train/grpo"),
        ("Score Response", f"{url}/api/v1/rlhf/score"),
        ("", ""),
        ("-- V11 Step 2 Tools --", ""),
        ("List Tools", f"{url}/api/v1/tools/list"),
        ("Call Tools", f"{url}/api/v1/tools/call"),
        ("Execute Tool", f"{url}/api/v1/tools/execute"),
        ("", ""),
        ("-- V11 Step 3 Consensus --", ""),
        ("Consensus Run", f"{url}/api/v1/consensus/run"),
        ("Consensus Status", f"{url}/api/v1/consensus/status"),
        ("", ""),
        ("System Status", f"{url}/api/v1/system/status"),
        ("AI Security", f"{url}/api/v1/security/assess"),
        ("RAG Knowledge", f"{url}/api/v1/knowledge/retrieve"),
    ]

    for label, value in endpoints:
        if not label and not value:
            print()
        elif not value:
            print(f"  \033[1;33m{label}\033[0m")
        else:
            print(f"  \033[32m{label:20s}\033[0m: {value}")

    print(f"\n  Logs: {LOG}")
    print("\n  Quick test:")
    print(f"  curl -X POST {url}/api/v1/chat/ \\")
    print('    -H "Content-Type: application/json" \\')
    print('    -d \'{"prompt":"Hello V11! What can you do?","max_tokens":128}\'')


def main() -> None:
    args = parse_args()
    p_head("SuperAI V11 - Colab Launcher")

    device = check_gpu()
    features = [item.strip() for item in args.features.split(",") if item.strip()]

    if not args.no_install:
        install_deps(args.safe_mode)
    verify_runtime_deps()
    create_dirs()
    patch_config(device, args.model, args.port, args.safe_mode, features)
    proc = start_server(args.port)
    url = open_tunnel(args.token, args.port)
    print_summary(url)

    os.environ["SUPERAI_V11_URL"] = url
    p_info("Press Ctrl+C to stop")
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        print("\nSuperAI V11 stopped.")


if __name__ == "__main__":
    main()
