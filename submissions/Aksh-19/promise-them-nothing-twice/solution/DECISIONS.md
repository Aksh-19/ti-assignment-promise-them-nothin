# Decisions

## 1. CTO vs. Support conflict

I explicitly choose the CTO's signed contractual requirement over the support request to silently exempt Northwind. Northwind remains capped at its contracted 300 RPM. I reject a customer-specific bypass, soft-limit mode, or invisible exception in the production request path.

Support's concern is real, but the compatible resolution is commercial: renegotiate Northwind's contract/quota or change its workload architecture after approval. A future approved exception belongs in authoritative configuration and audit, not an `if customer == Northwind` branch.

## 2. Algorithm and coordination

I use an exact Redis-backed sliding-window log. Each customer's request timestamps live in a Redis sorted set. One Lua script atomically expires old entries, checks the count, and inserts the request only if under quota. This avoids local process state and prevents three app nodes from independently admitting the same customer's budget.

I rejected fixed windows because they can admit almost two windows' worth of traffic around a boundary. I rejected an ordinary token bucket because its burst capacity conflicts with the literal no-over-quota requirement.

## 3. What the harness proves

It proves per-customer isolation, exact 100-RPM admission, rejection on request 101, multi-node coordination, atomicity under 500 concurrent requests, and rolling-window boundary semantics. The output is intentionally readable without inspecting code.

It does not prove Redis failover/HA, distributed clock skew, two-hour 800–1200 RPM production behavior, billing integration, or operational SLOs.

## 4. Next four hours

1. Add Redis Sentinel/managed-Redis failure tests and define fail-closed behavior.
2. Replace demo tier config with signed/validated authoritative configuration and audit events.
3. Add a real load generator capable of sustained 1200 RPM for 120 minutes plus metrics/p95 latency.
4. Add property-based tests around timestamp boundaries and concurrency.
