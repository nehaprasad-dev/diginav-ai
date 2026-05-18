# Implementation Plan

- [x] 1. Project scaffolding and monorepo setup
  - [x] 1.1 Initialize Next.js 15 frontend with App Router, Tailwind CSS, and shadcn/ui
    - Create Next.js app with TypeScript, App Router, Tailwind CSS configured
    - Install and configure shadcn/ui, Framer Motion, Zustand
    - Set up `lib/types.ts` with the full `AgentEvent` discriminated union from the design
    - Create `.env.example` with placeholder keys (GROQ_API_KEY, BACKEND_URL)
    - _Requirements: 6.1_

  - [ ] 1.2 Initialize FastAPI backend with project structure
    - Create `backend/` with `pyproject.toml`, FastAPI app, pydantic Settings, CORS config
    - Set up directory structure: `routers/`, `core/`, `store/`, `models/`
    - Create `AgentRuntime` Protocol in `core/agent_runtime.py`
    - Create `.env.example` with placeholder keys (GROQ_API_KEY, DATABASE_URL, ADMIN_TOKEN)
    - _Requirements: 5.1, 5.5_

  - [x] 1.3 Set up PostgreSQL schema and migrations
    - Install SQLAlchemy async + asyncpg + Alembic
    - Create initial migration with `sessions`, `chat_messages`, `workflows`, `events` tables per design
    - Write `store/db.py` with async session factory
    - _Requirements: 5.2, 8.1_

- [x] 2. LLM client and intent classification
  - [x] 2.1 Implement Groq streaming LLM client with retry and fallback
    - Create `core/llm_client.py` with `stream_narration()` method
    - Implement retry logic (3 attempts, exponential backoff, 15s timeout per Req 5.6)
    - Implement scripted fallback dict for all 3 flows when Groq is unreachable (Req 7.4)
    - Write unit tests: successful stream, timeout → retry → success, all retries fail → fallback
    - _Requirements: 5.6, 7.4_

  - [x] 2.2 Implement intent classifier
    - Create `core/intent_classifier.py` that uses Groq to classify user message into one of 3 flows or `general_chat`
    - Use a structured prompt with few-shot examples for reliable classification
    - Write unit tests with 30 representative prompts (10 per flow + 5 off-topic + 5 edge cases)
    - _Requirements: 1.4, 1.5_

- [x] 3. Flow simulator (AgentRuntime Week 1 implementation)
  - [x] 3.1 Create declarative flow definitions for all 3 workflows
    - Define `Step` dataclass with id, title, duration_range, narration_prompt, requires_human, final_output_template
    - Create `core/flows/incorporation.py` with 8 steps per Req 3.1
    - Create `core/flows/gst_filing.py` with 6 steps per Req 3.2
    - Create `core/flows/se_license.py` with 5 steps per Req 3.3
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 3.2 Implement FlowSimulator that walks step lists and emits AgentEvents
    - Create `core/flow_simulator.py` implementing `AgentRuntime` Protocol
    - For each step: emit `step_update(in_progress)`, call LLM for narration (emit tokens), sleep randomized duration (3–15s), emit `step_update(completed)`
    - On `requires_human` steps: emit `awaiting_human` and pause until `resume()` is called
    - On final step: emit `workflow_completed` with generated output (CIN, ARN, license number)
    - Write unit tests with mocked LLM verifying full event sequence for each flow
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 5.1_

