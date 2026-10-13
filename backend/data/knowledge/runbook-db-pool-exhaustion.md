---
title: Runbook - Database connection pool exhaustion
kind: runbook
services: checkout-api, payments-service
---

## Symptoms

Requests fail with `QueuePool limit ... reached, connection timed out` or `TimeoutError` from SQLAlchemy.
HTTP 500 rates rise sharply while database CPU stays normal. Latency increases first, then errors follow.

## Likely causes

- Pool `max_size` or `max_overflow` reduced in configuration.
- Long-running transactions holding connections (check `pg_stat_activity`).
- Traffic spike exceeding pool capacity.

## Mitigation

1. Confirm recent changes to `config/database.yaml` or pool environment variables.
2. If a recent deployment reduced pool capacity, roll back the deployment or restore the previous pool size.
3. Verify the database `max_connections` budget before raising pool sizes across many replicas.

## Verification

Error rate for `POST /api/v1/checkout` returns to baseline (< 0.5%) within 10 minutes of mitigation.
