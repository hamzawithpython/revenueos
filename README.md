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
