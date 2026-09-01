# 01 — ChatGPT build session

## User prompt

The user supplied the full "Promise Them Nothing Twice" take-home assignment, including the scenario, CTO memo, Support lead memo, platform context, required deliverables, and asked: "make me everything right now".

## Assistant work

The assistant resolved the conflict explicitly in favor of the CTO's signed hard quota requirement, rejecting a hidden Northwind bypass. It selected an exact Redis-backed sliding-window algorithm with an atomic Lua admission script so three stateless application nodes share one per-customer budget.

The generated vertical slice contains:
- FastAPI rate-limiting service
- Redis shared state
- Docker Compose with Redis + three application nodes
- 100-RPM, isolation, rolling-boundary, and concurrency load scenarios
- README with setup, counting semantics, tradeoffs, and limitations
- DECISIONS.md
- This session record

No external coding-agent transcript exists for this ChatGPT session, so no tool calls, hidden chain-of-thought, or fabricated agent logs are included.
