# SuperAI V11

SuperAI V11 is a full-stack AI assistant platform with a FastAPI backend and a Next.js frontend. The repository now defaults to a simplified, production-ready runtime: one clear backend entrypoint, feature-gated advanced modules, a stable frontend chat UI, and a Colab/ngrok flow that matches the actual codebase.

This README replaces the older split docs (`README2.md`, `REFACTOR_SUMMARY.md`, `RUN_INSTRUCTIONS.md`, and `COLAB_GUIDE.md`) so there is one source of truth.

## Current state

- Stable default mode: `minimal`
- Single backend entrypoint: [`run.py`](/B:/SuperAI/superai_v11_complete/superai_v11_final/run.py)
- Central execution controller: [`master_controller.py`](/B:/SuperAI/superai_v11_complete/superai_v11_final/backend/controllers/master_controller.py)
- Canonical runtime config: [`config.yaml`](/B:/SuperAI/superai_v11_complete/superai_v11_final/config/config.yaml)
- Canonical Python dependencies: [`requirements.txt`](/B:/SuperAI/superai_v11_complete/superai_v11_final/requirements.txt)
- Colab launcher aligned with the simplified runtime: [`run_colab_v11.py`](/B:/SuperAI/superai_v11_complete/superai_v11_final/scripts/run_colab_v11.py)

## Architecture

```text
Frontend (Next.js)
  ->
FastAPI App
  ->
API Router
  ->
MasterController
  ->
Security + Memory + Model Loader + Monitoring
  ->
Response
```

Default flow:

```text
User input
  -> security validation
  -> task understanding
  -> optional memory lookup
  -> prompt assembly
  -> model execution
  -> output filtering
  -> persistence + metrics
  -> response
```

Advanced systems remain in the repository, but they only activate through explicit feature gates.

## Repository structure

```text
superai_v11_final/
├── backend/
│   ├── api/
│   ├── app/
│   ├── config/
│   ├── controllers/
│   ├── core/
│   ├── intelligence/
│   ├── knowledge/
│   ├── memory/
│   ├── models/
│   ├── personality/
│   ├── rlhf/
│   ├── security_ai/
│   ├── services/
│   └── tools/
├── config/
│   └── config.yaml
├── docker/
├── frontend/
├── scripts/
├── tests/
├── requirements.txt
├── requirements-colab.txt
└── run.py
```

## What was fixed

### Backend fixes

The backend has been stabilized across the simplified runtime and the advanced optional paths. The main fixes include:

- startup/config correctness in [`settings.py`](/B:/SuperAI/superai_v11_complete/superai_v11_final/backend/config/settings.py)
- central minimal/advanced execution control in [`master_controller.py`](/B:/SuperAI/superai_v11_complete/superai_v11_final/backend/controllers/master_controller.py)
- dependency wiring and feature-gate loading in [`dependencies.py`](/B:/SuperAI/superai_v11_complete/superai_v11_final/backend/app/dependencies.py)
- WebSocket/chat flow consistency in [`chat_ws.py`](/B:/SuperAI/superai_v11_complete/superai_v11_final/backend/api/ws/chat_ws.py) and [`orchestrator.py`](/B:/SuperAI/superai_v11_complete/superai_v11_final/backend/core/orchestrator.py)
- RLHF, learning, memory, security, RAG, and monitoring fixes in:
  - [`rlhf_pipeline.py`](/B:/SuperAI/superai_v11_complete/superai_v11_final/backend/rlhf/rlhf_pipeline.py)
  - [`learning_pipeline.py`](/B:/SuperAI/superai_v11_complete/superai_v11_final/backend/intelligence/learning_pipeline.py)
  - [`advanced_memory.py`](/B:/SuperAI/superai_v11_complete/superai_v11_final/backend/memory/advanced_memory.py)
  - [`simple_memory_service.py`](/B:/SuperAI/superai_v11_complete/superai_v11_final/backend/services/simple_memory_service.py)
  - [`rag_engine.py`](/B:/SuperAI/superai_v11_complete/superai_v11_final/backend/knowledge/rag_engine.py)
  - [`ai_security.py`](/B:/SuperAI/superai_v11_complete/superai_v11_final/backend/security_ai/ai_security.py)
  - [`monitoring_service.py`](/B:/SuperAI/superai_v11_complete/superai_v11_final/backend/services/monitoring_service.py)
- tool execution hardening in [`tool_executor.py`](/B:/SuperAI/superai_v11_complete/superai_v11_final/backend/tools/tool_executor.py)
- upload limits and safer file handling in [`files.py`](/B:/SuperAI/superai_v11_complete/superai_v11_final/backend/api/v1/files.py)
- production/deployment cleanup in [`docker-compose.yml`](/B:/SuperAI/superai_v11_complete/superai_v11_final/docker/docker-compose.yml)

### Frontend fixes

The frontend now matches the stable backend path instead of assuming every advanced feature is live:

