"""Build docs/Atlas-AI-Technical-Design.pdf.

    pip install -r docs/design/requirements.txt
    python docs/design/build_design_doc.py

Content mirrors the implementation in backend/ and frontend/. When the design changes,
update the relevant section here and rebuild.
"""

from __future__ import annotations

import sys
from pathlib import Path

from reportlab.platypus import NextPageTemplate, PageBreak, Spacer

sys.path.insert(0, str(Path(__file__).parent))

from pdfkit import (  # noqa: E402
    FONT_MONO,
    H1,
    Arrow,
    Box,
    DesignDoc,
    Diagram,
    Group,
    Sequence,
    bullets,
    callout,
    code,
    figure,
    heading,
    numbered,
    p,
    table,
    toc,
)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "Atlas-AI-Technical-Design.pdf"

META = {
    "Version": "1.0",
    "Status": "Implemented (v0.1.0)",
    "Date": "13 October 2026",
    "Author": "Suriya K",
    "Repository": "atlas-ai (backend/, frontend/)",
}


def c(text: str) -> str:
    """Inline code."""
    safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<font name="{FONT_MONO}" size="8.3" color="#1d4ed8">{safe}</font>'


def b(text: str) -> str:
    return f"<b>{text}</b>"


# =========================================================================================
# Diagrams
# =========================================================================================


def system_context() -> Diagram:
    boxes = [
        Box("browser", 3, 40, 24, 14, "Browser", "grey", "operator"),
        Box("next", 35, 30, 34, 34, "Next.js console", "violet",
            "Server Components\nServer Actions\nBFF route\n(API key server-side)"),
        Box("api", 80, 6, 40, 15, "FastAPI", "blue", "auth, validation,\nrate limits"),
        Box("svc", 80, 29, 40, 15, "Incident service", "blue", "lifecycle + worker pool"),
        Box("graph", 80, 52, 40, 15, "LangGraph workflow", "dark", "agents, tools, gates"),
        Box("tools", 80, 76, 40, 15, "Integrations (mock)", "grey", "logs, git, deploys,\ntickets, runbooks"),
        Box("db", 132, 5, 35, 15, "Application DB", "green", "incidents, events,\napprovals, audit", "db"),
        Box("ckpt", 132, 28, 35, 15, "Checkpoint store", "green", "per-node checkpoints", "db"),
        Box("redis", 132, 50, 35, 13, "Redis", "green", "rate-limit counters", "db"),
        Box("llm", 132, 68, 35, 11, "LLM provider", "amber", "optional, via gateway"),
        Box("ls", 132, 84, 35, 10, "LangSmith", "amber", "optional tracing"),
    ]
    arrows = [
        Arrow("browser", "next", "HTTPS"),
        Arrow("next", "api", "REST + X-API-Key", via=[(52, 13.5)], src_side="n", dst_side="w"),
        Arrow("api", "svc", "commands"),
        Arrow("svc", "graph", "invoke / resume"),
        Arrow("graph", "tools", "tool registry"),
        Arrow("api", "db"),
        Arrow("graph", "ckpt", start=(120, 55.5), via=[(127, 55.5), (127, 35.5)], dst_side="w"),
        Arrow("api", "redis", start=(120, 18), via=[(124, 18), (124, 56.5)], dst_side="w",
              dashed=True),
        Arrow("graph", "llm", start=(120, 63), via=[(128, 63), (128, 73.5)], dst_side="w",
              dashed=True),
        Arrow("graph", "ls", start=(113, 67), via=[(113, 71), (125, 71), (125, 89)],
              dst_side="w", dashed=True),
    ]
    return Diagram(170, 96, boxes, arrows)


def workflow_graph() -> Diagram:
    boxes = [
        Box("start", 61, 1, 22, 8, "START", "dark", shape="round"),
        Box("triage", 52, 14, 40, 11, "Triage", "blue", "classify + resolve IDs"),
        Box("plan", 52, 31, 40, 11, "Planner", "blue", "bounded steps per round"),
        Box("logs", 2, 50, 42, 13, "Log analysis", "violet", "error rates, signatures"),
        Box("code", 52, 50, 40, 13, "Code & commits", "violet", "deploys, diffs, risk"),
        Box("kb", 100, 50, 42, 13, "Knowledge retrieval", "violet", "BM25 runbooks"),
        Box("agg", 52, 71, 40, 10, "Evidence aggregation", "blue"),
        Box("review", 52, 87, 40, 11, "Root cause review", "blue", "score hypotheses"),
        Box("dec", 54, 104, 36, 17, "Sufficient, or\nbudget spent?", "amber", shape="diamond"),
        Box("report", 52, 128, 40, 11, "Report", "blue", "facts, hypotheses, actions"),
        Box("gate", 54, 146, 36, 16, "Approval\nrequired?", "amber", shape="diamond"),
        Box("human", 112, 147, 46, 14, "Human approval", "red", "interrupt(), resumed by API"),
        Box("exec", 52, 170, 40, 11, "Execute actions", "green", "idempotent, allowlisted"),
        Box("end", 61, 188, 22, 8, "END", "dark", shape="round"),
    ]
    arrows = [
        Arrow("start", "triage"),
        Arrow("triage", "plan"),
        Arrow("plan", "logs", "Send", start=(66, 42), via=[(66, 46), (23, 46)], dst_side="n"),
        Arrow("plan", "code", "Send"),
        Arrow("plan", "kb", "Send", start=(78, 42), via=[(78, 46), (121, 46)], dst_side="n"),
        Arrow("logs", "agg", via=[(23, 76)], src_side="s", dst_side="w"),
        Arrow("code", "agg"),
        Arrow("kb", "agg", via=[(121, 76)], src_side="s", dst_side="e"),
        Arrow("agg", "review"),
        Arrow("review", "dec"),
        Arrow("dec", "report", "yes"),
        Arrow("dec", "plan", "no: closable gaps", via=[(47, 112.5), (47, 36.5)], src_side="w",
              dst_side="w", label_at=0.12, label_dx=-12),
        Arrow("report", "gate", "policy gate"),
        Arrow("gate", "human", "yes"),
        Arrow("gate", "exec", "no"),
        Arrow("human", "exec", "approved / rejected", via=[(135, 175.5)], src_side="s",
              dst_side="e"),
        Arrow("exec", "end"),
    ]
    texts = [(150, 30, "checkpoint after every node", 6),
             (150, 34, "(SQLite or Postgres saver)", 6)]
    return Diagram(170, 198, boxes, arrows, texts=texts)


def request_sequence() -> Sequence:
    parts = ["Browser", "Next.js", "FastAPI", "Worker", "Stores"]
    msgs = [
        (0, 1, "submit form (Server Action)", False),
        (1, 2, "POST /api/v1/incidents", False),
        (2, 4, "incident (queued) + audit", False),
        (2, 1, "202 Accepted", True),
        (2, 3, "dispatch to pool", False),
        (3, 4, "checkpoint + events per node", False),
        (0, 1, "poll /api/incidents/{id}", False),
        (1, 2, "GET incident, events, report", False),
        (3, 4, "interrupt: approval request", False),
        (0, 1, "Approve (Server Action)", False),
        (1, 2, "POST .../approvals", False),
        (2, 4, "conditional decide + audit", False),
        (2, 3, "resume Command(decision)", False),
        (3, 3, "idempotent actions", False),
        (3, 4, "final report, completed", False),
    ]
    return Sequence(parts, msgs, width_mm=170, step_mm=6.0)


def state_machine() -> Diagram:
    boxes = [
        Box("queued", 4, 30, 26, 11, "queued", "grey"),
        Box("running", 48, 30, 30, 11, "running", "blue"),
        Box("awaiting", 48, 3, 30, 12, "awaiting_\napproval", "amber"),
        Box("completed", 130, 30, 36, 11, "completed", "green"),
        Box("failed", 130, 44, 36, 11, "failed", "red"),
        Box("cancelled", 48, 58, 30, 11, "cancelled", "grey"),
    ]
    arrows = [
        Arrow("queued", "running", "dispatch", label_at=0.35),
        Arrow("running", "awaiting", "interrupt", start=(57, 30), end=(57, 15), label_dx=-8),
        Arrow("awaiting", "running", "decision", start=(69, 15), end=(69, 30), label_dx=8),
        Arrow("running", "completed", "graph reached END"),
        Arrow("running", "failed", "error / budget", start=(74, 41), via=[(74, 49.5)],
              dst_side="w"),
        Arrow("running", "cancelled", "cancel flag"),
        Arrow("queued", "cancelled", "cancel", via=[(17, 63.5)], src_side="s", dst_side="w"),
        Arrow("awaiting", "cancelled", "cancel", via=[(38, 9), (38, 52), (54, 52)],
              src_side="w", end=(54, 58), label_at=0.85),
    ]
    return Diagram(170, 72, boxes, arrows)


def tool_pipeline() -> Diagram:
    names = [("allow", "Allowlist\ncheck"), ("validate", "Schema\nvalidation"),
             ("budget", "Consume\nbudget"), ("run", "Run with\ntimeout"),
             ("classify", "Classify\noutcome"), ("emit", "Emit\nevent"), ("ret", "Return\nresult")]
    boxes = [Box(key, 2 + i * 24, 14, 21, 15, label, "blue" if key != "ret" else "green")
             for i, (key, label) in enumerate(names)]
    boxes += [
        Box("denied", 2, 40, 21, 11, "tool_denied", "red", "not permitted"),
        Box("invalid", 26, 40, 21, 11, "invalid args", "red", "ToolValidationError"),
        Box("exhausted", 50, 40, 21, 11, "budget spent", "red", "ToolBudgetExceeded"),
        Box("perm", 98, 40, 21, 11, "permanent", "red", "raise, no retry"),
        Box("gaveup", 122, 40, 21, 11, "retries spent", "red", "raise transient"),
    ]
    arrows = [Arrow(names[i][0], names[i + 1][0]) for i in range(len(names) - 1)]
    arrows += [
        Arrow("allow", "denied"), Arrow("validate", "invalid"), Arrow("budget", "exhausted"),
        Arrow("classify", "perm"),
        Arrow("classify", "gaveup", start=(114, 29), via=[(114, 34), (132.5, 34)],
              dst_side="n"),
        Arrow("classify", "budget", "transient: backoff, then retry",
              via=[(108.5, 5), (60.5, 5)], src_side="n", dst_side="n"),
    ]
    return Diagram(170, 54, boxes, arrows)


def data_model() -> Diagram:
    boxes = [
        Box("inc", 61, 3, 48, 76, "incidents", "blue",
            "id (PK)\ndescription\nservice_name\ndeployment_id\nseverity\nstatus (indexed)\n"
            "created_by\ncreated_at / updated_at\ncompleted_at\ncancel_requested\ncurrent_node\n"
            "triage (JSON)\nreport (JSON)\nmetrics (JSON)\nerror"),
        Box("ev", 2, 3, 46, 34, "workflow_events", "violet",
            "seq (PK, autoincrement)\nincident_id (FK, idx)\ntype\nnode\npayload (JSON, redacted)\n"
            "created_at"),
        Box("apr", 122, 3, 46, 36, "approval_requests", "amber",
            "id (PK)\nincident_id (FK, idx)\nstatus\nactions (JSON)\nrequested_at\n"
            "decided_by / decided_at\ncomment"),
        Box("aud", 2, 45, 46, 34, "audit_records", "grey",
            "id (PK)\nincident_id (idx)\nactor\naction\ndetails (JSON, redacted)\ncreated_at"),
        Box("ck", 122, 47, 46, 32, "LangGraph checkpoints", "green",
            "separate store\nthread_id = incident id\nfull IncidentState per step\n"
            "pending writes, interrupts"),
    ]
    arrows = [
        Arrow("ev", "inc", "N : 1"),
        Arrow("apr", "inc", "N : 1"),
        Arrow("aud", "inc", "N : 1 (soft)", dashed=True),
        Arrow("ck", "inc", "1 : 1 by thread_id", dashed=True),
    ]
    return Diagram(170, 82, boxes, arrows)


