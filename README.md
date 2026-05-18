# DigiNav AI

**Autonomous regulatory compliance agent for Indian MSMEs and startups.**

DigiNav AI eliminates the pain of navigating India's complex regulatory landscape. Instead of spending weeks decoding government portals, founders simply describe what they need in plain language — and DigiNav handles the rest.

This repository contains the **Week 1 MVP**: a production-grade, demo-ready web application where a founder chats with DigiNav in natural language and watches the AI agent plan, narrate, and progress through realistic multi-step regulatory workflows on a live dashboard.

---

## The Problem We're Solving

Indian MSMEs and startups face a brutal compliance burden:

- **Company Incorporation** requires navigating SPICe+, DIN applications, DSC issuance, MoA/AoA drafting, PAN/TAN allotment — across multiple portals with different logins.
- **GST Filing** means reconciling GSTR-2B, computing tax liability, generating GSTR-3B, and submitting before deadlines — every quarter.
- **Shops & Establishment License** varies by state, with different forms, different rules, and zero standardization.

Most founders either hire expensive CAs, miss deadlines, or spend days on government websites. DigiNav replaces all of that with a single conversational interface backed by an AI agent that understands Indian regulatory processes end-to-end.

---

## What This MVP Does

The Week 1 MVP is designed to be shown to 5–10 Mumbai SMEs to validate demand and sell paid compliance health scans. It demonstrates the full product vision with:

### Conversational Chat Interface
- Full-screen chat where founders describe their compliance need in plain English or Hindi
- Real LLM responses (Groq Llama-3.3-70b) streamed token-by-token via Server-Sent Events
- Intent detection that automatically triggers the right workflow when a user says something like "Incorporate my Pvt Ltd" or "File my Q4 GST"
- Three suggested prompts on first load for instant engagement
- Session persistence — refresh the page and nothing is lost

### Real-Time Workflow Dashboard
- Split-view layout: chat on the left, live workflow progress on the right
- Each workflow step rendered as a card with four visual states: pending, in-progress, completed, or blocked-awaiting-human
- Live sub-status updates every 2 seconds ("Fetching PAN from DigiLocker...", "Validating director DIN...")
- Animated transitions via Framer Motion with no layout shift
- Human approval gates where the workflow pauses and waits for explicit user confirmation before proceeding
- Success summary with simulated output (CIN numbers, ARN codes, license numbers) and downloadable dummy PDF

### Three Showcase Regulatory Flows

| Flow | Steps | What It Simulates |
|------|-------|-------------------|
| **Company Incorporation (SPICe+)** | 8+ | Name reservation → DIN application → DSC issuance → MoA/AoA drafting → SPICe+ Part B → PAN/TAN allotment → CIN generation |
| **GST Filing (GSTR-3B)** | 6+ | Fetch sales data → Compute tax liability → Reconcile GSTR-2B → Generate GSTR-3B → Human approval → Submission with ARN |
| **Shops & Establishment License** | 5+ | Detect user's state → Fetch state-specific form → Pre-fill from profile → Human approval → License number issuance |

Each step takes 3–15 seconds to complete (realistic pacing, not instant). The LLM generates contextual narration for every step transition that appears in the chat in real time. Users can ask clarifying questions mid-flow ("What is DIN?") without interrupting the workflow.

### Compliance Health Snapshot
- One-glance compliance health score (0–100) based on business profile
- Four sub-indicators: Incorporation, GST, Labor, Annual Filings — each with colored status and one-line explanation
- Drill-down on each indicator showing specific items driving the score
- "Start this flow" CTA to trigger the relevant workflow directly

### Demo Resilience
- Page refresh mid-workflow restores everything within 2 seconds
- Network drops show a "Reconnecting..." banner with automatic exponential backoff
- If Groq is down, the system falls back to pre-scripted narration so the demo never fails
- "Try a sample flow" button runs a compressed Incorporation demo in under 60 seconds with zero external dependencies

### Admin Analytics
- `/admin` page (secret-gated) showing total sessions, workflows started/completed, and last 50 events
- All events logged to PostgreSQL with timestamps, session IDs, event types — no PII stored

---

## Architecture

### Design Philosophy

1. **Real front, simulated back.** The LLM is real. The conversational UX is real. The workflow engine is a deterministic simulator that looks and feels like the future LangGraph agent. Every interface the frontend sees (streaming events, state API, approval flow) is shaped to match what LangGraph will emit — so Week 2 is a backend-internal swap.

2. **One seam per future capability.** The architecture leaves a single, named integration point for each upcoming piece: `AgentRuntime` (→ LangGraph), `DPIGateway` (→ Aadhaar/GSTN/DigiLocker), `RegulatoryMemory` (→ Pinecone + PostgreSQL), `RiskScorer` (→ predictive model). In Week 1, each is a stub. In later weeks, each is replaced without touching callers.

