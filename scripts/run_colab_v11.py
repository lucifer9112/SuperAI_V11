#!/usr/bin/env python3
"""
SuperAI V11 — scripts/run_colab_v11.py

One-command Colab launcher.

Usage:
  !python scripts/run_colab_v11.py --token YOUR_NGROK_TOKEN

Options:
  --token  TOKEN    ngrok authtoken
  --model  MODEL    override default model
  --no-install      skip pip install
  --safe-mode       disable V11 features (run V10-compat)
  --features F1,S2  enable specific features only
"""
import argparse, os, subprocess, sys, time, yaml
from pathlib import Path

PROJECT = Path(__file__).parent.parent.resolve()
DATA    = Path("/content/superai_v11_data")
LOG     = DATA / "logs" / "server.log"


def p_ok(m):   print(f"  \033[32m✓ {m}\033[0m")
def p_info(m): print(f"  \033[34mℹ {m}\033[0m")
def p_warn(m): print(f"  \033[33m⚠ {m}\033[0m")
def p_fail(m): print(f"  \033[31m✗ {m}\033[0m"); sys.exit(1)
def p_head(m): print(f"\n\033[1;36m{'─'*55}\n  {m}\n{'─'*55}\033[0m")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--token",       default=os.getenv("NGROK_TOKEN",""))
    p.add_argument("--port",        default=8000, type=int)
    p.add_argument("--model",       default="TinyLlama/TinyLlama-1.1B-Chat-v1.0")
    p.add_argument("--no-install",  action="store_true")
    p.add_argument("--safe-mode",   action="store_true",
                   help="Disable V10+V11 features, run baseline only")
    p.add_argument("--features",    default="",
                   help="Comma-separated feature IDs e.g. F1,F5,S1,S2")
    return p.parse_args()


def check_gpu():
    r = subprocess.run(["nvidia-smi","--query-gpu=name,memory.total",
                        "--format=csv,noheader"], capture_output=True, text=True)
    if r.returncode == 0:
        p_ok(f"GPU: {r.stdout.strip()}")
        return "cuda"
    p_warn("No GPU — CPU mode")
    return "cpu"


def install_deps():
    p_head("Installing dependencies")
    subprocess.run(["apt-get","update","-qq"], check=True, capture_output=True)
    subprocess.run(["apt-get","install","-y","-qq","ffmpeg","libsndfile1"],
                   check=True, capture_output=True)
    p_ok("System packages")
    req = PROJECT / "requirements" / "colab.txt"
    r   = subprocess.run([sys.executable,"-m","pip","install","-q","-r",str(req)],
                         capture_output=True, text=True)
    if r.returncode != 0: p_warn(f"Some packages failed (non-fatal):\n{r.stderr[-300:]}")
    else:                  p_ok("Python packages installed")


def create_dirs():
    for d in [DATA/"logs", DATA/"uploads", DATA/"vector_db", DATA/"training",
              DATA/"rlhf_checkpoints", DATA/"reward_model", DATA/"improvement_logs",
              DATA/"security_logs", DATA/"rlhf_checkpoints"]:
        d.mkdir(parents=True, exist_ok=True)
    p_ok(f"Data dirs: {DATA}")


def patch_config(device, model, safe_mode, features):
    p_head("Patching config.yaml for Colab")
    cfg_path = PROJECT / "config" / "config.yaml"
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)

    # Server
    cfg["server"].update({"host":"0.0.0.0","port":8000,"reload":False,
                           "workers":1,"cors_origins":["*"]})
    # Models
    cfg["models"]["device"]     = device
    cfg["models"]["cache_size"] = 1
    for k in ["chat","code","reasoning","agent","fast","reflection"]:
        cfg["models"]["routing"][k] = model
    cfg["models"]["routing"]["vision"] = ""

    # Data paths
    path_map = {
        ("memory","db_path"):                       str(DATA/"superai_v11.db"),
        ("memory","vector_db_path"):                str(DATA/"vector_db/"),
        ("advanced_memory","episodic_db_path"):     str(DATA/"episodic.db"),
        ("advanced_memory","semantic_graph_path"):  str(DATA/"knowledge_graph.pkl"),
        ("feedback","store_path"):                  str(DATA/"feedback.db"),
        ("files","upload_dir"):                     str(DATA/"uploads/"),
        ("logging","file"):                         str(DATA/"logs/superai_v11.log"),
        ("self_improvement","failure_log_path"):    str(DATA/"improvement_logs/"),
        ("self_improvement","improvement_db_path"): str(DATA/"improvements.db"),
        ("ai_security","anomaly_log_path"):         str(DATA/"security_logs/"),
        ("learning","dataset_path"):                str(DATA/"training/"),
        ("learning","lora_output_dir"):             str(DATA/"lora_checkpoints/"),
        ("model_registry","registry_path"):         str(DATA/"model_registry.json"),
    }
    if "rlhf" in cfg:
        cfg["rlhf"]["rlhf_output_dir"] = str(DATA/"rlhf_checkpoints/")
        cfg["rlhf"]["rlhf_log_db"]     = str(DATA/"rlhf_logs.db")

    for (sec,key),val in path_map.items():
        if sec in cfg and isinstance(cfg[sec],dict): cfg[sec][key] = val

    cfg["voice"]["enabled"]       = False
    cfg["logging"]["format"]      = "text"
    cfg["logging"]["level"]       = "INFO"

    if safe_mode:
        for sec in ["reflection","learning","advanced_memory","parallel_agents","rag",
                    "self_improvement","model_registry","ai_security","multimodal",
                    "distributed","rlhf","tools","consensus"]:
            if sec in cfg and isinstance(cfg[sec],dict):
                cfg[sec]["enabled"] = False
        p_warn("Safe mode — V10/V11 features disabled")
    elif features:
        # Feature ID → config section mapping
        feat_map = {
            "F1":"reflection","F2":"learning","F3":"advanced_memory","F4":"parallel_agents",
            "F5":"rag","F6":"self_improvement","F7":"model_registry","F8":"ai_security",
            "F9":"multimodal","F10":"distributed","F11":"reflection",
            "S1":"rlhf","S2":"tools","S3":"consensus",
        }
        enabled_secs = {feat_map[f] for f in features if f in feat_map}
        for sec in feat_map.values():
            if sec in cfg and isinstance(cfg[sec],dict):
                cfg[sec]["enabled"] = sec in enabled_secs
        p_info(f"Features enabled: {features}")

    with open(cfg_path,"w") as f:
        yaml.dump(cfg, f, default_flow_style=False)

    (PROJECT/".env").write_text(
        f"SECRET_KEY=colab-v11-key\nMODELS__DEVICE={device}\n"
        f"LOGGING__LEVEL=INFO\nSERVER__PORT=8000\n")
    p_ok(f"Config patched — device={device}, model={model.split('/')[-1]}")