- [ ] 4. Backend API endpoints (streaming + state)
  - [ ] 4.1 Implement POST /api/chat endpoint
    - Accept `{ sessionId, message, messageId }`, deduplicate on messageId
    - Persist user message to `chat_messages` table
    - Call intent classifier
    - If flow detected: create workflow row, start FlowSimulator in background task
    - Return `{ streamUrl: "/api/stream/{sessionId}" }` with 202 status
    - _Requirements: 5.1, 1.4_

  - [ ] 4.2 Implement GET /api/stream/{sessionId} SSE endpoint
    - Stream `AgentEvent`s as SSE `data:` lines with `event:` type field
    - Keep connection alive with periodic heartbeat (`:ping` comment every 15s)
    - On client disconnect, keep workflow running server-side (state in PG)
    - Write integration test: POST chat → GET stream → verify event sequence
    - _Requirements: 5.1, 5.2, 1.2_

  - [ ] 4.3 Implement GET /api/workflows/{workflowId} state endpoint
    - Return full workflow snapshot (steps with statuses, current index, output if completed)
    - Used by frontend on reconnect/refresh to rehydrate dashboard
    - Write integration test: start workflow → GET state mid-flow → verify matches
    - _Requirements: 5.3, 7.1_

  - [ ] 4.4 Implement POST /api/workflows/{workflowId}/resume endpoint
    - Accept `{ approvalId, approved: bool }`, deduplicate on approvalId
    - Signal FlowSimulator to continue (or mark step rejected and fail workflow)
    - Resume emitting events on the SSE stream
    - Write integration test: start → await_human → resume → workflow_completed
    - _Requirements: 5.4, 2.5, 2.6_

  - [ ] 4.5 Implement event logging middleware
    - Create `store/event_logger.py` that writes to `events` table
    - Log: message_sent, workflow_started, workflow_completed, workflow_failed, approval_granted
    - Hash prompts with SHA256, never store raw PII
    - _Requirements: 8.1, 8.2, 8.4_

- [ ] 5. Frontend chat interface
  - [ ] 5.1 Build ChatPanel with message list, input, and suggested prompts
    - Create `ChatPanel.tsx` with scrollable message list and sticky input bar
    - Create `SuggestedPrompts.tsx` showing 3 starter prompts on empty state
    - Create `MessageBubble.tsx` with user/assistant styling and streaming token append
    - Implement Enter to send, Shift+Enter for newline
    - _Requirements: 1.1, 1.7_

  - [ ] 5.2 Implement SSE client with reconnect and Zustand integration
    - Create `lib/sse.ts`: fetch-based SSE parser that handles typed `AgentEvent`s
    - Implement exponential backoff reconnect (1s → 30s cap) per Req 7.2
    - On each event, dispatch to Zustand store (append token, update step, etc.)
    - Create `ReconnectBanner.tsx` that shows when connection is dropped
    - _Requirements: 1.2, 1.3, 7.2_

  - [ ] 5.3 Implement Zustand store with persistence
    - Create `lib/store.ts` with slices: chat (messages), workflows (active + history), session (id, profile)
    - Use Zustand `persist` middleware with localStorage for Req 1.6 / 7.1
    - On page load: hydrate from localStorage, then call GET /api/workflows/:id to sync server state
    - _Requirements: 1.6, 7.1_

  - [ ] 5.4 Implement typing indicator and streaming token rendering
    - Create `TypingIndicator.tsx` with animated dots shown while `token` events arrive
    - Append tokens to the current assistant message bubble in real-time
    - Ensure first token renders within 500ms of message send (measure in Playwright test)
    - _Requirements: 1.3_

- [ ] 6. Frontend workflow dashboard
  - [ ] 6.1 Build WorkflowDashboard layout with WorkflowCard and StepCards
    - Create split-pane layout: chat left, dashboard right (responsive: stacked on mobile)
    - Create `WorkflowCard.tsx` showing flow name, progress bar, step count, ETA
    - Create `StepCard.tsx` with 4 visual states (pending, in_progress, completed, blocked_awaiting_human)
    - Animate state transitions with Framer Motion, no layout shift
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ] 6.2 Implement live sub-status updates on in-progress steps
    - When `step_update` event has `subStatus`, display it as a secondary line in the StepCard
    - Update at least every 2 seconds (driven by backend events)
    - _Requirements: 2.4_

  - [ ] 6.3 Implement HumanApprovalGate component
    - Create `HumanApprovalGate.tsx` with Approve and Reject buttons
    - On Approve: call POST /api/workflows/:id/resume, disable buttons, show spinner
    - On Reject: call resume with `approved: false`, show workflow cancelled state
    - Resume within 1 second of click
    - _Requirements: 2.5, 2.6_

  - [ ] 6.4 Implement workflow completion summary
    - When `workflow_completed` event arrives, show success card with output data (CIN, ARN, license number)
    - Generate and offer a downloadable dummy PDF certificate
    - _Requirements: 2.7_