def frontend_flow() -> Diagram:
    groups = [Group(1, 1, 48, 64, "Browser", "grey"), Group(56, 1, 54, 64, "Next.js server", "violet"),
              Group(146, 1, 23, 64, "Backend", "blue")]
    boxes = [
        Box("pages", 5, 9, 40, 13, "Server-rendered pages", "default", "streamed in Suspense"),
        Box("live", 5, 29, 40, 13, "Live incident view", "default", "polls 1.2 s / 5 s"),
        Box("forms", 5, 49, 40, 13, "Forms and buttons", "default", "new, approve, cancel"),
        Box("rsc", 60, 9, 46, 13, "Server Components", "violet", "dashboard, lists, detail"),
        Box("bff", 60, 29, 46, 13, "BFF route handler", "violet", "/api/incidents/[id]"),
        Box("act", 60, 49, 46, 13, "Server Actions", "violet", "validate, relay, refresh"),
        Box("lib", 116, 27, 25, 17, "lib/atlas.ts", "dark", "server-only\nX-API-Key"),
        Box("api", 149, 27, 18, 17, "FastAPI", "blue", "/api/v1"),
    ]
    arrows = [
        Arrow("pages", "rsc", "HTML/RSC", dashed=True),
        Arrow("live", "bff", "fetch JSON"),
        Arrow("forms", "act", "POST action"),
        Arrow("rsc", "lib", via=[(111, 15.5), (111, 31)], src_side="e", dst_side="w"),
        Arrow("bff", "lib"),
        Arrow("act", "lib", via=[(111, 55.5), (111, 40)], src_side="e", dst_side="w"),
        Arrow("lib", "api"),
    ]
    return Diagram(170, 67, boxes, arrows, groups)


def deployment_view() -> Diagram:
    groups = [Group(30, 1, 139, 52, "docker compose", "blue")]
    boxes = [
        Box("user", 2, 18, 22, 12, "Operator", "grey", "browser"),
        Box("fe", 36, 18, 30, 13, "frontend", "violet", "node:24, :3000"),
        Box("be", 76, 18, 32, 13, "backend", "dark", "python:3.12, :8000"),
        Box("pg", 120, 8, 30, 13, "postgres", "green", "16-alpine, :5432", "db"),
        Box("rd", 120, 31, 30, 13, "redis", "green", "7-alpine, :6379", "db"),
        Box("ext", 76, 58, 60, 10, "LLM provider / LangSmith (optional, outbound HTTPS)", "amber"),
    ]
    arrows = [
        Arrow("user", "fe"), Arrow("fe", "be", "ATLAS_API_URL"),
        Arrow("be", "pg", "data + checkpoints", via=[(114, 22), (114, 14.5)], src_side="e",
              dst_side="w"),
        Arrow("be", "rd", "rate limits", via=[(114, 27), (114, 37.5)], src_side="e",
              dst_side="w"),
        Arrow("be", "ext", dashed=True),
    ]
    return Diagram(170, 70, boxes, arrows, groups)


def ci_pipeline() -> Diagram:
    groups = [Group(1, 1, 168, 23, "backend job (ubuntu, Python 3.12)", "blue"),
              Group(1, 28, 168, 23, "frontend job (ubuntu, Node 24)", "violet")]
    be = [("b1", "pip install\n-e .[dev]"), ("b2", "ruff check"), ("b3", "ruff format\n--check"),
          ("b4", "pytest\n42 tests + eval gate"), ("b5", "evaluation run"), ("b6", "upload\nartifact")]
    fe = [("f1", "npm ci"), ("f2", "next typegen"), ("f3", "tsc --noEmit"), ("f4", "eslint"),
          ("f5", "next build")]
    boxes = [Box(k, 4 + i * 27.5, 8, 24, 13, label, "blue") for i, (k, label) in enumerate(be)]
    boxes += [Box(k, 4 + i * 33, 35, 28, 13, label, "violet") for i, (k, label) in enumerate(fe)]
    arrows = [Arrow(be[i][0], be[i + 1][0]) for i in range(len(be) - 1)]
    arrows += [Arrow(fe[i][0], fe[i + 1][0]) for i in range(len(fe) - 1)]
    return Diagram(170, 53, boxes, arrows, groups)


# =========================================================================================
# Content
# =========================================================================================


def front_matter() -> list:
    s = [NextPageTemplate("body"), PageBreak()]
    s.append(heading("Document control", 0))
    s.append(table([
        ["Field", "Value"],
        ["Document", "Atlas AI - Technical Design Document"],
        ["Version", META["Version"]],
        ["Status", "Describes the implemented system, backend 0.1.0 and frontend 0.1.0"],
        ["Date", META["Date"]],
        ["Owner", META["Author"]],
        ["Source of truth", "The code. Where this document and the code disagree, the code wins "
                            "and this document should be corrected."],
        ["Regenerate", f"{c('python docs/design/build_design_doc.py')}"],
    ], [0.22, 0.78]))
    s.append(heading("Revision history", 1))
    s.append(table([
        ["Version", "Date", "Change"],
        ["1.0", META["Date"], "First complete design: architecture, workflow, agents, tools, data, "
                              "API, security, reliability, observability, frontend, evaluation, "
                              "operations."],
    ], [0.12, 0.2, 0.68]))
    s.append(heading("How to read this document", 1))
    s.append(p(
        "Sections 1 to 4 explain what Atlas AI is for and how it is put together. Sections 5 to 9 "
        "describe the investigation engine in depth: the LangGraph workflow, each agent's "
        "algorithm, the evidence model, the tool layer, and the model gateway. Sections 10 to 15 "
        "cover persistence, the API, security, reliability, observability, and the frontend. "
        "Sections 16 to 19 cover evaluation, testing, operations, and known limitations. The "
        "appendices hold reference tables."))
    s.append(callout(
        "Conventions",
        f"Code identifiers appear as {c('monospace')}. Paths are relative to the repository root. "
        "Numbers such as thresholds, weights, and budgets are the defaults in the code at the time "
        "of writing; most are configurable (Appendix A). Statements about planned work are labelled "
        "<i>planned</i>.", "note"))
    s.append(PageBreak())
    s.append(p("Contents", H1))
    s.append(toc())
    s.append(PageBreak())
    return s


def sec_introduction() -> list:
    s = [heading("1. Introduction", 0)]
    s.append(heading("1.1 Purpose", 1))
    s.append(p(
        "Atlas AI is a multi-agent platform that investigates production incidents. An operator "
        "describes what they are seeing; the platform classifies the incident, gathers evidence "
        "from logs, source control, deployment records, and internal knowledge, weighs competing "
        "explanations, and produces a report in which every claim cites evidence. Actions with "
        "external effects, such as opening a ticket or rolling back a deployment, are proposed by "
        "the platform but executed only after a person approves them."))
    s.append(p(
        "This document specifies how the system is designed and why. It is intended to let an "
        "engineer understand, operate, review, or extend the system without reading every source "
        "file first, and to make the safety-relevant decisions explicit enough to audit."))
    s.append(heading("1.2 Scope", 1))
    s.append(table([
        ["In scope", "Out of scope (this version)"],
        ["Backend service: API, workflow, agents, tools, persistence, security, observability, "
         "evaluation.",
         "Real integrations with log stores, GitHub, deploy systems, and ticketing. The tool "
         "contracts are designed for them; the implementations are mocks."],
        ["Frontend console: dashboard, investigations, approvals, live investigation view.",
         "Multi-tenant isolation, SSO, and per-user identity (API keys map to principals)."],
        ["Local and containerised deployment, CI.",
         "Horizontal scaling of workers across replicas (Section 18.4)."],
    ], [0.5, 0.5]))
    s.append(heading("1.3 Audience", 1))
    s += bullets([
        f"{b('Engineers')} extending agents, tools, or the console.",
        f"{b('Reviewers')} assessing safety controls, failure handling, and evaluation.",
        f"{b('Operators')} deploying and configuring the service.",
    ])
    s.append(heading("1.4 Glossary", 1))
    s.append(table([
        ["Term", "Meaning"],
        ["Incident", "An operator-submitted investigation request and everything produced for it."],
        ["Investigation round", "One pass of plan, parallel evidence gathering, aggregation, and review. "
                                "At most two by default."],
        ["Evidence", "A typed, ID-bearing observation from one source (logs, code, deployment, "
                     "knowledge), e.g. L1.3."],
        ["Hypothesis", "A candidate root cause with supporting and contradicting evidence and a "
                       "confidence in [0, 1]."],
        ["Sufficient evidence", "A deterministic gate on the top hypothesis (Section 6.6.4)."],
        ["Gap", "A category of missing evidence named by the review (e.g. logs_wide); the planner "
                "turns closable gaps into steps."],
        ["Pivot time", "The deployment time if known, otherwise the reported incident time; "
                       "before/after comparisons split on it."],
        ["Policy gate", "Node that classifies proposed actions against the action policy table."],
        ["Checkpoint", "Persisted LangGraph state after a step; enables resume and approval pauses."],
        ["Offline mode", "Running with no model configured; every agent uses its deterministic "
                         "implementation."],
        ["BFF", "Backend-for-frontend: a Next.js route that proxies reads so the API key stays "
                "on the server."],
    ], [0.24, 0.76]))
    s.append(heading("1.5 References", 1))
    s += bullets([
        f"{c('README.md')}: setup and overview.",
        f"{c('docs/architecture.md')}, {c('docs/threat-model.md')}, "
        f"{c('docs/decisions/0001-deterministic-control-plane.md')}, "
        f"{c('docs/evaluation-report.md')}.",
        "LangGraph, LangChain, LangSmith, FastAPI, and Next.js 16 documentation.",
    ])
    return s


def sec_goals() -> list:
    s = [PageBreak(), heading("2. Problem, goals, and requirements", 0)]
    s.append(heading("2.1 Problem statement", 1))
    s.append(p(
        "During an incident, responders correlate signals across several systems under time "
        "pressure: an error spike in logs, the deployment that preceded it, the commits it "
        "contained, and the runbook or postmortem that describes a similar failure. The work is "
        "repetitive and evidence-driven, which makes it a good fit for automation, but the output "
        "feeds decisions with production impact. An assistant that is confidently wrong, that can "
        "be talked into acting by text in a log line, or that silently retries a rollback is worse "
        "than none."))
    s.append(heading("2.2 Goals", 1))
    s.append(table([
        ["ID", "Goal", "How the design meets it"],
        ["G1", "Produce evidence-backed root-cause reports.",
         "Typed evidence with stable IDs; every hypothesis and fact cites IDs; references are "
         "validated."],
        ["G2", "Never take a sensitive action without a human.",
         "Deterministic policy gate; graph interrupt; only one component may call side-effecting "
         "tools."],
        ["G3", "Be honest about uncertainty.",
         "Three report statuses; sufficiency gate; open questions listed; infrastructure "
         "hypotheses capped."],
        ["G4", "Survive failures and restarts.",
         "Checkpoint per step; resume on startup; retries with backoff; graceful degradation; "
         "idempotent actions."],
        ["G5", "Be observable and auditable.",
         "Per-incident event stream, audit records, run metrics, LangSmith tracing."],
        ["G6", "Run without a model.",
         "Every agent has a deterministic implementation; CI and evaluation run offline."],
        ["G7", "Be measurable.",
         "Evaluation dataset, seven evaluators, regression gate in CI."],
    ], [0.07, 0.33, 0.6]))
    s.append(heading("2.3 Non-goals", 1))
    s += bullets([
        "Replacing human judgement on remediation. The platform recommends and executes only "
        "approved actions.",
        "Free-form chat. The interaction model is: submit, observe, decide.",
        "Autonomous code changes. No agent writes code or configuration.",
    ])
    s.append(heading("2.4 Functional requirements", 1))
    s.append(table([
        ["ID", "Requirement"],
        ["FR1", "Accept an incident description with optional service, deployment, and severity hints."],
        ["FR2", "Classify the incident and resolve the service, deployment, and time window."],
        ["FR3", "Gather evidence from logs, code and deployments, and knowledge in parallel."],
        ["FR4", "Score competing hypotheses and decide whether evidence is sufficient."],
        ["FR5", "Request more evidence for closable gaps, within a round budget."],
        ["FR6", "Produce a report: summary, root cause, impact, facts, hypotheses, timeline, "
                "remediation, open questions, security notes, evidence."],
        ["FR7", "Propose actions; gate them by policy; pause for approval; execute idempotently."],
        ["FR8", "Expose status, events, report, approvals, and cancellation over a REST API."],
        ["FR9", "Provide a console to submit, monitor live, review reports, and decide approvals."],
    ], [0.08, 0.92]))
    s.append(heading("2.5 Non-functional requirements", 1))
    s.append(table([
        ["Quality", "Requirement", "Mechanism"],
        ["Safety", "No unapproved side effects; no model-driven authorization.",
         "Policy table, interrupt, allowlists"],
        ["Durability", "No lost work across process restarts.", "Checkpointer, startup recovery"],
        ["Boundedness", "Every run terminates within budgets.",
         "Rounds, tool-call budget, timeouts, wall clock"],
        ["Security", "Least privilege; secrets never persisted in clear text.",
         "Roles, allowlists, redaction"],
        ["Latency", "Offline investigation completes in well under a second on mock data.",
         "Measured p95 26 ms in evaluation"],
        ["Testability", "Deterministic runs in CI.", "Offline mode, inline executor, fault injection"],
        ["Accessibility", "Charts readable without colour; values reachable without hover.",
         "Validated palette, labels, sr-only tables"],
    ], [0.15, 0.5, 0.35]))
    return s


