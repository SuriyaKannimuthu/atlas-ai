---
title: Runbook - Rolling back a deployment
kind: runbook
services: all
---

## When to roll back

Roll back when a deployment is the most likely cause of customer-facing errors and a forward fix will take longer than 15 minutes.

## Procedure

1. Identify the previous known-good deployment ID from the deployment record.
2. Request approval from the on-call approver. Rollbacks of tier-1 services always require approval.
3. Trigger the rollback and monitor error rate and latency for 15 minutes.
4. Open a follow-up ticket to fix forward and record the rollback in the incident report.