- stable minimal-mode panel loading in [`page.tsx`](/B:/SuperAI/superai_v11_complete/superai_v11_final/frontend/src/app/page.tsx)
- production build compatibility settings in [`next.config.js`](/B:/SuperAI/superai_v11_complete/superai_v11_final/frontend/next.config.js)
- isolated manual type-check config in [`tsconfig.typecheck.json`](/B:/SuperAI/superai_v11_complete/superai_v11_final/frontend/tsconfig.typecheck.json)
- cleaned package metadata in [`package.json`](/B:/SuperAI/superai_v11_complete/superai_v11_final/frontend/package.json)
- updated app metadata and branding in:
  - [`layout.tsx`](/B:/SuperAI/superai_v11_complete/superai_v11_final/frontend/src/app/layout.tsx)
  - [`AgentPanel.tsx`](/B:/SuperAI/superai_v11_complete/superai_v11_final/frontend/src/components/agents/AgentPanel.tsx)
  - [`Dashboard.tsx`](/B:/SuperAI/superai_v11_complete/superai_v11_final/frontend/src/components/dashboard/Dashboard.tsx)
  - [`VoiceUI.tsx`](/B:/SuperAI/superai_v11_complete/superai_v11_final/frontend/src/components/voice/VoiceUI.tsx)
  - [`store.ts`](/B:/SuperAI/superai_v11_complete/superai_v11_final/frontend/src/lib/store.ts)

### Colab and ngrok fixes

The old Colab flow was still targeting the pre-refactor config shape. That has been replaced with a runtime-aware path:

- simplified Colab launcher in [`run_colab_v11.py`](/B:/SuperAI/superai_v11_complete/superai_v11_final/scripts/run_colab_v11.py)
- matching local smoke runner in [`colab_smoke_v11.py`](/B:/SuperAI/superai_v11_complete/superai_v11_final/scripts/colab_smoke_v11.py)
- regression coverage in [`test_colab_launcher.py`](/B:/SuperAI/superai_v11_complete/superai_v11_final/tests/unit/test_colab_launcher.py)

The launcher can now:

- patch the current `config.yaml`
- start the backend in minimal or advanced mode
- optionally start the frontend
- print the correct backend and frontend ngrok URLs

## Feature gates

Feature flags live in [`config.yaml`](/B:/SuperAI/superai_v11_complete/superai_v11_final/config/config.yaml) under `features`.

Examples:

```yaml
features:
  enable_workflow: false
  enable_skills: false
  enable_context: false
  enable_judge: false
  enable_cognitive: false
  enable_reflection: false
  enable_learning: false
  enable_advanced_memory: false
  enable_parallel_agents: false
  enable_rag: false
  enable_self_improvement: false
  enable_model_registry: false
  enable_ai_security: false
  enable_multimodal: false
  enable_distributed: false
  enable_personality: false
  enable_rlhf: false
  enable_tools: false
  enable_consensus: false
  enable_code_review: false
  enable_debugging: false
  enable_voice: false
  enable_vision: false
  enable_feedback: false
  enable_agent: false
```

## Local run

### Backend

```bash
pip install -r requirements.txt
python run.py
```

Useful variants:

```bash
python run.py --mode advanced
python run.py --port 8080
python run.py --reload
```

Check:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/system/status
curl -X POST http://localhost:8000/api/v1/chat/ \
  -H "Content-Type: application/json" \
  -d "{\"prompt\":\"Hello SuperAI\",\"session_id\":\"demo-001\"}"
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Create `frontend/.env.local` if needed:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=http://localhost:8000
NEXT_PUBLIC_ENABLE_ADVANCED_TABS=false
```

## Google Colab and ngrok

Install:

```python
!git clone https://github.com/lucifer9112/SuperAI_V11.git
%cd /content/SuperAI_V11
!python -m pip install -q --upgrade pip
!python -m pip install -q -r requirements-colab.txt
```

### Local smoke test in Colab

```python
!python scripts/colab_smoke_v11.py --strict-features
```

Advanced smoke test example:

```python
!python scripts/colab_smoke_v11.py --mode advanced --features F5,S2 --strict-features
```

### Public backend with ngrok

```python
NGROK_TOKEN = "your_ngrok_token"
!python scripts/run_colab_v11.py --token "$NGROK_TOKEN"
```

### Full backend + frontend UI in Colab

```python
NGROK_TOKEN = "your_ngrok_token"
!python scripts/run_colab_v11.py --token "$NGROK_TOKEN" --with-frontend
```

Use:

- backend URL + `/docs`: API testing
- frontend URL: actual user interface

### Advanced Colab run

```python
NGROK_TOKEN = "your_ngrok_token"
!python scripts/run_colab_v11.py --token "$NGROK_TOKEN" --mode advanced --features F5,S2 --with-frontend
```

Feature IDs accepted by the launcher:

- `F1` reflection
- `F2` learning
- `F3` advanced memory
- `F4` parallel agents
- `F5` RAG
- `F6` self improvement
- `F7` model registry
- `F8` AI security
- `F9` multimodal
- `F10` distributed
- `F11` workflow
- `S1` RLHF
- `S2` tools
- `S3` consensus

You can also pass full gate names like `enable_voice`.

## Verification

Current verification after the latest fixes:

- `python -m pytest -q` -> `207 passed`
- `npm run type-check` -> passed
- `npm run build` -> passed in unrestricted verification
- `python -m py_compile scripts/run_colab_v11.py scripts/colab_smoke_v11.py` -> passed

## Notes

- Minimal mode is the recommended default.
- Advanced systems are available, but should be enabled gradually.
- The backend `/health` URL is not the user interface.
- For browser users, open the frontend URL when the frontend is running.
