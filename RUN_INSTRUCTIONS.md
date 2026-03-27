# Run Instructions

## Local

Install and start the minimal service:

```bash
pip install -r requirements.txt
python run.py
```

Optional flags:

```bash
python run.py --mode advanced
python run.py --port 8080
python run.py --reload
```

Check:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/system/status
```

Example chat request:

```bash
curl -X POST http://localhost:8000/api/v1/chat/ \
  -H "Content-Type: application/json" \
  -d "{\"prompt\":\"Hello SuperAI\",\"session_id\":\"demo-001\"}"
```

## Google Colab

### Full local smoke test

Runs server locally, executes the smoke suite, and shuts the server down:

```python
!python scripts/colab_smoke_v11.py --strict-features
```

### Live public testing with ngrok

```python
NGROK_TOKEN = "your_token_here"
!python scripts/run_colab_v11.py --token "$NGROK_TOKEN" --no-install
```

Use the printed public URL in your browser for manual testing.

## Recommended Rollout

1. Boot with `python run.py`.
2. Confirm `/health` and `/docs`.
3. Test `POST /api/v1/chat/`.
4. Only then switch to `--mode advanced`.
5. Enable advanced feature flags one at a time in `config/config.yaml`.