def sec_overview() -> list:
    s = [PageBreak(), heading("3. System overview", 0)]
    s.append(p(
        "Atlas AI is two deployables in one repository. The backend owns all state and all "
        "decisions. The frontend is a presentation layer that holds the API key on its server and "
        "never exposes it to the browser."))
    s.append(figure(system_context(), "Figure 1. System context. Dashed edges are optional or "
                                      "asynchronous."))
    s.append(heading("3.1 Components", 1))
    s.append(table([
        ["Component", "Responsibility", "Location"],
        ["FastAPI app", "HTTP surface, authentication, authorization, validation, rate limiting.",
         c("backend/app/api/")],
        ["Incident service", "Lifecycle state machine, background dispatch, approval and cancel "
                             "commands, startup recovery, metrics.", c("backend/app/services/incident_service.py")],
        ["LangGraph workflow", "Typed state, nodes, routing, interrupts, checkpointing.",
         c("backend/app/graph/")],
        ["Agents", "Triage, planner, log, code, knowledge, review, reporting, policy gate, executor.",
         c("backend/app/agents/")],
        ["Tool registry", "Allowlists, schemas, timeouts, retries, budgets, fault injection, events.",
         c("backend/app/tools/base.py")],
        ["Model gateway", "Provider selection, structured output, usage accounting, fallback.",
         c("backend/app/services/model_gateway.py")],
        ["Persistence", "SQLAlchemy models and repository; checkpointer factory.",
         c("backend/app/persistence/")],
        ["Security", "Roles, action policy, tool access, redaction, untrusted content, rate limits.",
         c("backend/app/security/")],
        ["Evaluation", "Evaluators and runner over a versioned dataset.", c("backend/app/evaluation/")],
        ["Console", "Next.js 16 App Router UI, server actions, BFF route.", c("frontend/src/")],
    ], [0.18, 0.5, 0.32]))
    s.append(heading("3.2 Technology stack", 1))
    s.append(table([
        ["Layer", "Technology", "Version in use", "Role"],
        ["Language", "Python", "3.12+ (developed on 3.14)", "Backend"],
        ["API", "FastAPI, Pydantic, pydantic-settings", "0.143 / 2.14 / 2.15", "HTTP, validation, config"],
        ["Orchestration", "LangGraph", "1.2", "Stateful graph, Send, interrupts"],
        ["Checkpoints", "langgraph-checkpoint-sqlite / -postgres", "3.1", "Durable execution"],
        ["LLM integration", "LangChain init_chat_model", "1.4", "Provider-agnostic structured output"],
        ["Tracing", "LangSmith", "0.14", "Run traces via environment variables"],
        ["Data", "SQLAlchemy, SQLite, PostgreSQL", "2.1 / - / 16", "Application data"],
        ["Cache", "Redis", "7", "Shared rate limiting (optional)"],
        ["Frontend", "Next.js, React, Tailwind CSS", "16.4 / 19.3 / 4", "Console"],
        ["Quality", "pytest, ruff, ESLint, TypeScript", "9 / 0.17 / 9 / 5", "Tests, lint, types"],
        ["Delivery", "Docker, Docker Compose, GitHub Actions", "-", "Packaging, CI"],
    ], [0.15, 0.33, 0.22, 0.3]))
    s.append(heading("3.3 Repository layout", 1))
    s += code("""
atlas-ai/
  backend/
    app/
      api/            routes/, schemas.py, dependencies.py
      agents/         triage, planner, log_analysis, code_analysis, knowledge_retrieval,
                      root_cause_review, reporting, actions, schemas, common
      graph/          state.py, context.py, nodes.py, edges.py, workflow.py, checkpoint.py
      tools/          base.py (registry), logs, github, retrieval, ticketing, mock_data
      services/       incident_service.py, model_gateway.py
      persistence/    models.py, database.py, repository.py
      security/       policy, tool_access, redaction, untrusted, rate_limit
      observability/  tracing.py
      evaluation/     evaluators.py, run.py
      config.py, main.py
    data/             services, deployments, commits, logs (generated), knowledge/*.md
    datasets/incidents/eval_cases.json
    scripts/generate_mock_logs.py
    tests/            unit/, integration/, failure_scenarios/, evaluation/
  frontend/src/
    app/              page.tsx, incidents/, approvals/, system/, api/incidents/[id]/, actions.ts
    components/       sidebar, shell, charts, incident-live, incident-table, ui, icons
    lib/              atlas.ts (server-only client), types.ts, format.ts
  docs/               architecture, threat model, decisions, evaluation report, design/
  docker-compose.yml, .github/workflows/ci.yml
""", "Listing 1. Repository structure.")
    s.append(heading("3.4 Size", 1))
    s.append(p(
        "Approximately 4,700 lines of Python in the backend application, 2,700 lines of TypeScript "
        "in the frontend, and 42 automated backend tests."))
    return s


def sec_architecture() -> list:
    s = [PageBreak(), heading("4. Architecture", 0)]
    s.append(heading("4.1 Design principles", 1))
    s.append(table([
        ["Principle", "Consequence in the design"],
        ["Deterministic control over critical actions",
         "Routing, authorization, approval, and the sufficiency gate are code. Models never decide "
         "whether something may happen."],
        ["Evidence before conclusions",
         "Agents emit typed evidence first; hypotheses reference it by ID; reports separate facts, "
         "hypotheses, and open questions."],
        ["Bounded autonomy",
         "Round cap, one step per agent per round, no repeated steps, tool-call budget, time budget."],
        ["Observable by design",
         "Every node, tool call, retry, model call, and decision becomes a persisted event."],
        ["Evaluation-driven", "A regression gate in CI runs the dataset on every change."],
        ["Complexity justified by evidence",
         "Agents exist where they isolate a data source or a decision; the planner is not an LLM "
         "because it does not need to be."],
    ], [0.3, 0.7]))
    s.append(callout(
        "Key decision: deterministic control plane, model-assisted analysis",
        "Models are used to extract structure from free text (triage), refine hypotheses (review), "
        "and write narrative (report). Every model output is validated against real identifiers and "
        "evidence IDs before it can influence the run. See ADR 0001.", "info"))
    s.append(heading("4.2 Runtime view", 1))
    s.append(p(
        "A request to create an incident persists a row in state " + c("queued") + ", writes an "
        "audit record and a " + c("workflow_queued") + " event, and returns 202. The incident "
        "service then runs the graph on a bounded thread pool. The graph checkpoints after every "
        "node. When the policy gate requires approval, the " + c("human_approval") + " node calls "
        + c("interrupt()") + "; the run ends, the service records an approval request and moves "
        "the incident to " + c("awaiting_approval") + ". A later approval call resumes the same "
        "thread with " + c("Command(resume=decision)") + ". Figure 2 shows the full sequence."))
    s.append(heading("4.3 Concurrency model", 1))
    s += bullets([
        f"{b('Workers')}: a {c('ThreadPoolExecutor')} with {c('WORKER_THREADS')} (default 4). "
        f"Each investigation runs synchronously on one worker; parallel branches inside the graph "
        f"are executed by LangGraph.",
        f"{b('Per-incident lock')}: an in-process lock serialises runs of the same incident, so a "
        f"resume cannot overlap a still-running invocation.",
        f"{b('Tool execution')}: a shared 16-thread pool runs tool functions so timeouts can be "
        f"enforced without blocking the worker.",
        f"{b('Inline mode')}: {c('EXECUTOR=inline')} runs the graph inside the request. Tests and the "
        f"evaluation runner use it for determinism.",
    ])
    s.append(figure(request_sequence(), "Figure 2. Submit, observe, approve: end-to-end sequence."))
    s.append(figure(deployment_view(), "Figure 3. Containerised deployment with Docker Compose.",
                    lead=[heading("4.4 Deployment view", 1)]))
    return s


def sec_workflow() -> list:
    s = [PageBreak(), heading("5. Workflow orchestration (LangGraph)", 0)]
    s.append(p(
        "The investigation is a compiled " + c("StateGraph") + " named "
        + c("atlas-incident-investigation") + " with a typed state schema and a runtime context "
        "schema. Figure 4 shows every node and edge."))
    s.append(figure(workflow_graph(), "Figure 4. Investigation graph. Violet nodes run in parallel "
                                      "via Send; amber diamonds are deterministic routers."))
    s.append(heading("5.1 State schema", 1))
    s.append(p(
        "State is explicit and typed rather than a shared conversation history. Fields marked "
        "additive use an " + c("operator.add") + " reducer so parallel branches and later rounds "
        "append rather than overwrite. Every other field has exactly one owning node."))
    s.append(table([
        ["Field", "Type", "Reducer", "Owner", "Purpose"],
        ["incident_id", "str", "replace", "initial", "Thread ID and idempotency prefix"],
        ["description", "str", "replace", "initial", "Operator text (untrusted)"],
        ["hints", "dict", "replace", "initial", "Optional service, deployment, severity"],
        ["incident_spec", "dict", "replace", "triage", "Validated IncidentSpec"],
        ["round", "int", "replace", "plan", "Current investigation round"],
        ["investigation_plan", "list[dict]", "replace", "plan", "Steps for this round"],
        ["completed_steps", "list[dict]", "add", "investigators", "Step outcomes incl. failures"],
        ["evidence", "list[dict]", "add", "investigators", "All evidence across rounds"],
        ["hypotheses", "list[dict]", "replace", "review", "Scored hypotheses"],
        ["review", "dict", "replace", "review", "ReviewResult incl. gaps"],
        ["final_report", "dict", "replace", "report", "Report body"],
        ["proposed_actions", "list[dict]", "replace", "report, policy_gate", "Actions, then classified"],
        ["approval_status", "str", "replace", "policy_gate, human_approval",
         "not_required, pending, approved, rejected"],
        ["approval", "dict", "replace", "human_approval", "Decision payload"],
        ["action_results", "list[dict]", "add", "execute_actions", "Per-action outcomes"],
    ], [0.2, 0.12, 0.09, 0.22, 0.37], mono_cols=(0,)))
    s.append(heading("5.2 Node catalogue", 1))
    s.append(table([
        ["Node", "Input", "Writes", "Model?", "Notes"],
        ["triage", "state", "incident_spec", "optional", "Calls services.list, deployments.list_recent"],
        ["plan", "state", "investigation_plan, round", "no", "Deterministic; at most one step per agent"],
        ["log_analysis", "InvestigationTask", "evidence, completed_steps", "no", "Fan-out target"],
        ["code_analysis", "InvestigationTask", "evidence, completed_steps", "no", "Fan-out target"],
        ["knowledge_retrieval", "InvestigationTask", "evidence, completed_steps", "no", "Fan-out target"],
        ["aggregate", "state", "nothing", "no", "Join point; emits coverage event"],
        ["review", "state", "review, hypotheses", "optional", "Deterministic gate always applies"],
        ["report", "state", "final_report, proposed_actions", "optional", "Narrative only from model"],
        ["policy_gate", "state", "proposed_actions, approval_status", "no", "Drops unknown action types"],
        ["human_approval", "state", "approval_status, approval", "no", "Calls interrupt()"],
        ["execute_actions", "state", "action_results", "no", "Only caller of side-effecting tools"],
    ], [0.2, 0.17, 0.26, 0.09, 0.28], mono_cols=(0,)))
    s.append(heading("5.3 Instrumented nodes", 1))
    s.append(p(
        "Each agent function is wrapped by " + c("instrumented(name, fn)") + ". The wrapper "
        "declares the signature " + c("(state, runtime: Runtime[WorkflowContext])") + " so "
        "LangGraph injects the run context, and on every invocation it:"))
    s += numbered([
        f"checks the cancellation flag and the wall-clock budget ({c('check_limits()')});",
        f"records {c('current_node')} on the incident and a {c('node_started')} event;",
        f"runs the agent and records {c('node_completed')} with duration and a compact summary of "
        f"the update (evidence IDs, plan, confidence, triage spec);",
        f"on an exception records {c('node_failed')} and re-raises, except for LangGraph control-flow "
        f"exceptions ({c('GraphBubbleUp')}, which includes interrupts) which pass through untouched.",
    ])
    s.append(p(
        "The three investigation nodes are additionally wrapped by " + c("degrade_gracefully") +
        ": a " + c("ToolInvocationError") + " becomes a failed step with no evidence and a "
        + c("step_failed") + " event, so one dead data source weakens the investigation instead of "
        "aborting it."))
    s.append(heading("5.4 Routing rules", 1))
    s.append(table([
        ["Router", "Rule", "Targets"],
        [c("route_investigations"), "One Send per plan step carrying an InvestigationTask "
                                     "(incident_id, round, step, incident_spec, evidence so far). "
                                     "Empty plan goes straight to aggregate.",
         "log_analysis, code_analysis, knowledge_retrieval, aggregate"],
        [c("route_after_review"), "report if review.sufficient or round >= MAX_INVESTIGATION_ROUNDS; "
                                   "otherwise plan only if the planner can produce at least one "
                                   "new step for round + 1; else report.",
         "plan, report"],
        [c("route_after_policy"), "human_approval if approval_status == pending, else execute_actions.",
         "human_approval, execute_actions"],
    ], [0.24, 0.5, 0.26]))
    s.append(heading("5.5 Termination argument", 1))
    s.append(p(
        "The only cycle is review to plan. It is taken only when the round counter is below the "
        "cap (default 2) and the planner can produce a step that has not already completed. The "
        "planner deduplicates by (agent, mode) and never schedules two steps for one agent in a "
        "round, so the number of investigation steps is bounded by 3 agents x 2 modes. "
        "Independently, the tool-call budget (40) and the wall-clock budget (600 s) stop any run, "
        "and LangGraph's recursion limit is set to 60."))
    s.append(heading("5.6 Human-in-the-loop interrupt", 1))
    s.append(p(
        c("human_approval") + " calls " + c("interrupt({type: approval_request, actions})") + ". "
        "LangGraph persists the pending interrupt in the checkpoint and the invocation returns. On "
        "resume the node runs again from the top, receives the decision as the return value of "
        + c("interrupt()") + ", and writes " + c("approval_status") + ". Because the node is "
        "re-executed, it contains no side effects; actions run in the next node."))
    s.append(heading("5.7 Run context", 1))
    s.append(p(
        c("WorkflowContext") + " is passed as LangGraph runtime context and is not checkpointed. It "
        "carries the settings, tool registry, model gateway, an event sink bound to the "
        "repository, a cancellation probe, a node-start callback, the per-run " + c("CallBudget") +
        ", and token usage counters. It is rebuilt on every start or resume, so budgets apply per "
        "invocation."))
    return s


