# Requirements Document

## Introduction

DigiNav AI is an autonomous regulatory compliance agent for Indian MSMEs and startups. This spec covers the **Week 1 MVP**: a production-grade, demo-ready Next.js web application where a founder can chat with DigiNav in natural language and watch the agent plan, narrate, and progress through realistic multi-step regulatory workflows on a live dashboard.

The MVP does **not** yet connect to real government portals (Aadhaar, GSTN, DigiLocker). Instead, it uses a real LLM (Groq Llama-3.3-70b) for conversational intelligence and a deterministic flow simulator for three showcase journeys: **Company Incorporation (SPICe+)**, **GST Filing (GSTR-3B)**, and **Shops & Establishment License**. The goal is a believable, beautiful pilot demo that can be shown to 5–10 Mumbai SMEs to validate demand and sell paid compliance health scans.

This MVP is the foundation of the wider product. Every architectural decision here must leave clean seams for the real agent core (LangGraph/FastAPI), DPI gateway, and Regulatory Genome to slot in during later weeks.

**Out of scope for this spec:** real DPI integrations, Playwright portal automation, payments, multi-tenant auth with RBAC, mobile push notifications, the predictive risk model. Those are separate specs.

## Requirements

### Requirement 1: Conversational Chat Interface

**User Story:** As an Indian MSME founder, I want to describe my compliance need in plain English or Hindi through a chat interface, so that I can start a regulatory process without learning government jargon or navigating portals.

#### Acceptance Criteria

1. WHEN the user opens the application THEN the system SHALL display a full-screen chat interface with a welcome message, three suggested prompts ("Incorporate my Pvt Ltd", "File my Q4 GST", "Apply for Shops & Establishment license"), and a visible input field.
2. WHEN the user types a message and submits it THEN the system SHALL stream the assistant's response token-by-token using Groq Llama-3.3-70b over Server-Sent Events or WebSocket.
3. WHEN the assistant is generating a response THEN the system SHALL display a typing indicator and render partial tokens as they arrive with less than 500ms first-token latency under normal network conditions.
4. WHEN the user sends a message that matches one of the three supported flows (incorporation, GST filing, S&E license) THEN the system SHALL detect the intent and trigger the corresponding structured workflow on the dashboard.
5. IF the user sends a message outside the three supported flows THEN the system SHALL respond conversationally using the LLM and politely explain which flows are currently available.
6. WHEN the user refreshes the page THEN the system SHALL persist the current chat session and active workflow state in local storage so the conversation is not lost.
7. WHEN the user presses Enter without Shift THEN the system SHALL send the message, AND WHEN the user presses Shift+Enter THEN the system SHALL insert a newline.

### Requirement 2: Real-Time Agent Workflow Dashboard

**User Story:** As a founder, I want to see the agent's plan and live progress through a multi-step regulatory workflow, so that I trust the system is actually working and I know what is happening at every moment.

#### Acceptance Criteria

1. WHEN a workflow is triggered THEN the system SHALL display a dashboard panel alongside the chat showing the workflow name, total steps, current step, overall progress percentage, and estimated completion time.
2. WHEN the agent begins a workflow THEN the system SHALL render each step as a card with one of four visual states: pending, in-progress, completed, or blocked-awaiting-human.
3. WHEN a step transitions state THEN the system SHALL animate the transition using Framer Motion with no layout shift for other cards.
4. WHEN a step is in-progress THEN the system SHALL display a live sub-status line (e.g. "Fetching PAN from DigiLocker...", "Validating director DIN...") that updates at least every 2 seconds from the backend stream.
5. WHEN a step requires human approval (e.g. final submission, payment) THEN the system SHALL pause the workflow, change the step state to blocked-awaiting-human, and display an explicit Approve and Reject button.
6. WHEN the user clicks Approve on a blocked step THEN the system SHALL resume the workflow from that exact step within 1 second.
7. WHEN all steps complete THEN the system SHALL display a success summary card with the simulated output (e.g. "CIN: U72900MH2026PTC000001 generated") and a downloadable dummy PDF.

### Requirement 3: Three Demo Workflow Flows

**User Story:** As a prospective pilot customer watching a demo, I want to see DigiNav handle three of the most painful Indian compliance processes end-to-end, so that I am convinced it can handle my real workload.

#### Acceptance Criteria

1. WHEN the user triggers the Incorporation flow THEN the system SHALL execute a scripted but LLM-narrated sequence of at least 8 steps including name reservation (RUN), DIN application, DSC issuance, MoA/AoA drafting, SPICe+ Part B submission, PAN/TAN allotment, and CIN generation.
2. WHEN the user triggers the GST Filing flow THEN the system SHALL execute at least 6 steps including fetching sales data, computing tax liability, reconciling GSTR-2B, generating GSTR-3B, human approval checkpoint, and submission confirmation with a simulated ARN.
3. WHEN the user triggers the Shops & Establishment License flow THEN the system SHALL execute at least 5 steps including detecting the user's state (ask if unknown), fetching state-specific form, pre-filling from a mock user profile, human approval, and license number issuance.
4. WHEN any flow is running THEN each step SHALL take between 3 and 15 seconds to complete so the demo feels realistic, not instant.
5. WHEN a flow is running THEN the LLM SHALL generate contextual natural-language narration for each step transition that appears in the chat log in real time.
6. IF the user asks a clarifying question mid-flow (e.g. "What is DIN?") THEN the system SHALL answer via the LLM without interrupting or resetting the workflow.

