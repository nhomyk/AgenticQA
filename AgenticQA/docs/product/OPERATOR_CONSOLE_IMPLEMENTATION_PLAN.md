# Operator Console Implementation Plan (Streamlit + FastAPI)

## Goal
Turn Prompt Ops into a true **Operator Console**: chat-native orchestration with governed actions, persisted prompts, execution control, and full evidence traceability.

## Current foundation already in place
- Dashboard chat UI exists in Prompt Ops (`st.chat_input`, chat history rendering).
- Persisted chat storage exists (`chat_sessions`, `chat_messages`) in `PromptWorkflowStore`.
- Chat API exists:
  - `POST /api/chat/sessions`
  - `GET /api/chat/sessions`
  - `GET /api/chat/sessions/{id}`
  - `POST /api/chat/sessions/{id}/messages`
  - `POST /api/chat/turn`
- Workflow APIs and controls exist for approve/queue/run/replay/cancel.
- Observability and evidence APIs already provide audit-grade flow telemetry.

## Product definition (Operator Console)
The console should feel like one continuous command surface:
1. User asks for change in chat.
2. Assistant proposes actions + risk level.
3. User approves scoped actions.
4. System executes via workflow APIs.
5. Outcome and evidence are appended to chat timeline.
6. Baseline→delta and ROI impact are surfaced automatically.

## Architecture additions

### A) Control-plane LLM adapter layer (new)
Add a provider abstraction for BYO model calls:
- `src/agenticqa/operator_console/llm_adapter.py`
- Providers:
  - OpenAI-compatible endpoint
  - Anthropic (optional in phase 2)
  - Azure OpenAI (optional in phase 2)
- Contract:
  - `complete(messages, tools, settings) -> assistant_response`
- Safety constraints:
  - strict timeout
  - token caps
  - no direct execution side effects in model layer

### B) Tool router for governed actions (new)
Add deterministic tool gateway the assistant can call:
- `src/agenticqa/operator_console/tool_router.py`
- Supported tools (phase 1):
  - `create_workflow_request`
  - `get_workflow_status`
  - `approve_workflow_request`
  - `queue_workflow_request`
  - `run_workflow_request`
  - `get_portability_scorecard`
  - `save_portability_baseline`
  - `get_portability_roi_report`
- Every tool invocation must emit:
  - `who`, `what`, `when`, `request_id`, `trace_id`, `result`

### C) Policy gate (new)
Add a lightweight action policy evaluator:
- `src/agenticqa/operator_console/policy_gate.py`
- Initial rules:
  - write actions require explicit user approval
  - high-risk actions require `approved_by`
  - PR-opening path requires policy ticket

### D) Prompt ontology and persistence enrichment (existing schema extension)
Current DB tables already persist chat/workflow.
Add optional schema fields for ontology tags:
- `chat_messages.metadata.intent`
- `chat_messages.metadata.entities`
- `chat_messages.metadata.action_plan`
- `workflow_requests.metadata.chat_session_id`
- `workflow_events.note` include action origin (`chat_tool_call`, `manual_ui`, `worker`)

## API plan

### Existing endpoints to keep
- Keep `/api/chat/*` and `/api/workflows/*` as stable surface.

### New endpoints (phase 1)
- `GET /api/operator/config`  
  Return active provider, model, tool policy, limits (no secrets).
- `POST /api/operator/config/test-connection`  
  Validate provider settings.
- `POST /api/chat/turn` (enhanced)  
  Add optional mode:
  - `mode: deterministic|llm`
  - `tool_execution: suggest_only|require_approval|auto_for_safe`

### New endpoints (phase 2)
- `GET /api/chat/sessions/{id}/actions`  
  Return action timeline from tool invocations and workflow events.
- `POST /api/chat/sessions/{id}/approve-action`  
  Explicit approval handshake for queued action objects.

## Streamlit plan (Prompt Ops page)

### Phase 1 UI upgrades
- Add "Operator Console" section title (replace generic chat framing).
- Add provider status panel:
  - model provider
  - token budget
  - policy mode
- Add action cards under assistant messages:
  - suggested action
  - risk tag (low/med/high)
  - approve/reject buttons
- Add outcome cards:
  - linked workflow ID
  - latest status
  - last execution result

### Phase 2 UI upgrades
- Add left rail session picker + filters (repo, status, date).
- Add timeline view combining:
  - chat turns
  - workflow events
  - observability milestones
- Add one-click report export from active session (ROI + evidence bundle).

## Data flow (target)
1. User message arrives via `/api/chat/turn`.
2. Message persisted (`chat_messages`).
3. LLM adapter generates structured response + tool intents.
4. Policy gate validates intents.
5. Approved intents call tool router.
6. Tool outputs persisted as assistant/tool messages + workflow events.
7. Observability captures trace; ROI/evidence endpoint updates session context.

## Security and governance requirements
- Secrets never stored in plain text in chat metadata.
- PII-safe logging mode for message content.
- Per-action approval requirement for write operations.
- Immutable event trail for enterprise audit.

## 14-day delivery sequence

### Days 1-3
- Add LLM adapter abstraction
- Add operator config endpoint
- Enhance `/api/chat/turn` mode handling

### Days 4-6
- Build tool router with read-only actions first
- Add policy gate skeleton + approval state

### Days 7-9
- Add write-action flow (create/approve/queue/run)
- Persist action metadata and link to workflow IDs

### Days 10-12
- Upgrade Streamlit Operator Console UI cards + approvals
- Add action/result timeline blocks

### Days 13-14
- Test hardening + failure mode handling
- Pilot with Qdrant + Neo4j environment
- Publish operator quickstart

## Acceptance criteria
- A user can complete create→approve→queue→run workflow without leaving dashboard.
- Every action has traceable audit metadata.
- Chat sessions are replayable with full decision history.
- Prompt-to-outcome cycle is measurable through existing ROI endpoints.

## Immediate implementation note for current environment
Given Weaviate is expired, run Operator Console with:
- Qdrant as primary vector provider
- Neo4j for graph context
- Auto fallback enabled for vector backend resiliency
