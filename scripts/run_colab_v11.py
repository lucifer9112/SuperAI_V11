#!/usr/bin/env python3
"""
SuperAI V11 Colab launcher for the simplified runtime.

Examples:
  python scripts/run_colab_v11.py --token YOUR_NGROK_TOKEN
  python scripts/run_colab_v11.py --token YOUR_NGROK_TOKEN --with-frontend
  python scripts/run_colab_v11.py --token YOUR_NGROK_TOKEN --mode advanced --features F5,S2
"""

from __future__ import annotations

import argparse
import importlib
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable

import yaml

PROJECT = Path(__file__).parent.parent.resolve()
FRONTEND_DIR = PROJECT / "frontend"
CONFIG_PATH = PROJECT / "config" / "config.yaml"
DATA = Path("/content/superai_v11_data")
LOG_DIR = DATA / "logs"
BACKEND_LOG = LOG_DIR / "backend.log"
FRONTEND_LOG = LOG_DIR / "frontend.log"

KNOWN_FEATURE_KEYS = {
    "enable_workflow",
    "enable_skills",
    "enable_context",
    "enable_judge",
    "enable_cognitive",
    "enable_reflection",
    "enable_learning",
    "enable_advanced_memory",
    "enable_parallel_agents",
    "enable_rag",
    "enable_self_improvement",
    "enable_model_registry",
    "enable_ai_security",
    "enable_multimodal",
    "enable_distributed",
    "enable_personality",
    "enable_rlhf",
    "enable_tools",
    "enable_consensus",
    "enable_code_review",
    "enable_debugging",
    "enable_voice",
    "enable_vision",
    "enable_feedback",
    "enable_agent",
}

FEATURE_ID_MAP = {
    "F1": "enable_reflection",
    "F2": "enable_learning",
    "F3": "enable_advanced_memory",
    "F4": "enable_parallel_agents",
    "F5": "enable_rag",
    "F6": "enable_self_improvement",
    "F7": "enable_model_registry",
    "F8": "enable_ai_security",
    "F9": "enable_multimodal",
    "F10": "enable_distributed",
    "F11": "enable_workflow",
    "S1": "enable_rlhf",
    "S2": "enable_tools",
    "S3": "enable_consensus",
}


def p_ok(message: str) -> None:
    print(f"  \033[32mOK {message}\033[0m")


def p_info(message: str) -> None:
    print(f"  \033[34mINFO {message}\033[0m")


def p_warn(message: str) -> None:
    print(f"  \033[33mWARN {message}\033[0m")


def p_fail(message: str) -> None:
    print(f"  \033[31mFAIL {message}\033[0m")
    raise SystemExit(1)


def p_head(message: str) -> None:
    line = "-" * 55
    print(f"\n\033[1;36m{line}\n  {message}\n{line}\033[0m")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch SuperAI V11 on Google Colab.")
    parser.add_argument("--token", default=os.getenv("NGROK_TOKEN", ""))
    parser.add_argument("--port", default=8000, type=int)
    parser.add_argument("--frontend-port", default=3000, type=int)
    parser.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--mode", choices=["minimal", "advanced"], default="minimal")
    parser.add_argument("--features", default="", help="Comma-separated feature IDs or gate names")
    parser.add_argument("--with-frontend", action="store_true", help="Start the Next.js frontend too")
    parser.add_argument(
        "--enable-advanced-tabs",
        action="store_true",
        help="Expose advanced frontend tabs when running the frontend",
    )
    parser.add_argument("--no-install", action="store_true")
    parser.add_argument(
        "--safe-mode",
        action="store_true",
        help="Backward-compatible alias for minimal mode with all advanced gates disabled",
    )
    return parser.parse_args()


def run(cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        cmd,
        cwd=str(cwd or PROJECT),
        text=True,
        capture_output=True,
    )
    if check and completed.returncode != 0:
        p_fail(
            f"Command failed: {' '.join(cmd)}\n"
            f"stdout:\n{completed.stdout[-1200:]}\n"
            f"stderr:\n{completed.stderr[-1200:]}"
        )
    return completed


def _tail(path: Path, lines: int = 80) -> str:
    if not path.exists():
        return ""
    return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])


def _wait_for_http(url: str, *, timeout_seconds: int = 120, expected_fragment: str | None = None) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                text = response.read().decode("utf-8", errors="replace")
                if expected_fragment and expected_fragment not in text:
                    time.sleep(2)
                    continue
                return
        except urllib.error.URLError:
            time.sleep(2)
    p_fail(f"Timed out waiting for {url}")


def check_gpu() -> str:
    p_head("SuperAI V11 - Colab Launcher")
    try:
        result = run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader",
            ],
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            gpu_line = result.stdout.strip().splitlines()[0]
            p_ok(f"GPU: {gpu_line}")
            return "cuda"
    except Exception:
        pass

    p_warn("GPU not detected, falling back to CPU")
    return "cpu"


