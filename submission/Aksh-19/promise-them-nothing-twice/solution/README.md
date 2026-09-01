# RelayAPI thin vertical slice

## Decision in one paragraph

I resolve the CTO/support conflict in favor of the signed contract: Northwind's contracted quota remains a hard limit, so there is **no hidden Northwind bypass**. Support's legitimate business concern becomes a commercial/configuration follow-up, not a production-path exception. Because Northwind is contracted for 300 RPM but currently sends 800–1200 RPM, this slice will correctly return 429s above 300 RPM. The limiter uses an exact Redis-backed sliding-window log and an atomic Lua decision, so all three stateless nodes coordinate on one customer budget.

## Why exact sliding window?

A fixed window can admit nearly 2x the configured RPM across a minute boundary. A token bucket intentionally permits bursts above the nominal RPM unless its capacity is specially constrained, which makes it a poor fit for the CTO's literal "never exceed" requirement. An exact sliding window defines the audit rule directly:

> At request time `t`, count accepted requests with timestamps in `[t-60s, t)`. Admit iff that count is below the customer's contracted RPM.

Redis sorted sets store timestamps per customer. A Lua script removes expired entries, counts the remaining entries, and conditionally inserts the new request atomically. Thus nodes cannot independently spend stale local counters.

## Run in under 15 minutes

Requirements: Docker Desktop (or Docker Engine + Compose) and Python 3.11+.

```bash
cd solution
docker compose up --build
```

In another terminal:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python harness/harness.py
```

Expected headline results:

```text
[1] 100 RPM boundary across 3 nodes
test-100-a | 100 OK | 1 429
test-100-b | 100 OK | 1 429
test-100-c | 100 OK | 1 429

[2] Per-customer isolation
A after 100 requests | 100 | 0
B first request      | 1   | 0

[4] Concurrent race / atomicity
500 simultaneous requests -> 100 OK, 400 rejected
```

The exact node distribution is intentionally not fixed; round-robin sends requests to all three processes.

To run one scenario:

```bash
python harness/harness.py --scenario 100
python harness/harness.py --scenario isolation
python harness/harness.py --scenario boundary
python harness/harness.py --scenario concurrency
```

## HTTP behavior

Every request needs `X-Customer-Id`.

Success:

- `200 OK`
- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Algorithm: exact-sliding-window`
- `X-Relay-Node`

Limit exceeded:

- `429 Too Many Requests`
- `Retry-After` calculated from the oldest request currently occupying the window.

The demo config includes `northwind` at 300 RPM and test customers at 100 RPM. There is no `if Northwind` bypass.

## What this proves

The harness demonstrates:
1. Exact quota behavior when requests are spread across three independent app processes.
2. Customer isolation.
3. Atomic rejection under a concurrent race.
4. A rolling-window boundary where changing wall-clock minutes does not reset the budget.

It does **not** prove production-grade Redis HA, clock discipline across hosts, network partitions, durability, dynamic billing/config synchronization, or sustained Northwind-scale traffic for two hours. Those are intentionally outside the thin vertical slice.

## Counting semantics for security review

RelayAPI counts accepted requests per customer in a rolling 60-second window. At request time, entries older than 60 seconds are removed; if fewer than the contracted RPM number remain, the request is atomically recorded and accepted. Otherwise it receives HTTP 429 with `Retry-After`. The counter is shared through Redis and the admission decision is atomic, so load balancing across stateless application nodes does not create separate per-node budgets.

## Clean-up

```bash
docker compose down -v
```