def sec_agents() -> list:
    s = [PageBreak(), heading("6. Agent design", 0)]
    s.append(p(
        "Each agent has one narrow responsibility and a fixed set of tools. Where a model is "
        "optional, the deterministic implementation is the fallback for both 'no model configured' "
        "and 'model call failed', and a fallback emits an " + c("agent_fallback") + " event."))
    s.append(table([
        ["Agent", "Tools allowed", "Model role", "Output"],
        ["Triage", "services.list, deployments.list_recent", "Extraction, validated", "IncidentSpec"],
        ["Planner", "none", "none", "PlanStep list"],
        ["Log analysis", "logs.search, deployments.get", "none", "Evidence (logs)"],
        ["Code and commits", "deployments.get, deployments.list_recent, github.get_commit", "none",
         "Evidence (deployment, code)"],
        ["Knowledge retrieval", "knowledge.search", "none", "Evidence (knowledge)"],
        ["Root cause review", "none", "Hypothesis refinement, gated", "ReviewResult"],
        ["Reporting", "none", "Narrative fields only", "Report, ProposedAction list"],
        ["Action executor", "ticketing.create_ticket, ticketing.notify, deploy.rollback", "none",
         "Action results"],
    ], [0.18, 0.37, 0.2, 0.25]))

    # 6.1 triage
    s.append(heading("6.1 Incident Triage Agent", 1))
    s.append(p(
        "Turns free text into a validated " + c("IncidentSpec") + ": category, severity, symptoms, "
        "keywords, service and owning team, dependencies, deployment, and the analysis window."))
    s.append(heading("Extraction", 2))
    s.append(p(
        "With a model, " + c("TriageExtraction") + " is requested as structured output; the prompt "
        "contains the catalog service names and the description wrapped in an "
        + c("<untrusted>") + " block. Without a model, the heuristic extractor applies:"))
    s.append(table([
        ["Field", "Heuristic"],
        ["category", "First match in order: security (breach, unauthorized, leak, exfiltrat, credential); "
                     "deployment_regression (deploy, release, rollout, regression, new version); "
                     "availability (outage, down, unavailable, unreachable); latency (latency, slow, "
                     "p95, p99, timeout, timing out); error_spike (error, 5xx, 500, 502, 503, exception, "
                     "failing, failure); else unknown."],
        ["severity", "sev1 if the text mentions outage, all users, sev1, or down; sev3 for latency "
                     "or unknown; otherwise sev2."],
        ["service", "Longest catalog name or alias matched on word boundaries."],
        ["deployment", "First match of " + c("d-\\d{1,8}") + "."],
        ["time", "First ISO-8601 date or date-time; a bare date becomes midnight UTC."],
        ["symptoms", "Pattern table: 5xx, latency, timeouts, error rate, auth, payments, checkout."],
    ], [0.16, 0.84]))
    s.append(heading("Deterministic resolution", 2))
    s += numbered([
        "Service: operator hint, else extraction; kept only if it exists in the catalog.",
        "Deployment: if an ID is given and a service is known, it must appear in "
        "deployments.list_recent for that service. If no ID is given and the category is "
        "deployment_regression, the most recent deployment is used and marked "
        + c("deployment_inferred") + ".",
        "Pivot: the deployment time, else the reported time. Window: pivot +/- 2 hours. With no "
        "pivot: the last 6 hours.",
        "Category becomes deployment_regression if a deployment was resolved and the category was unknown.",
    ])
    s.append(callout("Why resolution is deterministic",
                     "A hallucinated service or deployment ID would send every downstream agent to "
                     "the wrong data. Resolving identifiers against source systems makes that "
                     "failure mode impossible rather than unlikely.", "ok"))

    # 6.2 planner
    s.append(heading("6.2 Investigation Planner", 1))
    s.append(p(
        "Round 1 always plans log analysis and knowledge retrieval, plus code analysis when a "
        "service is known. Later rounds translate review gaps into steps:"))
    s.append(table([
        ["Gap", "Step", "Mode", "Objective"],
        ["logs", "log_analysis", "default", "Re-query logs for the incident window"],
        ["logs_wide", "log_analysis", "wide", "Check whether the pattern predates the incident"],
        ["code", "code_analysis", "default", "Inspect changes shipped near the incident"],
        ["previous_deployments", "code_analysis", "wide", "Inspect earlier deployments"],
        ["knowledge", "knowledge_retrieval", "wide", "Search by observed error signatures"],
        ["dependency_health", "none", "-", "No tool exists; reported as an open question"],
    ], [0.22, 0.2, 0.1, 0.48], mono_cols=(0, 1)))
    s.append(p(
        "A candidate is skipped if its agent already has a step this round or if the same "
        "(agent, mode) completed successfully earlier. Failed steps do not count as completed, "
        "so a failed source can be retried once in the next round. Step IDs are "
        + c("r{round}-{agent}") + "."))

    # 6.3 logs
    s.append(heading("6.3 Log Analysis Agent", 1))
    s.append(p(
        "Queries " + c("logs.search") + " for the service at INFO and above (limit 2,000 records). "
        "Wide mode extends the window by 6 hours before and 2 hours after. Records are 5-minute "
        "aggregates with a count."))
    s.append(heading("Error-rate change", 2))
    s += code("""
for each record:  side = after if timestamp >= pivot else before
                  total[side] += count;  if level == ERROR: errors[side] += count
rate(side)      = round(100 * errors[side] / total[side], 2)
onset_minutes   = minutes from pivot to the first ERROR record after it
""", "Listing 2. Error-rate computation (one evidence item, kind error_rate_change).")
    s.append(heading("Error signatures", 2))
    s.append(p(
        "ERROR and WARN messages are normalised (hex IDs to " + c("<id>") + ", durations to "
        + c("<dur>") + ", truncated to 240 characters), clustered, and the four largest clusters "
        "become " + c("error_signature") + " evidence with total count, count before the pivot, "
        "first-seen time, and a " + c("new_since_pivot") + " flag."))
    s.append(heading("Untrusted content", 2))
    s.append(p(
        "Messages matching the injection patterns (Section 12.5) are excluded from clustering and "
        "reported as " + c("untrusted_content") + " evidence flagged " + c("possible_prompt_injection")
        + ". The bundled checkout data contains one such line on purpose."))

    # 6.4 code
    s.append(heading("6.4 Code and Commit Analysis Agent", 1))
    s.append(p(
        "Selects deployments, fetches each commit, and annotates it with risk signals."))
    s += bullets([
        "Default mode with a resolved deployment: that deployment only.",
        "Otherwise: up to 5 recent deployments before the pivot, within 24 hours (default) or 7 "
        "days (wide, excluding the already-inspected deployment).",
        "No deployment in range: a " + c("no_recent_deployment") + " evidence item, which later "
        "supports infrastructure hypotheses.",
    ])
    s.append(table([
        ["Risk signal", "Rule"],
        ["dependency change", "A changed file matches requirements*.txt, pyproject.toml, "
                              "package(-lock).json, go.mod, or pom.xml."],
        ["major version upgrade", "Dependency change and the message or diff shows X.y.z to/-> Y.y.z "
                                  "with X != Y."],
        ["capacity/timeout configuration change", "A config file (.yaml, .toml, .ini, .env, .json) "
                                                  "changed and the diff mentions pool, max_size, "
                                                  "overflow, limit, timeout, replicas, workers, or threads."],
        ["call signature change", "The diff both removes and adds lines containing a call."],
    ], [0.32, 0.68]))

    # 6.5 knowledge
    s.append(heading("6.5 Knowledge Retrieval Agent", 1))
    s.append(p(
        "Markdown documents with front matter (title, kind, services) are split into section "
        "chunks at " + c("## ") + " headings and indexed with BM25 (k1 = 1.4, b = 0.75, stopword "
        "removal). Chunks from documents tagged with the incident's service, or with " + c("all")
        + ", get a 1.25 score boost. Hits below a score of 2.0 are discarded and each document "
        "contributes at most one evidence item."))
    s.append(p(
        "Round 1 queries with symptoms, keywords, and the category. Wide mode (round 2) queries "
        "with up to three observed error signatures plus the first four terms, which is what finds "
        "the specific runbook once the logs have named the failure."))

    # 6.6 review
    s.append(heading("6.6 Root Cause Review Agent", 1))
    s.append(p(
        "Builds candidate hypotheses from evidence, scores them from explicit signals, and decides "
        "whether evidence is sufficient. A model, if configured, may refine statements and scores, "
        "but its output is validated and the sufficiency decision is always gated in code."))
    s.append(heading("6.6.1 Signals", 2))
    s.append(table([
        ["Signal", "Definition"],
        ["Temporal correlation", "Pivot is a deployment, after-rate > 2 x before-rate + 0.5, and "
                                 "errors start 0 to 30 minutes after the pivot."],
        ["Pre-existing errors", "Before-rate > 0.5% and before-rate >= 0.8 x after-rate (contradicts "
                                "change-based hypotheses)."],
        ["Overlap", "Size of the intersection between identifier-aware tokens of the commit "
                    "(message, diff, files) and of an error signature. Tokens split snake_case and "
                    "CamelCase, so StripeClient.create_charge yields stripe, client, create_charge, "
                    "create, charge."],
        ["Matched signature", "A signature sharing at least 2 tokens with the commit."],
        ["Runbook support", "A knowledge item sharing at least 3 tokens with the commit plus "
                            "matched signatures."],
        ["Precedent", "Runbook support includes a postmortem."],
    ], [0.24, 0.76]))
    s.append(heading("6.6.2 Change hypotheses (one per commit)", 2))
    s += code("""
overlap_score = min(max_overlap / 4, 1.0)
confidence    = 0.35 * overlap_score
              + 0.35  if temporal correlation
              + 0.15  if runbook support
              + 0.05  if precedent (postmortem)
confidence   *= 0.5   if no matched signature
confidence   -= 0.30  if pre-existing errors (contradicting evidence recorded)
confidence    = clamp(confidence, 0.02, 0.95)

kind = config_change       if 'capacity/timeout configuration change'
       dependency_upgrade  elif 'dependency change'
       code_change         otherwise
""", "Listing 3. Change-hypothesis scoring.")
    s.append(p(
        "The statement names the commit, deployment, matched signature, and onset. If another "
        "commit in the same deployment carries a major version upgrade, the statement adds it as a "
        "likely incompatibility; this is how the payments scenario attributes the failure to the "
        "call-site change combined with the SDK upgrade."))
    s.append(heading("6.6.3 Infrastructure hypotheses (one per dependency)", 2))
    s.append(p(
        "For each catalog dependency of the service that appears in an error signature:"))
    s += code("""
confidence = (0.30 if the signature is new since the pivot else 0.15)
           + 0.15 if a knowledge item shares >= 2 tokens with the dependency and signatures
           + 0.15 if no deployment preceded the incident
confidence = min(confidence, 0.60)   # cannot be confirmed without the dependency's telemetry
""", "Listing 4. Infrastructure-hypothesis scoring.")
    s.append(heading("6.6.4 Sufficiency gate", 2))
    s.append(p("Hypotheses are sorted by confidence. Evidence is sufficient only if all hold:"))
    s += numbered([
        "top confidence >= SUFFICIENT_CONFIDENCE (0.70);",
        "the top hypothesis cites evidence from at least two distinct sources;",
        "one of those sources is knowledge, or the confidence is at least 0.85 (strong direct signal).",
    ])
    s.append(callout(
        "Effect on the loop",
        "In the checkout scenario round 1 reaches 0.70 from logs and code alone. Because no "
        "runbook corroborates it yet, the gate fails, the review names the knowledge gap, round 2 "
        "searches by the observed QueuePool signature, finds the runbook and the July postmortem, "
        "and confidence rises to 0.90.", "info"))
    s.append(heading("6.6.5 Gap derivation", 2))
    s.append(table([
        ["Condition (only when not sufficient)", "Gaps added"],
        ["No usable log evidence", "logs"],
        ["Service known but no code or deployment evidence", "code"],
        ["No knowledge evidence, or the top hypothesis lacks knowledge support", "knowledge"],
        ["Top hypothesis is infrastructure", "dependency_health, logs_wide"],
        ["Top hypothesis is a change with contradicting evidence", "previous_deployments"],
        ["No hypothesis, or top confidence < 0.4", "logs_wide, previous_deployments"],
    ], [0.68, 0.32]))
    s.append(p(
        "Gaps whose step already completed successfully are then removed, so the report's open "
        "questions list only what is genuinely unknown."))
    s.append(heading("6.6.6 Validating model output", 2))
    s += bullets([
        "Evidence IDs not present in the collected evidence are removed from every hypothesis.",
        "Hypotheses left with no supporting evidence are dropped; if none remain, the rule-based "
        "review is used and a " + c("model_output_rejected") + " event is recorded.",
        "The gate in 6.6.4 is re-applied, and the result is sufficient only if both the gate and "
        "the model agree.",
    ])

    # 6.7 reporting
    s.append(heading("6.7 Reporting Agent", 1))
    s.append(table([
        ["Report status", "Condition"],
        ["root_cause_identified", "review.sufficient"],
        ["probable_cause", "not sufficient, top confidence >= 0.4"],
        ["inconclusive", "otherwise"],
    ], [0.35, 0.65], mono_cols=(0,)))
    s.append(p(
        "Structure, references, and actions are built in code. A model, if configured, writes "
        "only " + c("ReportNarrative") + " (title, summary, impact, remediation, unknowns). Report "
        "fields: title, status, summary, impact, root_cause (hypothesis ID, statement, kind, "
        "confidence, evidence IDs), facts (each with evidence IDs), hypotheses, timeline (up to 15 "
        "timestamped evidence items), unknowns, remediation, security_notes, evidence, "
        "investigation (rounds, steps, rationale), generated_by, incident_spec; after completion "
        "also actions with outcomes and the approval decision."))
    s.append(heading("Proposed actions", 2))
    s.append(table([
        ["Action", "Proposed when", "Parameters"],
        ["create_ticket", "A service is known", "title, body, service, severity"],
        ["notify_channel", "The service has an owning channel", "channel, message"],
        ["rollback_deployment", "Top hypothesis is a change kind, evidence is sufficient, and the "
                                "deployment's previous deployment is known",
         "service, from_deployment, to_deployment"],
    ], [0.23, 0.47, 0.3], mono_cols=(0,)))

    # 6.8 actions
    s.append(heading("6.8 Policy gate and action executor", 1))
    s.append(p(
        "The policy gate looks up each proposed action in " + c("ACTION_POLICIES") + "; unknown "
        "types are dropped with an " + c("action_blocked") + " event. The executor runs each "
        "action whose policy does not require approval, or all actions when the decision is "
        "approved. Every call carries the idempotency key " + c("{incident_id}:{action_id}") +
        ". Failures are recorded per action and do not fail the workflow."))
    s.append(table([
        ["Action type", "Risk", "Approval", "Tool"],
        ["create_ticket", "medium", "required", "ticketing.create_ticket"],
        ["rollback_deployment", "high", "required", "deploy.rollback"],
        ["notify_channel", "low", "not required", "ticketing.notify"],
    ], [0.3, 0.15, 0.2, 0.35], mono_cols=(0, 3)))
    return s