def install_deps(_safe_mode: bool = False) -> None:
    p_head("Installing dependencies")
    python = sys.executable
    run([python, "-m", "pip", "install", "-q", "--upgrade", "pip", "setuptools", "wheel"])
    p_ok("Build tooling")
    run([python, "-m", "pip", "install", "-q", "-r", str(PROJECT / "requirements-colab.txt")])
    p_ok("Core Python packages")


def verify_runtime_deps() -> None:
    modules = {
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "requests": "requests",
        "yaml": "yaml",
        "pydantic_settings": "pydantic_settings",
        "pyngrok": "pyngrok",
    }
    for display_name, module_name in modules.items():
        importlib.import_module(module_name)
    p_ok("Runtime imports verified")


def create_dirs() -> None:
    for path in [DATA, LOG_DIR, DATA / "uploads"]:
        path.mkdir(parents=True, exist_ok=True)
    p_ok(f"Data dirs: {DATA}")


def _normalize_feature_flags(items: Iterable[str]) -> set[str]:
    enabled: set[str] = set()
    for raw_item in items:
        item = raw_item.strip()
        if not item:
            continue
        upper = item.upper()
        lowered = item.lower()

        if upper in FEATURE_ID_MAP:
            enabled.add(FEATURE_ID_MAP[upper])
            continue

        if item in KNOWN_FEATURE_KEYS:
            enabled.add(item)
            continue

        prefixed = f"enable_{lowered}"
        if prefixed in KNOWN_FEATURE_KEYS:
            enabled.add(prefixed)
    return enabled


def patch_config(
    device: str,
    model: str,
    port: int,
    safe_mode: bool,
    features: list[str],
    *,
    mode: str = "minimal",
) -> None:
    p_head("Patching config.yaml for Colab")
    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}

    selected_mode = "minimal" if safe_mode else mode
    cfg["mode"] = selected_mode

    cfg.setdefault("server", {})
    cfg["server"].update(
        {
            "host": "0.0.0.0",
            "port": port,
            "reload": False,
            "workers": 1,
            "environment": "development",
            "cors_origins": ["*"],
        }
    )

    cfg.setdefault("models", {})
    cfg["models"]["device"] = device
    cfg["models"]["cache_size"] = 1
    cfg["models"]["idle_timeout"] = 300
    cfg["models"]["primary"] = model

    cfg.setdefault("memory", {})
    cfg["memory"]["enabled"] = True
    cfg["memory"]["backend"] = "sqlite"
    cfg["memory"]["db_path"] = str(DATA / "superai_v11.db")

    cfg.setdefault("logging", {})
    cfg["logging"]["level"] = "INFO"
    cfg["logging"]["format"] = "text"
    cfg["logging"]["file"] = str(LOG_DIR / "superai_v11.log")

    cfg.setdefault("features", {})
    for feature_key in KNOWN_FEATURE_KEYS:
        cfg["features"].setdefault(feature_key, False)

    if selected_mode == "minimal":
        for feature_key in KNOWN_FEATURE_KEYS:
            cfg["features"][feature_key] = False
        p_info("Minimal mode enabled - advanced feature gates disabled")
    else:
        enabled_features = _normalize_feature_flags(features)
        if enabled_features:
            for feature_key in KNOWN_FEATURE_KEYS:
                cfg["features"][feature_key] = feature_key in enabled_features
            p_info(f"Advanced features enabled: {', '.join(sorted(enabled_features))}")
        else:
            p_info("Advanced mode enabled - keeping current feature gates")

    CONFIG_PATH.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    (PROJECT / ".env").write_text(
        "\n".join(
            [
                "SECRET_KEY=colab-v11-key",
                "SERVER__ENVIRONMENT=development",
                "SERVER__HOST=0.0.0.0",
                f"SERVER__PORT={port}",
                f"MODELS__DEVICE={device}",
                "LOGGING__LEVEL=INFO",
                "",
            ]
        ),
        encoding="utf-8",
    )
    p_ok(f"Config patched - mode={selected_mode}, device={device}, model={model.split('/')[-1]}")


def start_server(port: int, *, mode: str = "minimal") -> subprocess.Popen[str]:
    p_head("Starting SuperAI V11 backend")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_handle = BACKEND_LOG.open("w", encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(PROJECT)}
    cmd = [sys.executable, "run.py", "--host", "0.0.0.0", "--port", str(port), "--mode", mode]

    proc = subprocess.Popen(
        cmd,
        cwd=str(PROJECT),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )

    try:
        _wait_for_http(f"http://127.0.0.1:{port}/health", timeout_seconds=150, expected_fragment="status")
    except BaseException:
        if proc.poll() is None:
            proc.terminate()
        p_fail(f"Server failed to start\n{_tail(BACKEND_LOG)}")

    p_ok(f"Server ready on http://127.0.0.1:{port}")
    return proc


