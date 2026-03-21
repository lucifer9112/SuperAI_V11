#!/usr/bin/env python3
"""
SuperAI V11 — scripts/run_colab_v10.py

ONE-COMMAND launcher for Google Colab.

Usage in Colab cell:
  !python scripts/run_colab_v10.py --token YOUR_NGROK_TOKEN

Options:
  --token TOKEN     ngrok authtoken (required for public URL)
  --port PORT       server port (default: 8000)
  --model MODEL     model name override
  --no-install      skip pip install (if already done)
  --no-v10          run in V9-compat mode (skip heavy V10 features)
  --features F1,F5  enable only specific features (F1=reflection,F5=rag etc.)
"""
import argparse, os, subprocess, sys, time, yaml, shutil
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent.resolve()
DATA_DIR    = Path("/content/superai_v11_data")
LOG_PATH    = DATA_DIR / "logs" / "server.log"


def banner(msg): print(f"\n\033[1;36m{'─'*58}\033[0m\n  \033[1;36m{msg}\033[0m\n\033[1;36m{'─'*58}\033[0m")
def ok(m):   print(f"  \033[0;32m✓ {m}\033[0m")
def info(m): print(f"  \033[0;34mℹ {m}\033[0m")
def warn(m): print(f"  \033[0;33m⚠ {m}\033[0m")
def fail(m): print(f"  \033[0;31m✗ {m}\033[0m"); sys.exit(1)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--token",      default=os.getenv("NGROK_TOKEN",""))
    p.add_argument("--port",       default=8000, type=int)
    p.add_argument("--model",      default="TinyLlama/TinyLlama-1.1B-Chat-v1.0")
    p.add_argument("--no-install", action="store_true")
    p.add_argument("--no-v10",     action="store_true",
                   help="Disable V10 features, run in V9-compat mode")
    p.add_argument("--features",   default="",
                   help="Comma-separated feature list to enable (e.g. F1,F5,F8)")
    return p.parse_args()


def check_gpu():
    r = subprocess.run(["nvidia-smi","--query-gpu=name,memory.total",
                        "--format=csv,noheader"], capture_output=True, text=True)
    if r.returncode == 0:
        ok(f"GPU: {r.stdout.strip()}")
        return "cuda"
    warn("No GPU — running on CPU")
    return "cpu"


def install_deps():
    banner("Installing dependencies")
    subprocess.run(["apt-get","update","-qq"], check=True, capture_output=True)
    subprocess.run(["apt-get","install","-y","-qq","ffmpeg","libsndfile1"],
                   check=True, capture_output=True)
    ok("System packages")
    req = PROJECT_DIR / "requirements" / "colab.txt"
    r   = subprocess.run([sys.executable,"-m","pip","install","-q","-r",str(req)],
                         capture_output=True, text=True)
    if r.returncode != 0:
        warn(f"Some packages failed:\n{r.stderr[-400:]}")
    else:
        ok("Python packages")


def create_dirs():
    for d in [DATA_DIR, DATA_DIR/"logs", DATA_DIR/"uploads",
              DATA_DIR/"vector_db", DATA_DIR/"training",
              DATA_DIR/"lora_checkpoints", DATA_DIR/"improvement_logs",
              DATA_DIR/"security_logs"]:
        d.mkdir(parents=True, exist_ok=True)
    ok(f"Data dirs: {DATA_DIR}")


def patch_config(device, model, no_v10, features_enabled):
    banner("Patching config for Colab")
    cfg_path = PROJECT_DIR / "config" / "config.yaml"
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)

    # Server
    cfg["server"]["host"]         = "0.0.0.0"
    cfg["server"]["port"]         = 8000
    cfg["server"]["reload"]       = False
    cfg["server"]["workers"]      = 1
    cfg["server"]["cors_origins"] = ["*"]

    # Models
    cfg["models"]["device"]       = device
    cfg["models"]["cache_size"]   = 1
    cfg["models"]["routing"]      = {k: model for k in
                                     ["chat","code","reasoning","agent","fast","reflection"]}
    cfg["models"]["routing"]["vision"] = ""

    # Data paths
    cfg["memory"]["db_path"]        = str(DATA_DIR/"superai_v11.db")
    cfg["memory"]["vector_db_path"] = str(DATA_DIR/"vector_db/")
    cfg["advanced_memory"]["episodic_db_path"]    = str(DATA_DIR/"episodic.db")
    cfg["advanced_memory"]["semantic_graph_path"] = str(DATA_DIR/"knowledge_graph.pkl")
    cfg["feedback"]["store_path"]   = str(DATA_DIR/"feedback.db")
    cfg["files"]["upload_dir"]      = str(DATA_DIR/"uploads/")
    cfg["logging"]["file"]          = str(DATA_DIR/"logs/superai_v11.log")
    cfg["logging"]["format"]        = "text"
    cfg["logging"]["level"]         = "INFO"
    cfg["self_improvement"]["failure_log_path"]  = str(DATA_DIR/"improvement_logs/")
    cfg["self_improvement"]["improvement_db_path"] = str(DATA_DIR/"improvements.db")
    cfg["ai_security"]["anomaly_log_path"]       = str(DATA_DIR/"security_logs/")
    cfg["learning"]["dataset_path"]   = str(DATA_DIR/"training/")
    cfg["learning"]["lora_output_dir"]= str(DATA_DIR/"lora_checkpoints/")
    cfg["model_registry"]["registry_path"] = str(DATA_DIR/"model_registry.json")

    # Voice off (no mic in Colab)
    cfg["voice"]["enabled"] = False

    # V10 feature toggles
    if no_v10:
        for feat in ["reflection","learning","advanced_memory","parallel_agents",
                     "rag","self_improvement","model_registry","ai_security",
                     "multimodal","distributed"]:
            if feat in cfg and isinstance(cfg[feat], dict):
                cfg[feat]["enabled"] = False
        warn("V10 features DISABLED (--no-v10 mode)")
    elif features_enabled:
        # Enable only specified features
        feat_map = {"F1":"reflection","F2":"learning","F3":"advanced_memory",
                    "F4":"parallel_agents","F5":"rag","F6":"self_improvement",
                    "F7":"model_registry","F8":"ai_security","F9":"multimodal",
                    "F10":"distributed"}
        all_feats = set(feat_map.values())
        enabled   = {feat_map[f] for f in features_enabled if f in feat_map}
        for feat in all_feats:
            if feat in cfg and isinstance(cfg[feat], dict):
                cfg[feat]["enabled"] = feat in enabled
        info(f"Features enabled: {features_enabled}")

    with open(cfg_path, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False)

    # Write .env
    (PROJECT_DIR / ".env").write_text(
        f"SECRET_KEY=colab-v10-secret\n"
        f"MODELS__DEVICE={device}\n"
        f"LOGGING__LEVEL=INFO\n"
        f"SERVER__PORT=8000\n"
    )
    ok(f"Config patched — device={device}, model={model.split('/')[-1]}")