def sec_evidence() -> list:
    s = [PageBreak(), heading("7. Evidence model", 0)]
    s.append(p(
        "Evidence is the contract between gathering and reasoning. It is validated by Pydantic on "
        "creation and stored in state as plain dictionaries."))
    s.append(table([
        ["Field", "Type", "Notes"],
        ["id", "str", "Source prefix + round + sequence: L, C, D, K (e.g. L1.3, K2.1)"],
        ["source", "enum", "logs, code, deployment, knowledge"],
        ["kind", "str", "error_rate_change, error_signature, untrusted_content, no_data, deployment, "
                        "commit, missing_commit, no_recent_deployment, runbook, postmortem, "
                        "architecture, no_match"],
        ["summary", "str (<= 600)", "Human-readable; scanned for injection on creation"],
        ["details", "dict", "Structured data used by the review (rates, signature, diff, text)"],
        ["references", "list[str]", "Source URIs: logs://, git://, deploys://, kb://"],
        ["timestamp", "str | null", "ISO-8601; drives the report timeline"],
        ["flags", "list[str]", "e.g. possible_prompt_injection"],
        ["round", "int", "Round in which it was collected"],
    ], [0.17, 0.17, 0.66], mono_cols=(0,)))
    s.append(p(
        "IDs are unique because the planner allows only one step per agent per round. The "
        "deployment agent shares a counter between deployment (D) and code (C) items, so a run "
        "may have D1.1 followed by C1.2."))
    s.append(callout("Grounding guarantee",
                     "Every evidence ID in a report resolves to an item in report.evidence. The "
                     "evaluation measures this (evidence grounding) and CI requires 1.0.", "ok"))
    return s


def sec_tools() -> list:
    s = [heading("8. Tool layer", 0)]
    s.append(p(
        "All access to external systems goes through " + c("ToolRegistry.invoke(caller, name, "
                                                            "args)") + ". It is the single place "
        "where permissions, validation, timeouts, retries, budgets, and auditing are enforced."))
    s.append(figure(tool_pipeline(), "Figure 5. Tool invocation pipeline and failure exits."))
    s.append(heading("8.1 Invocation contract", 1))
    s += numbered([
        f"Unknown tool or caller not in {c('AGENT_TOOL_ALLOWLIST')}: emit {c('tool_denied')}, raise "
        f"{c('ToolNotPermittedError')}.",
        f"Validate arguments against the tool's Pydantic model: on failure raise "
        f"{c('ToolValidationError')}.",
        f"For each attempt: consume one unit of the run's {c('CallBudget')} (raise "
        f"{c('ToolBudgetExceededError')} when spent), apply fault injection, run the function on the "
        f"tool pool with {c('TOOL_TIMEOUT_S')} (10 s).",
        f"Transient failure (including timeout): if attempts remain, emit {c('tool_retry')}, sleep "
        f"and retry; else emit {c('tool_failed')} and raise.",
        f"Permanent failure: emit {c('tool_failed')}, raise without retry. Any unexpected exception "
        f"is converted to a permanent error.",
        f"Success: emit {c('tool_called')} with caller, tool, attempt, redacted arguments, duration, "
        f"side-effect flag, and result size.",
    ])
    s += code("""
delay(attempt) = TOOL_BACKOFF_BASE_S * 2^(attempt - 1) * (0.5 + U(0, 0.5))
               = 0.2 s, 0.4 s, 0.8 s (+/- jitter) with defaults, max 3 retries
""", "Listing 5. Exponential backoff with jitter.")
    s.append(heading("8.2 Error taxonomy", 1))
    s.append(table([
        ["Error", "Retry", "Typical cause", "Workflow effect"],
        ["ToolNotPermittedError", "no", "Agent outside its allowlist", "Step fails (degrades)"],
        ["ToolValidationError", "no", "Bad arguments", "Step fails (degrades)"],
        ["TransientToolError", "yes", "Timeout, throttling, unavailability", "Retried, then step fails"],
        ["PermanentToolError", "no", "Not found, misconfiguration, bug", "Step fails (degrades)"],
        ["ToolBudgetExceededError", "no", "Run used MAX_TOOL_CALLS", "Remaining steps fail"],
    ], [0.27, 0.08, 0.35, 0.3], mono_cols=(0,)))
    s.append(heading("8.3 Tool catalogue", 1))
    s.append(table([
        ["Tool", "Side effect", "Input constraints", "Allowed callers"],
        ["services.list", "no", "none", "triage"],
        ["deployments.list_recent", "no", "service ^[a-z0-9-]+$, before?, limit 1-20",
         "triage, code_analysis"],
        ["deployments.get", "no", "deployment_id ^d-\\d{1,8}$", "log_analysis, code_analysis"],
        ["github.get_commit", "no", "sha ^[0-9a-f]{7,40}$", "code_analysis"],
        ["logs.search", "no", "service, start < end, window <= 7 days, min_level, contains <= 200, "
                              "limit <= 2000", "log_analysis"],
        ["knowledge.search", "no", "query 2-500 chars, service?, top_k 1-10", "knowledge_retrieval"],
        ["ticketing.create_ticket", "yes", "idempotency_key, title 3-200, body <= 20,000, service, "
                                           "severity sev1-4", "action_executor"],
        ["ticketing.notify", "yes", "idempotency_key, channel ^#[a-z0-9-]+$, message <= 4,000",
         "action_executor"],
        ["deploy.rollback", "yes", "idempotency_key, service, from/to deployment IDs",
         "action_executor"],
    ], [0.25, 0.1, 0.43, 0.22], mono_cols=(0,)))
    s.append(heading("8.4 Idempotent side effects", 1))
    s.append(p(
        "Side-effecting tools route through " + c("IdempotentStore.run_once(key, action)") + ": the "
        "first call executes and stores the result; any later call with the same key returns the "
        "stored result marked " + c("replayed: true") + ". Combined with the stable key "
        + c("{incident_id}:{action_id}") + ", a retried tool call or a resumed workflow cannot act "
        "twice. Real integrations should pass the key to the external system (for example as a "
        "request idempotency header) so the guarantee survives process restarts."))
    s.append(heading("8.5 Fault injection", 1))
    s.append(p(
        c("FAULT_INJECTION") + " takes comma-separated " + c("tool:kind:count") + " entries; "
        "kind is " + c("transient") + ", " + c("permanent") + ", or " + c("timeout") + ". Each "
        "entry fails the next count calls of that tool. Example: "
        + c("logs.search:transient:2,github.get_commit:permanent:1") + ". The reliability tests "
        "and the evaluation runner's " + c("--fault") + " option use it."))
    s.append(heading("8.6 Mock integrations", 1))
    s.append(table([
        ["Data", "Contents"],
        ["services.json", "4 services with team, channel, tier, dependencies, aliases"],
        ["deployments.json", "4 deployments (checkout d-2041/d-2033, payments d-3107, auth d-1188)"],
        ["commits.json", "6 commits with messages, files, diffs"],
        ["logs.json", "235 aggregated 5-minute records, generated by scripts/generate_mock_logs.py"],
        ["knowledge/*.md", "4 runbooks, 1 postmortem, 1 architecture note"],
    ], [0.25, 0.75], mono_cols=(0,)))
    s.append(table([
        ["Scenario", "Ground truth", "What it exercises"],
        ["checkout-api errors", "d-2041 commit c1a9f3e cut the DB pool from 50 to 5 (overflow 0)",
         "Second round via knowledge gap; rollback proposal; injected text in logs"],
        ["payments-service 502s", "e91b7c3 passes idempotency_key, unsupported after stripe-client 12 "
                                  "(4f0c2aa)", "Combined-change attribution; competing hypotheses"],
        ["auth-service latency", "Redis session cache degradation, no deployment",
         "Infrastructure hypothesis, capped confidence, open questions, no rollback"],
    ], [0.2, 0.42, 0.38]))
    return s