3. **Demo-first, production-clean.** The app must survive a live pilot demo on shaky hotel WiFi. SSE with reconnect, server-side workflow state, scripted fallback if Groq is down, and skeleton loading everywhere — these are core, not polish.

### System Diagram

```mermaid
flowchart LR
    subgraph Client["Next.js 15 App (Vercel)"]
        UI[Chat + Dashboard UI]
        SW[Session Store — localStorage + Zustand]
        SSE[SSE Client with reconnect]
    end

    subgraph Backend["FastAPI Backend (Railway/Fly.io)"]
        API[REST + SSE Endpoints]
        AR[AgentRuntime interface]
        SIM[FlowSimulator — Week 1]
        LLM[LLMClient — Groq + fallback]
        WS[WorkflowStore]
        EV[EventLogger]
    end

    subgraph Data["Data Layer"]
        PG[(PostgreSQL)]
    end

    subgraph External["External"]
        GROQ[Groq API — Llama-3.3-70b]
    end

    UI -->|POST /api/chat| API
    UI <-->|SSE /api/stream/:sessionId| API
    UI -->|POST /api/workflows/:id/resume| API
    UI -->|GET /api/workflows/:id| API

    API --> AR
    AR -.Week 1.-> SIM
    AR -.Week 2+.-> LG[LangGraph Agent]
    SIM --> LLM
    LLM --> GROQ
    API --> WS
    API --> EV
    WS --> PG
    EV --> PG

    style LG stroke-dasharray: 5 5
```

### Request & Stream Lifecycle

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Next.js UI
    participant BE as FastAPI
    participant SIM as FlowSimulator
    participant G as Groq

    U->>FE: "File my Q4 GST"
    FE->>BE: POST /api/chat { sessionId, message }
    BE->>BE: persist message, classify intent
    BE-->>FE: 202 { streamUrl }
    FE->>BE: GET /api/stream/:sessionId (SSE)
    BE-->>FE: event: token (LLM narration)
    BE->>G: stream completion
    G-->>BE: tokens
    BE-->>FE: event: intent_detected { flow: "gst_filing" }
    BE-->>FE: event: workflow_started { workflowId, steps[] }
    loop each step (3–15s each)
        BE->>SIM: execute step
        BE-->>FE: event: step_update { idx, status, subStatus }
    end
    BE-->>FE: event: awaiting_human { stepIdx, prompt }
    U->>FE: clicks Approve
    FE->>BE: POST /api/workflows/:id/resume
    BE->>SIM: resume
    BE-->>FE: event: workflow_completed { output }
