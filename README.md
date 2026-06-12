# RevenueOS

> ?? **Demonstration system. Runs entirely on synthetic data with mock external integrations.** No real patient health information (PHI) is used anywhere. External payer/clearinghouse systems are simulated. Designed to be SaaS-upgradeable ? see the Future SaaS Path section.

An agentic Medical Billing / Revenue Cycle Management (RCM) platform. Five specialised AI agents ? Eligibility, Coding, Scrubbing, Adjudication, and Denial Management ? coordinated by a Supervisor, moving each claim through its full lifecycle. Multi-tenant by design.

## Problem

Medical billing is a high-volume, error-prone, multi-stage workflow. Claims get denied for missing modifiers, eligibility lapses, and coding mismatches ? each denial costs time and revenue. RevenueOS automates the full revenue cycle with stage-specialised AI agents and a human-in-the-loop review queue.

## Architecture

_Architecture diagram added in Phase 1._

A claim flows: `DRAFT ? ELIGIBILITY_CHECKED ? CODED ? SCRUBBED ? SUBMITTED ? ADJUDICATED ? {PAID | DENIED}`, with denied claims routing into an appeal loop, all orchestrated by a LangGraph supervisor.

## Tech Stack

- **Orchestration:** LangGraph + LangChain
- **LLM:** Groq (Llama 3.3)
- **Backend:** FastAPI
- **Database:** PostgreSQL (multi-tenant, shared schema with tenant_id isolation)
- **Frontend:** React + Vite + Tailwind + shadcn/ui
- **Infra:** Docker Compose
- **Deploy:** Neon (DB) ? Railway (backend) ? Vercel (frontend)

## Setup

```powershell
# Clone
git clone https://github.com/hamzawithpython/revenueos.git
cd revenueos

# Copy env template and fill in your keys
Copy-Item .env.example .env

# Boot Postgres
docker compose up -d
```

_Full setup instructions expand as phases land._

## Live Demo

_Link added in Phase 9._

## Technical Decisions

- **LangGraph over CrewAI:** RCM is a deterministic pipeline with conditional branches and durable state needs ? LangGraph's StateGraph + checkpointer fits; autonomous collaboration does not.
- **Shared-schema multi-tenancy with tenant_id:** correct and cheap for early SaaS; row-level isolation enforced in the data-access layer.
- **Real HTTP mock services:** mirror EDI request/response shapes so production integration is a connector swap, not a rewrite.

## What Didn't Work / Lessons

_Populated as the build surfaces real issues._

## Future SaaS Path

What changes to "go real": HIPAA hosting under BAA, real clearinghouse integration (Availity/Change Healthcare), JWT/OAuth2 auth replacing the demo role-switcher, Postgres Row-Level Security, field-level PHI encryption, Stripe billing, SOC 2 path.

## Mock External Services

RevenueOS talks to three mock services that mirror real EDI transactions, so swapping in a production clearinghouse (Availity, Change Healthcare) is a config change rather than a rewrite:

- **mock-eligibility** (270/271) ? returns coverage status, copay, and deductible. ~12% of members return inactive to exercise the eligibility-failure path.
- **mock-clearinghouse** (837 -> 999/277CA) ? applies front-end edits, rejecting structurally invalid claims (missing NPI, malformed codes) before they reach the payer.
- **mock-payer** (835/ERA) ? adjudicates claims: pays clean ones with a contractual adjustment (CO-45) and patient responsibility carved out; denies flawed ones with the CARC/RARC matching the actual defect.

All run as containerized FastAPI services on a shared Docker network, reachable by service name. Denial logic is driven by the same pattern files as the synthetic generator, keeping the system internally consistent.

## Phase 3 ? Agents & Supervisor (Technical Decisions & Lessons)