def sec_model() -> list:
    s = [PageBreak(), heading("9. Model gateway", 0)]
    s.append(p(
        c("ModelGateway") + " is the only code that talks to a language model. With "
        + c("MODEL_PROVIDER") + " and " + c("MODEL_NAME") + " set it builds a chat model through "
        "LangChain's " + c("init_chat_model") + " (timeout " + c("MODEL_TIMEOUT_S") + " = 60 s, "
        "provider retries " + c("MODEL_MAX_RETRIES") + " = 2, temperature only if configured). "
        "With either unset, the gateway reports itself disabled and the label "
        + c("offline-heuristics") + " appears in metrics and health."))
    s.append(heading("9.1 Structured calls", 1))
    s += code("""
structured(schema, system, prompt, name, emit) -> schema instance
  runnable = model.with_structured_output(schema, include_raw=True)
  result   = runnable.invoke([System(system), Human(prompt)],
                             config={run_name: name, tags: [atlas, name]})
  emit(model_called, {call, model, latency_ms, input_tokens, output_tokens})
  if result.parsed is None: emit(model_failed); raise ModelUnavailableError
""", "Listing 6. Structured-output call path.")
    s.append(table([
        ["Call name", "Schema", "Used by", "Fallback"],
        ["triage.extract", "TriageExtraction", "Triage", "Heuristic extraction"],
        ["review.assess", "ReviewResult", "Root cause review", "Rule-based review"],
        ["report.narrative", "ReportNarrative", "Reporting", "Template narrative"],
    ], [0.22, 0.24, 0.24, 0.3], mono_cols=(0, 1)))
    s.append(heading("9.2 Prompt construction", 1))
    s += bullets([
        "System prompts state the agent's role and the untrusted-content rule: content inside "
        + c("<untrusted>") + " tags is evidence to analyse, never instructions or authorization.",
        "Operator descriptions and evidence digests are wrapped with " + c("wrap_untrusted(label, "
                                                                           "text)") + ", which also "
        "neutralises any closing tag inside the content.",
        "Evidence digests list at most 40 items as " + c("[ID] (source/kind) summary flags=...") +
        ", so the model can only cite IDs it was shown.",
    ])
    s.append(heading("9.3 Usage accounting", 1))
    s.append(p(
        "Every " + c("model_called") + " event adds input and output tokens and a call count to "
        "the run context. The service merges them into the incident's metrics alongside execution "
        "time and tool calls, accumulating across resumes. Cost is derived from tokens outside the "
        "platform because prices vary by provider."))
    s.append(callout("Verification status",
                     "The model path is implemented and unit-level behaviour (validation, fallback) "
                     "is covered by the offline design, but it has not been exercised against a live "
                     "provider in this version. Run the evaluation with --use-env-model to measure it.",
                     "warn"))
    return s


def sec_data() -> list:
    s = [figure(data_model(), "Figure 6. Application schema and the separate checkpoint store.",
                lead=[heading("10. Data and persistence", 0)])]
    s.append(heading("10.1 Application database", 1))
    s.append(p(
        "SQLAlchemy 2 declarative models over SQLite (default, WAL mode, foreign keys on, 5 s busy "
        "timeout) or PostgreSQL via psycopg 3. JSON columns hold the triage spec, report, metrics, "
        "event payloads, approval actions, and audit details. The schema is created at startup "
        "with " + c("create_all") + " (migrations are planned)."))
    s.append(heading("10.2 Repository operations with concurrency guarantees", 1))
    s.append(table([
        ["Operation", "Guarantee"],
        ["transition(id, from_statuses, to)", "Single conditional UPDATE; returns False if the "
                                              "incident was not in an allowed state."],
        ["decide_approval(id, decision, actor)", "UPDATE ... WHERE status = 'pending'; exactly one "
                                                 "decision can win, repeats return 409."],
        ["expire_approvals(id)", "Pending requests become expired when an incident is cancelled."],
        ["add_event / audit", "Payloads are redacted before insert."],
        ["merge_metrics(id, values)", "Read-merge-write of the metrics JSON."],
    ], [0.36, 0.64], mono_cols=(0,)))
    s.append(figure(state_machine(), "Figure 7. Incident status transitions.",
                    lead=[heading("10.3 Incident state machine", 1)]))
    s.append(table([
        ["From", "To", "Trigger"],
        ["queued", "running", "Worker picks up the incident (also on startup recovery)"],
        ["running", "awaiting_approval", "Graph interrupted at human_approval"],
        ["awaiting_approval", "running", "Approval decision recorded; resume dispatched"],
        ["running", "completed", "Graph reached END"],
        ["running", "failed", "Unhandled error or wall-clock budget exceeded"],
        ["running", "cancelled", "Cancel flag observed at the next node boundary"],
        ["queued, awaiting_approval", "cancelled", "Cancel request (immediate); approvals expire"],
    ], [0.27, 0.2, 0.53], mono_cols=(0, 1)))
    s.append(heading("10.4 Checkpoint store", 1))
    s.append(p(
        "Configured with " + c("CHECKPOINTER") + ": " + c("memory") + " (tests), " + c("sqlite")
        + " (default; " + c("SqliteSaver") + " on a dedicated file), or " + c("postgres") + " ("
        + c("PostgresSaver.from_conn_string") + ", which expects a plain " + c("postgresql://")
        + " URL). The thread ID is the incident ID. Resources are owned by the application's "
        "lifespan " + c("ExitStack") + "."))
    return s


def sec_api() -> list:
    s = [PageBreak(), heading("11. API design", 0)]
    s.append(p(
        "JSON over HTTP, versioned under " + c("/api/v1") + ". Authentication is an " + c("X-API-Key")
        + " header. OpenAPI documentation is served at " + c("/docs") + "."))
    s.append(table([
        ["Method", "Path", "Permission", "Success", "Errors"],
        ["POST", "/api/v1/incidents", "incident:create", "202 IncidentDetail", "401, 403, 422, 429"],
        ["GET", "/api/v1/incidents?status=&limit=", "incident:read", "200 IncidentList", "401, 403, 422"],
        ["GET", "/api/v1/incidents/{id}", "incident:read", "200 IncidentDetail", "401, 403, 404"],
        ["GET", "/api/v1/incidents/{id}/report", "incident:read", "200 ReportOut", "404, 409 (no report yet)"],
        ["GET", "/api/v1/incidents/{id}/events?after=&limit=", "incident:read", "200 EventList", "404"],
        ["POST", "/api/v1/incidents/{id}/approvals", "action:approve", "200 IncidentDetail",
         "403 (role or separation of duties), 404, 409"],
        ["POST", "/api/v1/incidents/{id}/cancel", "incident:cancel", "200 IncidentDetail", "404, 409"],
        ["GET", "/api/v1/me", "any valid key", "200 PrincipalOut", "401"],
        ["GET", "/health", "none", "200 HealthOut", "-"],
    ], [0.1, 0.33, 0.15, 0.19, 0.23], mono_cols=(1,)))
    s.append(heading("11.1 Request validation", 1))
    s.append(table([
        ["Field", "Constraint"],
        ["description", "10 to 5,000 characters"],
        ["service_name", "^[a-z0-9-]{2,64}$ (optional)"],
        ["deployment_id", "^d-\\d{1,8}$ (optional)"],
        ["severity", "sev1 | sev2 | sev3 | sev4 (optional)"],
        ["(any other field)", "Rejected (extra = forbid)"],
        ["decision", "approved | rejected; comment <= 2,000 characters"],
    ], [0.25, 0.75], mono_cols=(0,)))
    s.append(heading("11.2 Representative payloads", 1))
    s += code("""
POST /api/v1/incidents
{ "description": "payments-service is returning 502s on charges since deployment d-3107" }

202 Accepted
{ "id": "inc_6427fabe18006ce6", "status": "queued", "service_name": null,
  "pending_approval": null, "approvals": [], "has_report": false,
  "links": { "self": "/api/v1/incidents/inc_6427fabe18006ce6",
             "report": ".../report", "events": ".../events",
             "approvals": ".../approvals", "cancel": ".../cancel" }, ... }

POST /api/v1/incidents/inc_6427fabe18006ce6/approvals
{ "decision": "approved", "comment": "verified in staging" }
""", "Listing 7. Submitting and approving an investigation.")
    s.append(heading("11.3 Polling model", 1))
    s.append(p(
        "Clients poll the incident and events. Events have a monotonically increasing " + c("seq")
        + "; " + c("?after=<seq>") + " returns only newer events and " + c("next_after") + " gives "
        "the cursor. The report endpoint returns " + c("final: false") + " while actions await "
        "approval, so the draft can be reviewed before deciding. Streaming (SSE) is planned."))
    return s


def sec_security() -> list:
    s = [PageBreak(), heading("12. Security design", 0)]
    s.append(heading("12.1 Authentication", 1))
    s.append(p(
        c("API_KEYS") + " maps keys to principals: " + c('{"key": {"subject": "...", "role": "..."}}')
        + ". Keys are compared with " + c("hmac.compare_digest") + ". In development only, an empty "
        "map enables " + c("atlas-dev-key") + " as admin and logs a warning; production refuses to "
        "start without keys."))
    s.append(heading("12.2 Authorization", 1))
    s.append(table([
        ["Role", "incident:read", "incident:create", "incident:cancel", "action:approve"],
        ["viewer", "yes", "-", "-", "-"],
        ["operator", "yes", "yes", "yes", "-"],
        ["approver", "yes", "-", "-", "yes"],
        ["admin", "yes", "yes", "yes", "yes"],
    ], [0.2, 0.2, 0.2, 0.2, 0.2]))
    s.append(p(
        "With " + c("REQUIRE_SEPARATION_OF_DUTIES=true") + ", the subject who submitted an incident "
        "cannot approve its actions, even as admin."))
    s.append(heading("12.3 Least-privilege tools", 1))
    s.append(p(
        "The allowlist in Section 8.3 is enforced by the registry, not by prompts. No reasoning "
        "agent can reach a side-effecting tool; the executor reaches them only after the policy "
        "gate and, where required, a recorded human decision."))
    s.append(heading("12.4 Input validation", 1))
    s.append(p(
        "API inputs are validated by Pydantic models with patterns and bounds. Tool inputs are "
        "validated again inside the registry. Frontend Server Actions repeat the same checks for "
        "fast feedback, but the backend remains authoritative."))
    s.append(heading("12.5 Prompt injection and untrusted content", 1))
    s.append(table([
        ["Layer", "Control"],
        ["Detection (signal)", "Six case-insensitive patterns: ignore previous/prior instructions; "
                               "disregard system/previous prompt; 'you are now'; approve/execute/run "
                               "rollback/action/command immediately/now/automatically; do not "
                               "tell/inform the user/operator; fake system/assistant tags."],
        ["Containment (control)", "Untrusted text is delimited in prompts; models cannot call tools; "
                                  "identifiers and evidence IDs are validated; actions need policy "
                                  "and approval."],
        ["Disclosure", "Flagged evidence appears under 'Untrusted content flagged' in the report and "
                       "console."],
    ], [0.22, 0.78]))
    s.append(callout("Design stance",
                     "Detection is pattern-based and will miss novel phrasing. It is deliberately "
                     "not relied on: even an undetected injection cannot cause an action, because "
                     "no model output can authorize one.", "risk"))
    s.append(heading("12.6 Redaction", 1))
    s.append(table([
        ["Pattern", "Replacement"],
        ["Bearer tokens", "Bearer [REDACTED]"],
        ["sk-... style keys", "[REDACTED_KEY]"],
        ["AWS access key IDs (AKIA/ASIA)", "[REDACTED_AWS_KEY]"],
        ["GitHub tokens (ghp_, gho_, ...)", "[REDACTED_GH_TOKEN]"],
        ["password|secret|api_key|token = value", "key=[REDACTED]"],
        ["Postgres URL credentials", "user:[REDACTED]@"],
        ["Email addresses", "[REDACTED_EMAIL]"],
    ], [0.5, 0.5]))
    s.append(p(
        "Redaction is applied recursively to event payloads, audit details, and logged tool "
        "arguments before they are stored. It does not apply to LangSmith traces (Section 14.3)."))
    s.append(heading("12.7 Rate limiting and secrets", 1))
    s += bullets([
        "Incident submission is limited per principal (default 20 per minute), fixed window, in "
        "memory or in Redis when " + c("REDIS_URL") + " is set. Exceeding it returns 429 with "
        "Retry-After.",
        "Secrets come from the environment. The frontend's key is read only in server modules "
        "marked " + c("server-only") + ", so a client import fails the build.",
        "CORS allows only configured origins, GET and POST, and two headers.",
    ])
    s.append(heading("12.8 Threats and mitigations", 1))
    s.append(table([
        ["Threat", "Mitigation"],
        ["Injected text triggers a rollback", "No model-reachable side effects; policy + approval"],
        ["Hallucinated identifiers misdirect investigation", "Resolution against catalog and deploy system"],
        ["Unsupported conclusions", "Evidence-ID validation; sufficiency gate; capped infra confidence"],
        ["Privilege misuse", "Roles; separation of duties; audit records for every command"],
        ["Duplicate external actions", "Idempotency keys; conditional approval update; per-incident lock"],
        ["Runaway cost or loops", "Round cap, tool budget, timeouts, wall clock, rate limit"],
        ["Secret leakage into storage", "Redaction before persistence"],
        ["Key exposure in browser", "Server-only API client; BFF route"],
    ], [0.42, 0.58]))
    return s