```

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Frontend | Next.js 15 (App Router), TypeScript, Tailwind CSS, shadcn/ui | Modern React with server components, accessible UI primitives |
| Animation | Framer Motion | Smooth step transitions without layout shift |
| State | Zustand (with persist middleware) | Low ceremony, SSE-friendly partial updates, free localStorage hydration |
| Backend | FastAPI, Python 3.11+ | Async-native, matches future LangGraph stack |
| Validation | Pydantic v2, pydantic-settings | Type-safe config and request/response models |
| Database | PostgreSQL 15+ (asyncpg driver) | Durable workflow state + analytics |
| ORM | SQLAlchemy 2.0 (async) | Async session factory, declarative models |
| Migrations | Alembic | Version-controlled schema changes |
| LLM | Groq API (Llama-3.3-70b-versatile) | Fast inference, streaming support |
| Streaming | SSE (sse-starlette) | Simpler than WebSocket, survives reverse proxies, auto-reconnects |
| PDF | @react-pdf/renderer or jsPDF (client-side) | Cosmetic certificates, no server-side generation needed |

---

## Project Structure

```
diginav-ai/
├── frontend/                       # Next.js 15 application
│   ├── app/
│   │   ├── layout.tsx              # Root layout with providers
│   │   ├── page.tsx                # Main split-view (chat + dashboard)
│   │   └── admin/page.tsx          # Protected analytics page
│   ├── components/
│   │   ├── chat/                   # ChatPanel, MessageBubble, SuggestedPrompts, TypingIndicator
│   │   ├── dashboard/              # WorkflowDashboard, StepCard, HumanApprovalGate, ComplianceHealthCard
│   │   ├── shared/                 # ReconnectBanner, SkeletonChat, SkeletonDashboard
│   │   └── ui/                     # shadcn/ui primitives (Button, Card, etc.)
│   ├── lib/
│   │   ├── types.ts                # AgentEvent discriminated union (frontend ↔ backend contract)
│   │   ├── store.ts                # Zustand store (chat, workflows, session slices)
│   │   ├── sse.ts                  # SSE client with exponential backoff reconnect
│   │   ├── api.ts                  # Fetch wrappers
│   │   └── persistence.ts          # localStorage hydrate/dehydrate
│   ├── public/                     # Static assets
│   ├── tailwind.config.ts
│   ├── next.config.mjs
│   ├── tsconfig.json
│   ├── package.json
│   └── .env.example
│
├── backend/                        # FastAPI server
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app, CORS middleware, router registration
│   │   ├── config.py               # Pydantic Settings (env-driven configuration)
│   │   ├── routers/
│   │   │   ├── chat.py             # POST /api/chat, GET /api/stream/:sessionId
│   │   │   ├── workflows.py        # GET /api/workflows/:id, POST /api/workflows/:id/resume
│   │   │   └── admin.py            # GET /api/admin/stats, GET /api/admin/events
│   │   ├── core/
│   │   │   ├── agent_runtime.py    # AgentRuntime Protocol (the single seam for LangGraph)
│   │   │   ├── events.py           # Typed event dataclasses (AgentEvent union)
│   │   │   ├── flow_simulator.py   # Week 1 implementation of AgentRuntime
│   │   │   ├── llm_client.py       # Groq streaming + scripted fallback
│   │   │   ├── intent_classifier.py # LLM-based intent → FlowId mapping
│   │   │   └── flows/
│   │   │       ├── incorporation.py # 8-step SPICe+ flow definition
│   │   │       ├── gst_filing.py    # 6-step GSTR-3B flow definition
│   │   │       └── se_license.py    # 5-step S&E license flow definition
│   │   ├── models/
│   │   │   ├── base.py             # SQLAlchemy DeclarativeBase
│   │   │   ├── session.py          # Session model (browser sessions, not auth)
│   │   │   ├── chat_message.py     # ChatMessage model
│   │   │   ├── workflow.py         # Workflow model (steps stored as JSONB)
│   │   │   └── event.py            # Event model (analytics, no PII)
│   │   └── store/
│   │       ├── db.py               # Async SQLAlchemy session factory
│   │       ├── workflow_store.py    # WorkflowStore (PG-backed CRUD)
│   │       └── event_logger.py     # EventLogger (analytics writes)
│   ├── migrations/
│   │   ├── env.py                  # Alembic async environment config
│   │   └── versions/
│   │       └── 166908ab7971_initial_schema.py
│   ├── tests/
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── .env.example
│
└── .kiro/specs/                    # Feature specifications
    └── diginav-mvp-chat-dashboard/
        ├── requirements.md
        ├── design.md
        └── tasks.md
```

---

## Getting Started

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Node.js | 18+ | Frontend runtime |
| Python | 3.11+ | Backend runtime |
| PostgreSQL | 15+ | Persistent storage |
| Groq API Key | — | LLM inference ([console.groq.com](https://console.groq.com)) |

### 1. Clone the Repository

```bash
git clone <repo-url>
cd diginav-ai
```

### 2. Frontend Setup

```bash
cd frontend
cp .env.example .env.local
# Edit .env.local — fill in GROQ_API_KEY and BACKEND_URL

npm install
npm run dev
# → http://localhost:3000
```

### 3. Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate    # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"

cp .env.example .env
# Edit .env — fill in GROQ_API_KEY, DATABASE_URL, ADMIN_TOKEN
```

### 4. Database Setup

```bash
# Create the PostgreSQL database
createdb diginav

# Run migrations
cd backend
alembic upgrade head
```

### 5. Run the Backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
# → http://localhost:8000/health
# → http://localhost:8000/docs (when DEBUG=true)
```

---

## Environment Variables

### Frontend (`frontend/.env.local`)

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `GROQ_API_KEY` | Yes | Groq API key for LLM streaming | — |
| `BACKEND_URL` | Yes | FastAPI backend URL | `http://localhost:8000` |

### Backend (`backend/.env`)

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `GROQ_API_KEY` | Yes | Groq API key for LLM streaming | — |
| `DATABASE_URL` | Yes | PostgreSQL connection string (asyncpg driver) | `postgresql+asyncpg://postgres:postgres@localhost:5432/diginav` |
| `ADMIN_TOKEN` | Yes | Secret token for `/api/admin/*` endpoints | `changeme` |
| `CORS_ORIGINS` | No | JSON array of allowed frontend origins | `["http://localhost:3000"]` |
| `GROQ_MODEL` | No | Groq model identifier | `llama-3.3-70b-versatile` |
| `DEBUG` | No | Enable verbose SQL logging and `/docs` endpoint | `false` |

---

## API Reference

### Chat & Streaming

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat` | Accept a user message, persist it, classify intent, return stream URL |
| `GET` | `/api/stream/{sessionId}` | SSE stream of typed `AgentEvent`s (tokens, workflow updates, errors) |

### Workflows

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/workflows/{workflowId}` | Fetch full workflow snapshot for UI rehydration after refresh/reconnect |
| `POST` | `/api/workflows/{workflowId}/resume` | Approve or reject a blocked step (idempotent via `approvalId`) |

