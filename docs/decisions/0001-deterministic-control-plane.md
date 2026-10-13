# ADR 0001: Deterministic control plane, model-assisted analysis

- Status: accepted
- Date: 2026-10-12

## Context

Atlas AI investigates production incidents and can propose actions such as rolling back a deployment. Model output is probabilistic and can be steered by untrusted content in logs, commits, and documents.

## Decision

1. Planning, routing, authorization, approval, and action execution are deterministic code.
2. Models are used for language-heavy work only: extracting structure from free text (triage), refining hypotheses (review), and writing narrative (report).
3. Every model output passes a deterministic validator: identifiers are resolved against source systems, evidence references must exist, and "sufficient evidence" requires two independent sources plus corroboration.
4. Each agent has a deterministic implementation, used when no model is configured or when a model call fails.

## Consequences

- The full workflow runs offline, which makes CI, evaluation, and local development free and reproducible.
- Model failures degrade quality instead of availability.
- The deterministic baseline is tuned to the shipped mock scenarios; with real integrations, quality depends on the configured model and must be measured with the evaluation runner.
- Adding an agent is justified only when it improves measured outcomes, not to increase agent count.