def sec_reliability() -> list:
    s = [PageBreak(), heading("13. Reliability and failure handling", 0)]
    s.append(table([
        ["Failure", "Detection", "Behaviour", "Verified by"],
        ["Transient tool error or timeout", "Exception / future timeout",
         "Retry with backoff, up to 3", "Reliability test: transient retry"],
        ["Evidence source down", "PermanentToolError",
         "Step fails; review sees gap; report not over-claimed", "Reliability test: dead source"],
        ["Process crash mid-run", "Incident left running at startup",
         "Resume from last checkpoint; completed nodes not re-run", "Reliability test: crash and resume"],
        ["Operator cancels", "cancel_requested flag", "Stops before next node", "Reliability test: cancellation"],
        ["Tool budget spent", "CallBudget", "Remaining steps fail; run completes",
         "Reliability test: tool budget"],
        ["Model error / bad output", "Exception / parsed is None", "Deterministic fallback; event",
         "design (no live provider in CI)"],
        ["Double approval", "Conditional UPDATE", "Second decision 409", "API test: approve flow (replay 409)"],
        ["Action retried after resume", "Idempotency key", "Replayed result, no second execution",
         "Unit test: idempotent store"],
        ["Workflow exceeds time", "check_limits()", "Marked failed with reason", "design"],
    ], [0.2, 0.2, 0.3, 0.3]))
    s.append(heading("13.1 Durable execution and recovery", 1))
    s.append(p(
        "On startup " + c("IncidentService.recover()") + " finds incidents in " + c("queued")
        + " or " + c("running") + ", records " + c("workflow_recovered") + ", and dispatches "
        "them. A run with an existing checkpoint is continued with " + c("invoke(None)") + "; one "
        "without a checkpoint starts from the initial state. Incidents awaiting approval need no "
        "recovery: their interrupt is already persisted."))
    s.append(heading("13.2 Exactly-once is not assumed", 1))
    s.append(p(
        "A retry alone does not guarantee exactly-once execution. External actions are designed "
        "for idempotency and their outcome is recorded per action (executed, skipped, failed, or "
        "replayed). With real integrations, the idempotency key must be honoured by the external "
        "system and outcomes reconciled against its records."))
    s.append(heading("13.3 Budgets", 1))
    s.append(table([
        ["Budget", "Default", "Scope"],
        ["MAX_INVESTIGATION_ROUNDS", "2", "Per incident"],
        ["MAX_TOOL_CALLS", "40", "Per invocation (start or resume)"],
        ["MAX_WORKFLOW_SECONDS", "600", "Per invocation, checked at node boundaries"],
        ["TOOL_TIMEOUT_S", "10", "Per tool attempt"],
        ["TOOL_MAX_RETRIES", "3", "Per tool call"],
        ["MODEL_TIMEOUT_S / MODEL_MAX_RETRIES", "60 / 2", "Per model call"],
        ["recursion_limit", "60", "LangGraph supersteps per invocation"],
        ["RATE_LIMIT_PER_MINUTE", "20", "Submissions per principal"],
    ], [0.42, 0.15, 0.43], mono_cols=(0,)))
    return s


def sec_observability() -> list:
    s = [heading("14. Observability", 0)]
    s.append(heading("14.1 Workflow events", 1))
    s.append(p("Every incident has an append-only, redacted event stream (catalogue in Appendix B). "
               "The console's activity feed and pipeline view are built from it."))
    s.append(heading("14.2 Metrics", 1))
    s.append(table([
        ["Metric", "Source", "Where shown"],
        ["execution_ms", "Wall time of each invocation, summed", "Incident metrics, dashboard median"],
        ["tool_calls", "CallBudget.used, summed", "Run metrics panel"],
        ["model_calls, input_tokens, output_tokens", "model_called events", "Run metrics panel"],
        ["model", "Gateway label", "Run metrics, /health"],
        ["Evaluation metrics", "Evaluation runner", "CI artifact, evaluation report"],
    ], [0.36, 0.34, 0.3], mono_cols=(0,)))
    s.append(heading("14.3 Tracing with LangSmith", 1))
    s.append(p(
        "Setting " + c("LANGSMITH_TRACING=true") + " and " + c("LANGSMITH_API_KEY") + " enables "
        "LangChain/LangGraph tracing. Each run is named " + c("incident-investigation") + ", tagged "
        "with " + c("atlas") + " and the environment, and carries " + c("incident_id") + ", "
        "environment, and model as metadata; model calls are named per agent (" + c("triage.extract")
        + ", " + c("review.assess") + ", " + c("report.narrative") + "). Traces contain model "
        "inputs and are not covered by Atlas redaction."))
    s.append(heading("14.4 Audit trail", 1))
    s.append(p(
        "Commands write audit records: " + c("incident.submitted") + " (with hints), "
        + c("approval.approved") + " / " + c("approval.rejected") + " (with approval ID, comment, "
        "action IDs), and " + c("incident.cancel_requested") + ". Records are never updated."))
    s.append(heading("14.5 Planned", 1))
    s += bullets(["OpenTelemetry spans and metrics export.",
                  "LangSmith datasets and experiments for prompt and model comparison."])
    return s


def sec_frontend() -> list:
    s = [PageBreak(), heading("15. Frontend design", 0)]
    s.append(p(
        "Next.js 16 App Router with Cache Components and Partial Prefetching enabled, React 19, "
        "Tailwind CSS 4, TypeScript. The console never sees the API key."))
    s.append(figure(frontend_flow(), "Figure 8. Frontend data flow."))
    s.append(heading("15.1 Data access", 1))
    s.append(table([
        ["Mechanism", "Used for", "Notes"],
        ["Server Components", "Dashboard, lists, approvals, system, initial incident detail",
         "Uncached fetches wrapped in Suspense, as Cache Components requires"],
        ["BFF route /api/incidents/[id]", "Live polling of one incident",
         "Returns incident, events, and report in one response"],
        ["Server Actions", "Create, approve/reject, cancel",
         "Validate input, relay, map API errors to messages, call refresh()"],
        ["lib/atlas.ts", "All backend calls", "server-only import; attempt() returns ok/error "
                                              "without throwing so pages render errors cleanly"],
    ], [0.27, 0.33, 0.4]))
    s.append(heading("15.2 Pages", 1))
    s.append(table([
        ["Route", "Content"],
        ["/", "Stat cards with sparklines, activity bar chart (7 days), status donut, recent "
              "investigations, root causes by type"],
        ["/incidents", "Filter chips by status with counts, text search (?q=), full table"],
        ["/incidents/new", "Form with example prompts and optional hints; process explainer"],
        ["/incidents/[id]", "Header, 10-step pipeline progress, approval panel, findings, "
                            "hypotheses, actions, filterable evidence, run metrics, activity feed"],
        ["/approvals", "Pending approvals with action risk and a link to decide"],
        ["/system", "Health tiles and the agent and tool permission table"],
    ], [0.2, 0.8], mono_cols=(0,)))
    s.append(heading("15.3 Live view behaviour", 1))
    s += bullets([
        "Polls every 1.2 s while queued or running, every 5 s while awaiting approval, and stops "
        "when terminal.",
        "Pipeline state is derived from node_started, node_completed, node_failed, and step_failed "
        "events; nodes not needed are shown as such.",
        "Evidence chips link to anchored evidence items; flagged items are highlighted.",
    ])
    s.append(heading("15.4 Visual design and accessibility", 1))
    s.append(p(
        "A dark, glass-panel console. All colours are CSS custom properties in "
        + c("globals.css") + ". Status pills always include a text label and an icon, so colour is "
        "never the only signal."))
    s.append(table([
        ["Chart element", "Decision"],
        ["Donut palette", "Categorical slots #3987e5, #d95926, #199e70, #c98500 against surface "
                          "#111733. Validated: worst adjacent colour-blind separation 8.4 "
                          "(target >= 8), normal-vision 19.8 (floor 15), ring wrap pair 27.4, all "
                          "contrast >= 3:1. Red/green status colours were rejected (deutan "
                          "separation 4.1)."],
        ["Legend", "Always present with counts and percentages, doubling as the table view"],
        ["Bar chart", "Single series, single hue; hover and keyboard focus show a tooltip; values "
                      "also in a screen-reader table"],
        ["Marks", "Thin lines, rounded data ends, solid hairline grid, 2 px gaps between donut segments"],
        ["Motion", "Pulse animations disabled under prefers-reduced-motion"],
    ], [0.2, 0.8]))
    return s


def sec_evaluation() -> list:
    s = [PageBreak(), heading("16. Evaluation", 0)]
    s.append(p(
        "The runner (" + c("python -m app.evaluation.run") + ") executes the workflow in-process "
        "for each case, always rejects gated actions so nothing external runs, and scores the "
        "final state."))
    s.append(table([
        ["Evaluator", "Definition"],
        ["root_cause_accuracy", "1 if the top hypothesis ID matches and all expected keywords are in "
                                "the statement; 0.5 if only the ID matches; for inconclusive cases, 1 "
                                "if the report is inconclusive."],
        ["outcome_acceptable", "Report status is in the case's accepted set."],
        ["triage_accuracy", "Share of service and category that match."],
        ["evidence_grounding", "Share of evidence references in root cause, facts, and hypotheses "
                               "that resolve."],
        ["unsupported_claim_rate", "Share of hypotheses citing no supporting evidence (lower is better)."],
        ["tool_selection_accuracy", "Jaccard similarity of round-1 agents with the expected set."],
        ["approval_policy_compliance", "0 if a rollback is not gated or a gated action ran without "
                                       "approval; otherwise 1 if rollback was proposed exactly when "
                                       "expected."],
    ], [0.3, 0.7], mono_cols=(0,)))
    s.append(heading("16.1 Dataset", 1))
    s.append(table([
        ["Case", "Exercises"],
        ["checkout-pool-latest-deploy", "Inferred deployment, second round, rollback"],
        ["checkout-pool-explicit-hints", "Operator hints override extraction"],
        ["payments-sdk-upgrade", "Combined-change attribution"],
        ["auth-redis-degradation", "Infrastructure cause, probable status, no rollback"],
        ["unknown-service-insufficient-evidence", "Inconclusive without inventing a cause"],
        ["prompt-injection-in-description", "Injected instruction in the operator's text has no effect"],
    ], [0.42, 0.58], mono_cols=(0,)))
    s.append(heading("16.2 Results (offline, 13 October 2026)", 1))
    s.append(table([
        ["Case", "Status", "Root cause", "Conf.", "RC acc.", "Grounding"],
        ["checkout-pool-latest-deploy", "root_cause_identified", "H-c1a9f3e", "0.90", "1.00", "1.00"],
        ["checkout-pool-explicit-hints", "root_cause_identified", "H-c1a9f3e", "0.90", "1.00", "1.00"],
        ["payments-sdk-upgrade", "root_cause_identified", "H-e91b7c3", "0.85", "1.00", "1.00"],
        ["auth-redis-degradation", "probable_cause", "H-dep-redis-sessions", "0.60", "1.00", "1.00"],
        ["unknown-service-...", "inconclusive", "-", "-", "1.00", "1.00"],
        ["prompt-injection-...", "root_cause_identified", "H-c1a9f3e", "0.90", "1.00", "1.00"],
    ], [0.27, 0.2, 0.2, 0.09, 0.12, 0.12]))
    s.append(p(
        "Aggregate: success rate 1.00, root-cause accuracy 1.00, triage 1.00, grounding 1.00, "
        "unsupported claims 0.00, tool selection 1.00, approval compliance 1.00, latency p50 22 ms "
        "and p95 26 ms, 0 tokens."))
    s.append(callout(
        "Interpretation",
        "The cases were written alongside the mock data and the heuristics, which are expected to "
        "score perfectly on them. These results show correct wiring and guard against "
        "regressions; they are not evidence of accuracy on real incidents. Real quality must be "
        "measured with cases from real incidents with verified causes and, ideally, a configured "
        "model.", "warn"))
    s.append(heading("16.3 Regression gate", 1))
    s.append(p(
        c("tests/evaluation/test_regression.py") + " fails CI unless errors = 0, root-cause accuracy "
        ">= 0.95, success >= 0.95, grounding = 1.0, unsupported claims = 0, and approval compliance "
        "= 1.0, and it re-runs the dataset with injected transient faults in logs and knowledge "
        "search."))
    return s