def ensure_node() -> None:
    p_head("Preparing frontend toolchain")
    node = shutil.which("node")
    npm = shutil.which("npm")
    if node and npm:
        version = run(["node", "--version"]).stdout.strip()
        p_ok(f"Node.js ready ({version})")
        return

    p_info("Installing Node.js 20")
    run(["bash", "-lc", "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -"])
    run(["apt-get", "install", "-y", "nodejs"])
    version = run(["node", "--version"]).stdout.strip()
    p_ok(f"Node.js installed ({version})")


def install_frontend_deps() -> None:
    p_head("Installing frontend dependencies")
    result = run(["npm", "install", "--no-fund", "--no-audit"], cwd=FRONTEND_DIR, check=False)
    if result.returncode != 0:
        p_warn("npm install failed once, retrying with legacy peer deps")
        run(
            ["npm", "install", "--legacy-peer-deps", "--no-fund", "--no-audit"],
            cwd=FRONTEND_DIR,
        )
    p_ok("Frontend dependencies installed")


def write_frontend_env(api_url: str, *, enable_advanced_tabs: bool) -> None:
    env_path = FRONTEND_DIR / ".env.local"
    env_path.write_text(
        "\n".join(
            [
                f"NEXT_PUBLIC_API_URL={api_url}",
                f"NEXT_PUBLIC_WS_URL={api_url}",
                f"NEXT_PUBLIC_ENABLE_ADVANCED_TABS={'true' if enable_advanced_tabs else 'false'}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    p_ok("Frontend environment written")


def start_frontend(port: int) -> subprocess.Popen[str]:
    p_head("Starting SuperAI V11 frontend")
    log_handle = FRONTEND_LOG.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", str(port)],
        cwd=str(FRONTEND_DIR),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        _wait_for_http(f"http://127.0.0.1:{port}", timeout_seconds=180, expected_fragment="<html")
    except BaseException:
        if proc.poll() is None:
            proc.terminate()
        p_fail(f"Frontend failed to start\n{_tail(FRONTEND_LOG)}")

    p_ok(f"Frontend ready on http://127.0.0.1:{port}")
    return proc


def _open_tunnel(port: int, label: str):
    from pyngrok import ngrok

    tunnel = ngrok.connect(port, bind_tls=True)
    p_ok(f"{label} tunnel: {tunnel.public_url}")
    return tunnel


def main() -> int:
    args = parse_args()
    device = check_gpu()
    selected_mode = "minimal" if args.safe_mode else args.mode
    feature_list = [item.strip() for item in args.features.split(",") if item.strip()]

    if not args.no_install:
        install_deps(args.safe_mode)
    verify_runtime_deps()
    create_dirs()
    patch_config(device, args.model, args.port, args.safe_mode, feature_list, mode=selected_mode)

    backend_proc = start_server(args.port, mode=selected_mode)
    frontend_proc: subprocess.Popen[str] | None = None

    try:
        backend_url = f"http://127.0.0.1:{args.port}"
        frontend_url = ""

        if args.token:
            from pyngrok import ngrok

            p_head("Opening ngrok tunnel(s)")
            ngrok.kill()
            ngrok.set_auth_token(args.token)
            backend_url = _open_tunnel(args.port, "Backend").public_url

        if args.with_frontend:
            ensure_node()
            if not args.no_install:
                install_frontend_deps()
            write_frontend_env(backend_url, enable_advanced_tabs=args.enable_advanced_tabs)
            frontend_proc = start_frontend(args.frontend_port)

            if args.token:
                frontend_url = _open_tunnel(args.frontend_port, "Frontend").public_url
            else:
                frontend_url = f"http://127.0.0.1:{args.frontend_port}"

        p_head("SuperAI V11 is LIVE")
        print(f"  Backend URL        : {backend_url}")
        print(f"  API docs           : {backend_url}/docs")
        print(f"  Health             : {backend_url}/health")
        print(f"  Chat API           : {backend_url}/api/v1/chat/")
        print(f"  Local smoke        : python scripts/colab_smoke_v11.py --no-install --mode {selected_mode}")
        if frontend_url:
            print(f"  Frontend URL       : {frontend_url}")
            print("  User interface     : Open the frontend URL, not /docs")
        else:
            print("  Frontend URL       : not started (use --with-frontend)")
        print(f"  Logs               : {BACKEND_LOG}")
        if frontend_proc is not None:
            print(f"  Frontend log       : {FRONTEND_LOG}")
        print("  Press Ctrl+C to stop")

        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        p_info("Stopping services")
        return 0
    finally:
        if frontend_proc and frontend_proc.poll() is None:
            frontend_proc.terminate()
            try:
                frontend_proc.wait(timeout=20)
            except Exception:
                frontend_proc.kill()

        if backend_proc.poll() is None:
            backend_proc.terminate()
            try:
                backend_proc.wait(timeout=20)
            except Exception:
                backend_proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
