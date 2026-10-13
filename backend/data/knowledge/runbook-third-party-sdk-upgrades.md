---
title: Runbook - Third-party SDK upgrade regressions
kind: runbook
services: payments-service
---

## Symptoms

`TypeError` or `AttributeError` raised from vendor client calls immediately after a deployment.
Upstream-facing endpoints return 502 because the outbound call fails before it is sent.

## Likely causes

- Major version bump of a vendor SDK (for example `stripe-client` 11 -> 12) that changed method signatures.
- Keyword arguments renamed or moved into an options object.

## Mitigation

1. Compare the changelog for the new major version against the call sites touched in the deployment.
2. Roll back to the previous deployment if charge success rate drops below 95%.
3. Pin the SDK to the previous major version and schedule a migration with contract tests.

## Notes

stripe-client 12.0.0 moved `idempotency_key` into `RequestOptions`; passing it as a keyword argument raises `TypeError`.