- [ ] 7. Compliance Health Snapshot
  - [ ] 7.1 Implement backend POST /api/health-check endpoint
    - Accept business profile fields (name, type, state, founded_at, cin, gstin, se_license, last_filing_date)
    - Compute rule-based health score per design (4 sub-indicators, weighted total)
    - Return `HealthReport` JSON
    - _Requirements: 4.1, 4.2_

  - [ ] 7.2 Build ComplianceHealthCard and HealthSubIndicator components
    - Create `ComplianceHealthCard.tsx` showing overall score out of 100
    - Create `HealthSubIndicator.tsx` for each of 4 areas with colored status (green/amber/red) and one-line explanation
    - On click: expand drill-down with specific items and "Start this flow" CTA
    - If no profile entered: show soft prompt card inviting 2-minute scan with privacy copy
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [ ] 8. Admin analytics page
  - [ ] 8.1 Implement GET /api/admin/stats and GET /api/admin/events endpoints
    - Gate with `X-Admin-Token` header check against env var
    - `/stats`: return total sessions, workflows started, completed, failed
    - `/events`: return last 50 events ordered by created_at DESC
    - _Requirements: 8.3_

  - [ ] 8.2 Build /admin page in Next.js
    - Create `app/admin/page.tsx` with token input (stored in sessionStorage)
    - Display stats cards and scrollable events table
    - Auto-refresh every 30 seconds
    - _Requirements: 8.3_

- [ ] 9. Demo resilience and polish
  - [ ] 9.1 Implement "Try a sample flow" quick demo mode
    - On welcome screen, add a "Try a sample flow" button that runs a pre-recorded Incorporation flow
    - Use scripted responses (no LLM call) so it completes in under 60 seconds
    - _Requirements: 7.3_

  - [ ] 9.2 Implement skeleton loading states
    - Create `SkeletonChat.tsx` and `SkeletonDashboard.tsx` shown during initial load
    - Ensure LCP under 3 seconds on slow 3G (test with Lighthouse throttling)
    - _Requirements: 6.4_

  - [ ] 9.3 Accessibility pass
    - Add aria-live region to chat message list
    - Ensure all interactive elements have accessible labels
    - Ensure step states are communicated via text/icon, not color alone
    - Run axe-core in Playwright tests, zero serious violations
    - _Requirements: 6.5_

  - [ ] 9.4 Responsive layout verification
    - Test and fix layout at desktop (>=1024px), tablet (768–1023px), and mobile (<768px)
    - No horizontal scroll, no clipped content at any breakpoint
    - _Requirements: 6.2_

- [ ] 10. End-to-end tests and CI
  - [ ] 10.1 Write Playwright E2E tests for core flows
    - Happy path: send "File my Q4 GST" → dashboard appears → steps progress → approve → completion card
    - Refresh mid-flow: state persists
    - Network kill: reconnect banner appears, stream resumes
    - Groq down (mocked): fallback narration completes the flow
    - _Requirements: 7.1, 7.2, 7.4, 3.1, 3.2, 3.3_

  - [ ] 10.2 Set up CI pipeline
    - GitHub Actions workflow: lint (ruff + eslint), typecheck (mypy + tsc), unit tests, integration tests (with PG service container), Playwright smoke
    - Vercel preview deploys for frontend PRs
    - Railway preview for backend PRs (or Docker-based test)
    - _Requirements: 5.5 (reliability)_