def sec_testing() -> list:
    s = [heading("17. Testing strategy", 0)]
    s.append(table([
        ["Suite", "Tests", "Covers"],
        ["Unit: security", "5", "Role permissions, action policy, tool allowlist, redaction, "
                                "injection detection and wrapping"],
        ["Unit: tool registry", "9", "Denial, validation, transient retry, retry exhaustion, no retry "
                                     "on permanent, exception conversion, timeout, budget, idempotency"],
        ["Unit: agents", "6", "Triage heuristics and aliases, identifier tokenisation, sufficiency gate, "
                              "gap pruning, BM25 ranking"],
        ["Unit: config", "3", "CORS as CSV or JSON, API keys from JSON env"],
        ["Integration: API", "12", "Health, 401, RBAC, validation, approve flow and replay 409, "
                                   "reject flow, ambiguous incident, cancel, list counts, separation "
                                   "of duties, rate limit, /me"],
        ["Failure scenarios", "5", "Transient faults, dead source, crash and resume, cancellation, "
                                   "tool budget"],
        ["Evaluation gate", "2", "Quality bar; quality under injected faults"],
        ["Total", "42", "All run offline with SQLite in a temporary directory"],
    ], [0.22, 0.08, 0.7]))
    s.append(p(
        "Integration tests run the real application with " + c("EXECUTOR=inline") + " so requests "
        "complete deterministically. The crash test raises a " + c("BaseException") + " from the "
        "review node to leave the incident running with a partial checkpoint, then starts a new "
        "application instance on the same files and asserts that recovery completes the run "
        "without re-running triage."))
    s.append(p(
        "Frontend quality gates are type checking, ESLint (including React Compiler rules), and a "
        "production build, which validates Cache Components constraints such as Suspense "
        "boundaries. Visual checks were done with headless browser screenshots at desktop and "
        "narrow widths."))
    s.append(heading("17.1 Gaps", 1))
    s += bullets([
        "Postgres checkpointer and Redis rate limiter paths are not exercised by tests.",
        "The model path has not been run against a live provider.",
        "No automated frontend component or end-to-end browser tests yet.",
    ])
    return s


def sec_operations() -> list:
    s = [PageBreak(), heading("18. Deployment and operations", 0)]
    s.append(heading("18.1 Local development", 1))
    s += code("""
# backend
cd backend && python -m venv .venv && .venv/Scripts/activate   # or source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000

# frontend
cd frontend && npm install && cp .env.example .env.local && npm run dev
""", "Listing 8. Running locally (offline mode, SQLite).")
    s.append(heading("18.2 Containers", 1))
    s.append(p(
        "The backend image is python:3.12-slim, installs the package with the Anthropic extra, "
        "runs as an unprivileged user, and has an HTTP health check. The frontend image is a "
        "three-stage node:24-alpine build. Compose wires Postgres for both application data and "
        "checkpoints, Redis for rate limits, and passes optional model and LangSmith variables "
        "through from the host environment."))
    s.append(figure(ci_pipeline(), "Figure 9. GitHub Actions jobs.",
                    lead=[heading("18.3 Continuous integration", 1)]))
    s.append(heading("18.4 Scaling considerations", 1))
    s += bullets([
        "Work runs on an in-process pool with in-process per-incident locks. Running several API "
        "replicas safely requires a shared queue and a distributed per-incident lock (for example "
        "Redis), with workers separate from the API (planned).",
        "Postgres should be used for both stores in any shared deployment.",
        "Events grow linearly with tool calls (about 40 to 55 per offline investigation); add "
        "retention and pagination for long histories.",
    ])
    s.append(heading("18.5 Production checklist", 1))
    s += bullets([
        "Set APP_ENV=production and API_KEYS; enable REQUIRE_SEPARATION_OF_DUTIES.",
        "Use Postgres for DATABASE_URL and CHECKPOINTER; add migrations before schema changes.",
        "Restrict CORS_ORIGINS to the console's origin; terminate TLS in front of both services.",
        "Decide on LangSmith tracing given that traces contain model inputs.",
        "Replace mock tools with real integrations that honour idempotency keys.",
    ])
    return s


def sec_limitations() -> list:
    s = [heading("19. Limitations, risks, and roadmap", 0)]
    s.append(table([
        ["Limitation or risk", "Impact", "Mitigation or plan"],
        ["Mock integrations", "Results do not reflect real data quality", "Implement real tools behind the same contracts"],
        ["Heuristics tuned to scenarios", "Offline accuracy will drop on new failure types",
         "Configure a model; grow the dataset from real incidents"],
        ["In-process workers and locks", "Unsafe to scale API replicas", "Queue + distributed lock"],
        ["create_all instead of migrations", "Schema changes need manual steps", "Alembic"],
        ["Pattern-based injection detection", "Misses novel phrasing", "Controls do not depend on it"],
        ["Traces not redacted", "Sensitive inputs may reach LangSmith", "Disable or configure redaction"],
        ["Polling", "Extra load and latency", "Server-sent events"],
        ["Keyword-only retrieval", "Misses paraphrased runbooks", "Hybrid BM25 + embeddings"],
    ], [0.3, 0.33, 0.37]))
    s.append(heading("19.1 Roadmap", 1))
    s += numbered([
        "Real integrations: log store, GitHub, deploy system, ticketing.",
        "Model evaluation with LangSmith datasets and experiments; prompt versioning.",
        "OpenTelemetry instrumentation.",
        "Alembic migrations.",
        "Queue-based workers for multi-replica deployments.",
        "Hybrid retrieval.",
        "Evaluation cases from real incidents with verified causes.",
        "Frontend end-to-end tests.",
    ])
    return s


def appendices() -> list:
    s = [PageBreak(), heading("Appendix A. Configuration reference", 0)]
    s.append(table([
        ["Variable", "Default", "Description"],
        ["APP_ENV", "development", "development | test | production"],
        ["LOG_LEVEL", "INFO", "Python logging level"],
        ["DATABASE_URL", "sqlite:///backend/atlas.db", "SQLAlchemy URL"],
        ["CHECKPOINTER", "sqlite", "memory | sqlite | postgres"],
        ["CHECKPOINT_URL", "backend/atlas_checkpoints.db", "File path or postgresql:// URL"],
        ["REDIS_URL", "(unset)", "Enables shared rate limiting"],
        ["API_KEYS", "{}", "JSON map key -> {subject, role}"],
        ["CORS_ORIGINS", "http://localhost:3000", "CSV or JSON list"],
        ["REQUIRE_SEPARATION_OF_DUTIES", "false", "Submitter cannot approve"],
        ["RATE_LIMIT_PER_MINUTE", "20", "Submissions per principal"],
        ["MODEL_PROVIDER / MODEL_NAME", "(unset)", "Enable model gateway, e.g. anthropic / claude-sonnet-5-5"],
        ["MODEL_TEMPERATURE", "(unset)", "Passed only if set"],
        ["MODEL_TIMEOUT_S / MODEL_MAX_RETRIES", "60 / 2", "Per model call"],
        ["MAX_INVESTIGATION_ROUNDS", "2", "Review loop cap"],
        ["MAX_TOOL_CALLS", "40", "Per invocation"],
        ["MAX_WORKFLOW_SECONDS", "600", "Per invocation"],
        ["TOOL_TIMEOUT_S / TOOL_MAX_RETRIES", "10 / 3", "Per tool"],
        ["TOOL_BACKOFF_BASE_S", "0.2", "Backoff base"],
        ["SUFFICIENT_CONFIDENCE", "0.7", "Sufficiency threshold"],
        ["EXECUTOR / WORKER_THREADS", "thread / 4", "thread | inline"],
        ["FAULT_INJECTION", "(empty)", "tool:kind:count list"],
        ["LANGSMITH_TRACING / _API_KEY / _PROJECT", "false / - / atlas-ai", "Tracing"],
        ["ATLAS_API_URL (frontend)", "http://localhost:8000", "Backend base URL"],
        ["ATLAS_API_KEY (frontend)", "atlas-dev-key", "Server-side key"],
    ], [0.38, 0.25, 0.37], mono_cols=(0,)))

    s.append(heading("Appendix B. Event catalogue", 0))
    s.append(table([
        ["Event", "Emitted by", "Payload highlights"],
        ["workflow_queued / started / recovered", "service", "by, resumed, model"],
        ["workflow_completed / failed / cancelled", "service", "status, rounds, error"],
        ["cancel_requested", "service", "by"],
        ["node_started / node_completed / node_failed", "node wrapper", "duration_ms, updated keys, "
                                                                        "evidence IDs, plan, confidence"],
        ["plan_created", "planner", "round, steps"],
        ["evidence_aggregated", "aggregate", "new_items, total_items, by_source, flagged"],
        ["review_completed", "review", "top hypothesis, confidence, sufficient, gaps"],
        ["step_failed", "investigation wrapper", "step, error"],
        ["tool_called / tool_retry / tool_failed / tool_denied", "registry", "tool, caller, attempt, "
                                                                             "duration, backoff, args"],
        ["model_called / model_failed", "gateway", "call, model, latency, tokens, error"],
        ["agent_fallback / model_output_rejected", "agents", "reason"],
        ["action_blocked / action_failed", "policy gate / executor", "action_id, reason, error"],
        ["approval_requested / approval_decided", "service", "approval_id, actions, decision, by"],
    ], [0.42, 0.2, 0.38], mono_cols=(0,)))

    s.append(heading("Appendix C. Report excerpt (checkout scenario)", 0))
    s += code("""
{
  "title": "checkout-api: configuration change in d-2041 (deployment regression)",
  "status": "root_cause_identified",
  "root_cause": {
    "hypothesis_id": "H-c1a9f3e", "kind": "config_change", "confidence": 0.9,
    "statement": "Commit c1a9f3e in deployment d-2041 (\\"config: lower database pool
      max_size from 50 to 5 to reduce RDS connection count\\") reduced capacity settings,
      matching the new error \\"sqlalchemy.exc.TimeoutError: QueuePool limit of size 5
      overflow 0 reached...\\" that began 5 min after the deployment.",
    "evidence_ids": ["C1.2", "L1.1", "L1.3", "K2.1", "K2.3"]
  },
  "impact": "Error rate for checkout-api rose from 0.0% to 58.69% after
             2026-10-10T14:00:00Z (32,680 failed events in the analysed window) [L1.1].",
  "remediation": [
    "Roll back checkout-api from d-2041 to d-2033 to restore service, then fix forward.",
    "Restore the previous capacity settings and load test before reapplying.",
    "Follow runbook: Database connection pool exhaustion [K2.1]."
  ],
  "security_notes": [{ "evidence_id": "L1.5",
    "note": "Log record contains instruction-like text; it was treated as data ..." }],
  "investigation": { "rounds": 2, ... },
  "actions": [ { "type": "rollback_deployment", "requires_approval": true, "risk": "high",
                 "outcome": { "status": "executed",
                              "idempotency_key": "inc_...:act-rollback" } }, ... ]
}
""", "Listing 9. Abbreviated report produced by the offline workflow.")

    s.append(heading("Appendix D. Decision log", 0))
    s.append(table([
        ["Decision", "Alternatives", "Rationale"],
        ["Deterministic planner", "LLM planner", "Plans are a small finite set; determinism makes "
                                                 "loops provably bounded and runs reproducible"],
        ["Separate checkpoint store", "Store state in app tables", "Use LangGraph's tested savers; "
                                                                    "keep the app schema small"],
        ["Polling over SSE", "SSE / WebSockets", "Simpler first version; events already support cursors"],
        ["API keys with roles", "OAuth/OIDC", "Sufficient for service-to-service and a single console; "
                                              "OIDC is a later integration"],
        ["Sync workers on threads", "asyncio graph", "Tools and SQLAlchemy are sync; threads keep the "
                                                     "code simple and testable"],
        ["BM25 retrieval", "Vector DB", "No embedding dependency; strong on error-string matches"],
        ["BFF + server-only key", "Browser calls API with token", "Keeps the credential out of the "
                                                                  "browser entirely"],
    ], [0.24, 0.24, 0.52]))
    return s


def build() -> Path:
    doc = DesignDoc(
        str(OUT),
        title="Atlas AI - Technical Design Document",
        subtitle="Multi-agent incident investigation with evidence-based\n"
                 "root-cause analysis and human-approved remediation",
        meta=META,
    )
    story: list = [Spacer(1, 1)]
    story += front_matter()
    for section in (sec_introduction, sec_goals, sec_overview, sec_architecture, sec_workflow,
                    sec_agents, sec_evidence, sec_tools, sec_model, sec_data, sec_api,
                    sec_security, sec_reliability, sec_observability, sec_frontend,
                    sec_evaluation, sec_testing, sec_operations, sec_limitations, appendices):
        story += section()
    doc.multiBuild(story)
    return OUT


if __name__ == "__main__":
    path = build()
    print(f"wrote {path} ({path.stat().st_size / 1024:.0f} KB)")