def start_server():
    p_head("Starting SuperAI V11 backend")
    subprocess.run(["pkill","-f","uvicorn"], capture_output=True)
    time.sleep(1)
    sys.path.insert(0, str(PROJECT))
    os.chdir(PROJECT)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    log_fh = open(LOG,"w")
    proc   = subprocess.Popen(
        [sys.executable,"-m","uvicorn","backend.main:app",
         "--host","0.0.0.0","--port","8000","--log-level","info","--no-access-log"],
        cwd=str(PROJECT), stdout=log_fh, stderr=subprocess.STDOUT,
        env={**os.environ,"PYTHONPATH":str(PROJECT)})

    import urllib.request
    for i in range(90):
        time.sleep(2)
        try:
            urllib.request.urlopen("http://localhost:8000/health", timeout=3)
            p_ok(f"Server ready after {i*2}s")
            return proc
        except Exception:
            if proc.poll() is not None:
                print(LOG.read_text()[-3000:])
                p_fail("Server died — check logs above")
            if i % 10 == 9: p_info(f"Still starting… ({i*2}s)")
    p_fail("Server timeout after 180s")


def open_tunnel(token, port):
    p_head("Opening ngrok tunnel")
    try:
        from pyngrok import ngrok
        if token: ngrok.set_auth_token(token)
        else:     p_warn("No token — anonymous tunnel (limited)")
        t   = ngrok.connect(port, "http")
        url = t.public_url
        p_ok(f"Tunnel: {url}")
        return url
    except ImportError: p_fail("pyngrok not found: pip install pyngrok")
    except Exception as e: p_fail(f"ngrok error: {e}")


def print_summary(url):
    p_head("🚀 SuperAI V11 is LIVE!")
    endpoints = [
        ("Public URL",        url),
        ("API Docs",          f"{url}/docs"),
        ("Health",            f"{url}/health"),
        ("Chat",              f"{url}/api/v1/chat/"),
        ("",                  ""),
        ("── V11 Step 1 RLHF ──",""),
        ("RLHF Status",       f"{url}/api/v1/rlhf/status"),
        ("Train DPO",         f"{url}/api/v1/rlhf/train/dpo"),
        ("Train GRPO",        f"{url}/api/v1/rlhf/train/grpo"),
        ("Score Response",    f"{url}/api/v1/rlhf/score"),
        ("",                  ""),
        ("── V11 Step 2 Tools ──",""),
        ("List Tools",        f"{url}/api/v1/tools/list"),
        ("Call Tools",        f"{url}/api/v1/tools/call"),
        ("Execute Tool",      f"{url}/api/v1/tools/execute"),
        ("",                  ""),
        ("── V11 Step 3 Consensus ──",""),
        ("Consensus Run",     f"{url}/api/v1/consensus/run"),
        ("Consensus Status",  f"{url}/api/v1/consensus/status"),
        ("",                  ""),
        ("System Status",     f"{url}/api/v1/system/status"),
        ("AI Security",       f"{url}/api/v1/security/assess"),
        ("RAG Knowledge",     f"{url}/api/v1/knowledge/retrieve"),
    ]
    for label, val in endpoints:
        if not label and not val: print()
        elif not val: print(f"  \033[1;33m{label}\033[0m")
        else: print(f"  \033[32m{label:20s}\033[0m: {val}")
    print(f"\n  Logs: {LOG}")
    print(f"\n  Quick test:")
    print(f'  curl -X POST {url}/api/v1/chat/ \\')
    print(f'    -H "Content-Type: application/json" \\')
    print(f'    -d \'{{"prompt":"Hello V11! What can you do?","max_tokens":128}}\'')


def main():
    args = parse_args()
    p_head("SuperAI V11 — Colab Launcher")

    device   = check_gpu()
    features = [f.strip() for f in args.features.split(",") if f.strip()] if args.features else []

    if not args.no_install: install_deps()
    create_dirs()
    patch_config(device, args.model, args.safe_mode, features)
    proc = start_server()
    url  = open_tunnel(args.token, args.port)
    print_summary(url)

    os.environ["SUPERAI_V11_URL"] = url
    p_info("Press Ctrl+C to stop")
    try:   proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        print("\n👋 SuperAI V11 stopped.")

if __name__ == "__main__":
    main()
