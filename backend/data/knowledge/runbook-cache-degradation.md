---
title: Runbook - Session cache (Redis) degradation
kind: runbook
services: auth-service
---

## Symptoms

`redis: i/o timeout` warnings, elevated login latency, and occasional session lookups falling back to Postgres.

## Likely causes

- Redis primary failover or network partition between the service and `redis-sessions`.
- Memory pressure causing evictions and slow commands.
- Noisy neighbours on the shared cache cluster.

## Mitigation

1. Check the cache provider status page and the `redis-sessions` failover events.
2. Confirm whether latency correlates with a deployment. If not, treat as an infrastructure incident.
3. Escalate to the platform team; application rollbacks rarely help this class of incident.
