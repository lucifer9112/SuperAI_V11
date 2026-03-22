#!/usr/bin/env python3
"""
Notebook-friendly local smoke test runner for SuperAI V11 on Google Colab.

This script:
1. Installs / verifies runtime deps
2. Patches config for Colab
3. Starts the backend locally
4. Runs the full smoke suite against localhost
5. Stops the local backend

Example:
  python scripts/colab_smoke_v11.py --safe-mode
  python scripts/colab_smoke_v11.py --features F1,F2,F4,F5,F6,F7,F8,F10,F11,S1,S2,S3 --strict-features
"""

from __future__ import annotations

import argparse
import sys

from run_colab_v11 import (
    check_gpu,
    create_dirs,
    install_deps,
    p_head,
    p_info,
    patch_config,
    start_server,
    verify_runtime_deps,
)
from smoke_test_v11 import SmokeTester


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run SuperAI V11 smoke tests locally on Colab.")
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
    parser.add_argument("--timeout", type=int, default=120, help="Per-request timeout in seconds")
    parser.add_argument(
        "--strict-features",
        action="store_true",
        help="Treat disabled optional features as failures",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    p_head("SuperAI V11 - Colab Local Smoke Test")

    device = check_gpu()
    features = [item.strip() for item in args.features.split(",") if item.strip()]

    if not args.no_install:
        install_deps(args.safe_mode)
    verify_runtime_deps()
    create_dirs()
    patch_config(device, args.model, args.port, args.safe_mode, features)

    proc = start_server(args.port)
    base_url = f"http://127.0.0.1:{args.port}"
    p_info(f"Running smoke suite against {base_url}")

    try:
        tester = SmokeTester(base_url, args.timeout, args.strict_features)
        return tester.run()
    finally:
        p_info("Stopping local test server")
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