### Requirement 4: Compliance Health Snapshot

**User Story:** As a founder, I want to see a one-glance compliance health score for my business, so that I know where I stand and what to fix next — and so I am willing to pay for a detailed scan.

#### Acceptance Criteria

1. WHEN the user completes onboarding or enters basic business details (name, type, state, founding date) THEN the system SHALL display a Compliance Health card with an overall score out of 100.
2. WHEN the health card is displayed THEN the system SHALL show at least four sub-indicators: Incorporation, GST, Labor, and Annual Filings, each with a colored status (green, amber, red) and a one-line explanation.
3. WHEN the user clicks any sub-indicator THEN the system SHALL expand a drill-down showing the specific items driving that status and a CTA to "Start this flow".
4. IF the user has not entered business details THEN the system SHALL display a soft prompt card inviting them to run a 2-minute scan, with clear privacy copy stating no data is submitted to any government portal in the MVP.

### Requirement 5: Backend Streaming and State API

**User Story:** As the engineering team, I want a clean backend contract for LLM streaming and workflow state, so that we can swap the simulator for the real LangGraph agent core in Week 2 without touching the frontend.

#### Acceptance Criteria

1. WHEN the frontend sends a chat message THEN the backend SHALL expose a POST /api/chat endpoint that returns a streaming response (SSE or chunked) with typed events: `token`, `intent_detected`, `workflow_started`, `step_update`, `awaiting_human`, `workflow_completed`, `error`.
2. WHEN a workflow is running THEN the backend SHALL maintain workflow state (steps, current index, status, metadata) in a server-side store keyed by session ID, NOT solely in the frontend.
3. WHEN the frontend reconnects after a dropped connection THEN the backend SHALL expose GET /api/workflows/:id that returns the current full state so the UI can re-hydrate.
4. WHEN the user approves a blocked step THEN the frontend SHALL call POST /api/workflows/:id/resume and the backend SHALL continue the stream on the original connection or a new SSE channel.
5. WHEN any backend error occurs THEN the system SHALL emit a structured `error` event with a user-friendly message and a correlation ID, and SHALL NOT crash the workflow state.
6. WHEN an LLM API call fails or times out after 15 seconds THEN the backend SHALL retry up to 2 times with exponential backoff before surfacing the error to the user.

### Requirement 6: Visual Design and Brand

**User Story:** As a founder evaluating a new tool, I want DigiNav to look trustworthy and premium on first glance, so that I believe it can handle something as serious as government compliance.

#### Acceptance Criteria

1. WHEN the user loads any page THEN the system SHALL render using Tailwind CSS and shadcn/ui components with a consistent design system (primary color, typography scale, spacing tokens).
2. WHEN the user views the app on desktop (>= 1024px), tablet (768–1023px), or mobile (< 768px) THEN the layout SHALL adapt responsively with no horizontal scroll and no clipped content.
3. WHEN the user interacts with any button, card, or input THEN the system SHALL provide visible focus states, hover feedback, and transitions under 200ms.
4. WHEN the user loads the app on a slow 3G connection THEN the largest contentful paint SHALL occur within 3 seconds and the app SHALL show a skeleton state, not a blank screen.
5. WHEN a screen reader is used THEN all interactive elements SHALL have accessible labels, the chat log SHALL use an aria-live region, and color SHALL not be the sole indicator of step state.

### Requirement 7: Session Persistence and Demo Resilience

**User Story:** As a founder showing this to my team or as a salesperson running a pilot demo, I want the app to survive a refresh, a lost internet connection, and a cold start, so that the demo never embarrasses me.

#### Acceptance Criteria

1. WHEN the user refreshes the browser mid-workflow THEN the system SHALL restore the chat history, the workflow progress, and the current step within 2 seconds.
2. WHEN the network connection drops THEN the system SHALL display a non-blocking banner "Reconnecting..." and SHALL automatically reconnect with exponential backoff up to 30 seconds.
3. WHEN the user opens the app with no prior session THEN the system SHALL display the welcome state with the three suggested prompts and a "Try a sample flow" affordance that runs a pre-recorded Incorporation flow in under 60 seconds for quick demos.
4. IF the LLM provider (Groq) is down THEN the system SHALL fall back to a pre-scripted response set for the three demo flows so the pilot demo still works.

### Requirement 8: Observability and Demo Analytics

**User Story:** As the founder of DigiNav, I want to see which prompts users send and which flows they start, so that I can learn what to prioritize next and report usage to pilot customers.

#### Acceptance Criteria

1. WHEN any user submits a chat message or triggers a workflow THEN the system SHALL log an event (timestamp, session ID, event type, intent, anonymized prompt hash) to a PostgreSQL `events` table.
2. WHEN a workflow completes or fails THEN the system SHALL log duration, step count, and terminal status.
3. WHEN the founder visits /admin (protected by a single shared secret in the MVP) THEN the system SHALL display total sessions, workflows started, workflows completed, and a table of the last 50 events.
4. WHEN any event is logged THEN the system SHALL NOT store raw PII (names, PAN, Aadhaar) in the events table — only the fact that a flow occurred.
