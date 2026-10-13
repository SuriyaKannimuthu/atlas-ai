---
title: Architecture - Checkout path
kind: architecture
services: checkout-api, payments-service
---

## Request flow

The web client calls `POST /api/v1/checkout` on checkout-api. checkout-api reads the cart from `redis-cart`, writes the order to `postgres-orders`, and calls payments-service `POST /charges`.

## Capacity

checkout-api runs 12 replicas. Each replica holds a SQLAlchemy pool. Peak traffic requires roughly 30 concurrent connections per replica.

## Failure modes

- Pool exhaustion surfaces as HTTP 500 from checkout-api.
- payments-service failures surface as HTTP 502 from checkout-api and from payments-service itself.