def start_server():
    banner("Starting SuperAI V11 backend")
    subprocess.run(["pkill","-f","uvicorn"], capture_output=True)
    time.sleep(1)

    sys.path.insert(0, str(PROJECT_DIR))
    os.chdir(PROJECT_DIR)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log_fh = open(LOG_PATH, "w")

    proc = subprocess.Popen(
        [sys.executable,"-m","uvicorn","backend.main:app",
         "--host","0.0.0.0","--port","8000","--log-level","info","--no-access-log"],
        cwd=str(PROJECT_DIR), stdout=log_fh, stderr=subprocess.STDOUT,
        env={**os.environ,"PYTHONPATH":str(PROJECT_DIR)},
    )

    import urllib.request
    for i in range(90):
        time.sleep(2)
        try:
            urllib.request.urlopen("http://localhost:8000/health", timeout=3)
            ok(f"Server ready after {i*2}s")
            return proc
        except Exception:
            if proc.poll() is not None:
                print(LOG_PATH.read_text()[-3000:])
                fail("Server died — check logs above")
            if i % 10 == 9:
                info(f"Still starting… ({i*2}s) — loading model may take time")

    fail("Server timeout after 180s")


def open_tunnel(token, port):
    banner("Opening ngrok tunnel")
    try:
        from pyngrok import ngrok
        if token:
            ngrok.set_auth_token(token)
        else:
            warn("No ngrok token — tunnel may be limited")
        t   = ngrok.connect(port, "http")
        url = t.public_url
        ok(f"Tunnel: {url}")
        return url
    except ImportError:
        fail("pyngrok not found — run: pip install pyngrok")
    except Exception as e:
        fail(f"ngrok error: {e}")


def print_summary(url):
    banner("🚀 SuperAI V11 is LIVE!")
    print(f"""
  \033[1;32mPublic URL    \033[0m: {url}
  \033[1;32mAPI Docs      \033[0m: {url}/docs
  \033[1;32mHealth        \033[0m: {url}/health
  \033[1;32mChat          \033[0m: {url}/api/v1/chat/
  \033[1;32mParallel Agents\033[0m: {url}/api/v1/personality/parallel-agents
  \033[1;32mRAG Knowledge \033[0m: {url}/api/v1/knowledge/retrieve
  \033[1;32mSelf-Reflect  \033[0m: {url}/api/v1/intelligence/reflect
  \033[1;32mAI Security   \033[0m: {url}/api/v1/security/assess
  \033[1;32mLearning      \033[0m: {url}/api/v1/learning/status
  \033[1;32mPersonality   \033[0m: {url}/api/v1/personality/profile
  \033[1;32mSystem        \033[0m: {url}/api/v1/system/status

  Logs: {LOG_PATH}

  \033[0;33mQuick test:\033[0m
  curl -X POST {url}/api/v1/chat/ \\
    -H 'Content-Type: application/json' \\
    -d '{{"prompt":"Hello SuperAI V11! What can you do?","max_tokens":128}}'
""")


def main():
    args = parse_args()
    banner("SuperAI V11 — Colab Launcher")

    device  = check_gpu()
    features = [f.strip() for f in args.features.split(",") if f.strip()] if args.features else []

    if not args.no_install:
        install_deps()

    create_dirs()
    patch_config(device, args.model, args.no_v10, features)

    proc = start_server()
    url  = open_tunnel(args.token, args.port)
    print_summary(url)

    # Store URL in env for test cells
    os.environ["SUPERAI_V10_URL"] = url

    info("Server running. Press Ctrl+C to stop.")
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        print("\n👋 SuperAI V11 stopped.")


if __name__ == "__main__":
    main()