### Technical Decisions
- **Pydantic ClaimState as the LangGraph channel:** the graph threads a typed `ClaimState` model through every node (node signature `ClaimState -> ClaimState`), so agents work with validated attributes instead of dict subscripting.
- **Eligibility is deterministic, coding is LLM-driven:** eligibility is a data lookup (no reasoning needed), so that agent just calls the mock and persists. Coding genuinely requires judgment about whether documented care matches the codes, so it uses Groq ? constrained to the known code catalogue so it cannot hallucinate codes outside the set.
- **Agents persist as they go:** each agent writes its result (271, finalized codes) plus an audit event in its own DB session, so the claim's history is reconstructable independent of graph state.

### What Didn't Work / Lessons
- **LangGraph node names cannot collide with state-field names.** Naming a node `eligibility` while `ClaimState` has an `eligibility` field raises `'eligibility' is already being used as a state key`. Fix: suffix node names (`eligibility_check`, `coding_assign`).
- **Service-name URLs vs localhost.** The mock URLs in `.env` pointed at Docker service names (`http://mock-eligibility:8001`), which only resolve inside the compose network. Running agents locally needs `localhost` URLs. A swallowed `ConnectError` made every eligibility check silently return inactive ? one root cause producing four visible symptoms (no eligibility data, no audit rows, active=False, needs_review=True). Lesson: a bare `except` that returns a degraded result can mask a connectivity bug as a business outcome.
- **Backslashes are not allowed inside f-string expression braces (Python <3.12).** Build display strings before the f-string rather than escaping quotes inside `{}`.

## Phase 4 ? Scrubber & Adjudication (Technical Decisions)

### Technical Decisions
- **Scrubbing is rule-based, not LLM.** Clean-claim edits (missing modifiers, dx/cpt mismatches) are deterministic rules mirroring real CCI/LCD edits ? an LLM would add latency and nondeterminism to a check that is fundamentally a lookup. The coding agent (judgment) uses the LLM; the scrubber (rules) does not.
- **Scrubber and payer read the same pattern files.** This makes the system internally consistent: a defect the scrubber flags is the same defect the payer denies, with matching CARC codes (missing modifier -> CO-16, dx/cpt mismatch -> CO-11). The scrubber is the practice's pre-submission catch; the payer is the external check ? modeling both shows the real value of scrubbing (catching denials before they happen).
- **Flawed claims still proceed to adjudication.** Rather than blocking flawed claims, the pipeline submits them so the denial path is exercised end to end. In production the scrubber would gate submission; here it flags for review but continues, which is what makes the denial-management phase demonstrable.
- **Two-hop adjudication mirrors production.** Clearinghouse front-end edits first, then payer adjudication ? the same boundary a real integration crosses, so swapping mocks for Availity/Change Healthcare is a client change, not a logic change.

## Phase 5 ? Denial Management & the Appeal Loop (Technical Decisions)

### Technical Decisions
- **CARC code drives strategy, not the LLM.** The recovery decision (correct-and-resubmit vs. appeal vs. write-off) is a deterministic mapping from the denial code, because it is a business rule, not a judgment call. The LLM is used only where it adds value: drafting appeal-letter prose grounded in the specific denial reason.
- **Corrections are real mutations, re-read on resubmission.** A CO-16 correction adds the missing modifier to the claim's codes; a CO-11 correction realigns the diagnosis. The resubmission rebuilds the claim from the corrected state, so the payer genuinely re-adjudicates the fixed claim and flips it to PAID ? the loop recovers revenue rather than just re-sending the same denial.
- **Conditional routing with a bounded loop.** This is the first use of LangGraph conditional edges: adjudicate branches PAID->END / DENIED->denial; denial branches correct->adjudicate (the loop) / appeal->END. A max-attempts guard (2) prevents infinite cycling if a correction does not resolve the defect.
- **Denied-then-paid history is preserved.** A recovered claim keeps both its Denial row and its Remittance row ? an accurate audit trail of a claim that was denied, corrected, and paid on resubmission.

