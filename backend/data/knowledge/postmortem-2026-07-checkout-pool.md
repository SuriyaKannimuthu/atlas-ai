---
title: Postmortem - Checkout outage caused by pool misconfiguration (July 2026)
kind: postmortem
services: checkout-api
---

## Summary

On 2026-07-14 checkout-api returned HTTP 500 for 23 minutes. A configuration change reduced the SQLAlchemy pool `max_overflow` to 0 during a traffic peak, exhausting connections.

## Root cause

Pool capacity was reduced to lower RDS connection count without load testing. Requests waited 30 seconds for a connection and then failed with `QueuePool limit reached`.

## Resolution

Rolled back to the previous deployment. Restored `max_size: 50` and `max_overflow: 10`.

## Follow-ups

- Add a CI check that flags pool size reductions greater than 50%.
- Load test configuration changes to connection pools before release.