### Admin (secret-gated via `X-Admin-Token` header)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/admin/stats` | Aggregated counts: sessions, workflows started/completed/failed |
| `GET` | `/api/admin/events` | Last 50 events with timestamps and metadata |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Simple health check returning `{"status": "ok"}` |

---

## Event Contract (Frontend ↔ Backend)

All SSE events follow a discriminated union. This is the contract that LangGraph must honor when it replaces the simulator in Week 2.

```typescript
type AgentEvent =
  | { type: "token"; text: string; messageId: string }
  | { type: "intent_detected"; flow: "incorporation" | "gst_filing" | "se_license"; confidence: number }
  | { type: "workflow_started"; workflowId: string; steps: StepSummary[] }
  | { type: "step_update"; workflowId: string; stepIdx: number;
      status: "pending" | "in_progress" | "completed" | "blocked_awaiting_human";
      subStatus?: string }
  | { type: "awaiting_human"; workflowId: string; stepIdx: number; prompt: string }
  | { type: "workflow_completed"; workflowId: string; output: Record<string, unknown> }
  | { type: "error"; message: string; correlationId: string; recoverable: boolean }
```

---

## Database Schema

Four tables, designed for simplicity and fast state restoration:

| Table | Purpose | Key Design Choice |
|-------|---------|-------------------|
| `sessions` | Browser sessions (not auth) with optional business profile | JSONB for flexible profile data |
| `chat_messages` | Full chat history per session | Indexed by (session_id, created_at) for ordered retrieval |
| `workflows` | Active and completed workflow state | Steps stored as JSONB — single row read restores full state |
| `events` | Analytics events (no PII) | Append-only, indexed by time, SHA256 prompt hashes only |

---

## Key Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| **FastAPI from day 1** (not Next.js API routes) | Matches the full LangGraph stack we're committed to. Keeps the streaming layer in one place. Avoids rewriting in Week 2. |
| **SSE over WebSocket** | One-way server push is all Week 1 needs. Simpler, survives reverse proxies, auto-reconnects natively. Socket.IO deferred to Week 3. |
| **Zustand over Redux** | Low ceremony, first-class persistence middleware, plays well with SSE-driven many-small-updates pattern. |
| **PostgreSQL, not Redis** | Durable workflow state + analytics. Redis is overkill for Week 1 throughput. Added later for pub/sub multi-replica fanout. |
| **Simulator is data-driven** | Each flow is a list of `Step` dataclasses, not hand-written code. Adding a 4th flow becomes a 30-minute config job. |
| **Scripted fallback is a feature** | A pilot demo that fails because Groq is down is a business loss. Fallback is explicit, tested, and always available. |
| **No auth in Week 1** | Session ID in cookie is enough. Pilot customers see their own session only. Full multi-tenant auth is a separate spec. |
| **JSONB for workflow steps** | Steps are tightly coupled to parent workflow, never queried across workflows. Single row read = instant state restore on refresh. |

---

## Roadmap: What Comes Next

| Week | Milestone | What Changes |
|------|-----------|--------------|
| **Week 1 (this MVP)** | Demo-ready chat + dashboard | FlowSimulator, scripted flows, Groq streaming |
| **Week 2** | Real agent core | `LangGraphAgent` replaces `FlowSimulator` behind the same `AgentRuntime` interface |
| **Week 3** | DPI Gateway | Real Aadhaar/GSTN/DigiLocker integrations via `DPIGateway` interface |
| **Week 4** | Regulatory Genome | Pinecone + embeddings for regulatory knowledge via `RegulatoryMemory` interface |
| **Week 5+** | Predictive risk, payments, multi-tenant auth, mobile push | `RiskScorer` ML model, Clerk/Auth.js, Stripe |

Every future capability plugs into a named interface that already exists as a stub in this codebase.

---

## Out of Scope (Week 1)

These are explicitly not part of this MVP and will be separate specs:

- Real DPI integrations (Aadhaar, GSTN, DigiLocker, MCA portals)
- Playwright-based portal automation
- Payments and billing
- Multi-tenant authentication with RBAC
- Mobile push notifications
- Predictive compliance risk model
- Voice/vision input
- Full Hindi UI localization (though Hindi chat works natively via the LLM)

---

## Development

### Linting & Type Checking

```bash
# Backend
cd backend
ruff check .
mypy app/

# Frontend
cd frontend
npm run lint
npx tsc --noEmit
```

### Running Tests

```bash
# Backend unit + integration tests
cd backend
pytest

# Frontend (when test suite is set up)
cd frontend
npm test
```

---

## License

Private — not open source.