### Lesson
- **The node-name / state-key collision recurred.** Adding a `denial_mgmt` state field and naming the node `denial_mgmt` re-triggered the LangGraph reserved-key error from Phase 3. Confirmed pattern: node names must be distinct from every ClaimState field name. Node renamed to `denial_handle`.

## Phase 6 - REST API (Technical Decisions)

### Technical Decisions
- **DTOs separate from ORM models.** API responses use dedicated Pydantic schemas, so the public contract is stable and explicit even if the database schema evolves.
- **Tenant scoping at the API boundary.** Every request carries an X-Tenant-Id header (standing in for auth, which arrives in the SaaS upgrade). Cross-tenant access returns 404, not a leak; a missing header returns 400. The isolation enforced in the data layer is re-verified at the HTTP edge.
- **Processing service shared by API and CLI.** The load-state -> run-graph -> persist logic lives in one service module, so the REST endpoint and the CLI runner drive claims through the exact same path.
- **Service-name networking inside compose.** The API container reaches Postgres and the mocks by service name via environment overrides, while local development uses localhost. Same code, environment-driven URLs - the pattern that makes the production integration swap a config change.

## Phase 7 - React Dashboard (Technical Decisions)

### Technical Decisions
- **React + Vite + Tailwind over Streamlit.** A system meant to convince a billing professional needs a real operations dashboard - a kanban pipeline, drill-down claim detail, worklists. Streamlit (used elsewhere for an ML demo) cannot deliver that interaction model; the extra build cost buys the "I want this" reaction.
- **Tenant + role switcher instead of auth.** The switcher sets the X-Tenant-Id the API already enforces, demonstrating the multi-tenant model and role hierarchy without building auth plumbing that adds no portfolio signal. Real JWT/OAuth2 is the documented SaaS upgrade.
- **Dev-server proxy to the API.** Vite proxies /api to the FastAPI backend, avoiding CORS friction in development and mirroring the deployed topology.
- **Monospaced numerics.** Codes, money, and IDs render in a tabular monospace face so data reads as data - a small clinical-operations detail that makes the interface feel built for billers.
- **The pipeline is the signature screen.** Claims as cards moving left-to-right across lifecycle columns, with a one-click "run pipeline" that drives a draft through the full agent flow and watches it land in PAID / DENIED / recovered - the system working, live.

## Phase 8 - Evaluation Suite (Technical Decisions & Results)

### Results (on synthetic test data, n=40)
| Metric | Score |
|---|---|
| Coding accuracy | 90% |
| Clean-claim rate | 100% |
| Scrub detection | 100% |
| Denial-handling accuracy | 100% |
| Defect resolution (end-to-end) | 100% |

### Technical Decisions & Lessons
- **Not RAGAS.** RevenueOS is not a retrieval-augmented system; its core task is claim-processing accuracy against gold labels, not retrieval quality. The eval scores decisions (coding, scrubbing, denial strategy) against a labeled synthetic test set - the measurement that fits the task.
- **Eval-driven improvement, measured.** The first run showed 75% coding accuracy. Debug output revealed every miss was a dx/cpt-mismatch claim where the LLM echoed the bad draft diagnosis instead of correcting it. Tightening the coding prompt to actively replace a diagnosis inconsistent with the procedure raised coding accuracy to 90%. The remaining misses are claims whose notes are too thin to infer the correct diagnosis - a genuine, documented limitation rather than a hidden one.
- **Per-agent isolation prevents metric artifacts.** Fixing the coder caused scrub detection to appear to drop to 70% - because claims the coder corrected upstream were clean by the time the scrubber saw them, and were wrongly counted as scrub misses. The fix: measure the scrubber in isolation on the as-generated claim, and add an end-to-end "defect resolution" metric that credits a defect resolved by either agent. Lesson: in a sequential agent pipeline, a downstream agent's metric must isolate that agent's input, or an upstream improvement distorts it.
- **Compute/persist separation.** The coding and scrubbing logic was refactored to separate pure decision functions (used by the eval) from persistence (used by the live pipeline), so evals run fast, reproducibly, and never write to the database.
