#!/usr/bin/env python3
import argparse
import asyncio
import time
from collections import Counter
import httpx

DEFAULT_NODES = [
    "http://localhost:8001",
    "http://localhost:8002",
    "http://localhost:8003",
]

async def request(client, node, customer):
    r = await client.get(f"{node}/api/v1/ping", headers={"X-Customer-Id": customer})
    return r.status_code, node, r.headers

async def hammer(client, nodes, customer, n):
    results = []
    tasks = []
    for i in range(n):
        tasks.append(request(client, nodes[i % len(nodes)], customer))
    return await asyncio.gather(*tasks)

async def scenario_exact_100(nodes):
    async with httpx.AsyncClient(timeout=10) as client:
        rows = []
        for customer in ["test-100-a", "test-100-b", "test-100-c"]:
            results = await hammer(client, nodes, customer, 101)
            counts = Counter(r[0] for r in results)
            by_node = Counter(r[1] for r in results)
            rows.append((customer, counts[200], counts[429], dict(by_node)))
        return rows

async def scenario_isolation(nodes):
    async with httpx.AsyncClient(timeout=10) as client:
        a = await hammer(client, nodes, "test-100-a", 100)
        b = await hammer(client, nodes, "test-100-b", 1)
        return Counter(x[0] for x in a), Counter(x[0] for x in b)

async def scenario_rolling_boundary(nodes):
    # Uses a 5 RPM test customer so the boundary test is laptop-friendly.
    async with httpx.AsyncClient(timeout=10) as client:
        first = await hammer(client, nodes, "boundary-5", 5)
        sixth = await request(client, nodes[0], "boundary-5")
        await asyncio.sleep(1.2)
        # Still inside 60s: must remain rejected.
        near = await request(client, nodes[1], "boundary-5")
        return first, sixth, near

async def scenario_concurrency(nodes):
    # A single atomic Lua decision must admit exactly 100 of 500 concurrent
    # requests, regardless of which node receives each request.
    async with httpx.AsyncClient(timeout=20) as client:
        results = await hammer(client, nodes, "test-100-c", 500)
        return Counter(r[0] for r in results)

def print_table(headers, rows):
    widths = [len(h) for h in headers]
    for row in rows:
        for i, value in enumerate(row):
            widths[i] = max(widths[i], len(str(value)))
    line = " | ".join(h.ljust(widths[i]) for i,h in enumerate(headers))
    print(line)
    print("-+-".join("-"*w for w in widths))
    for row in rows:
        print(" | ".join(str(v).ljust(widths[i]) for i,v in enumerate(row)))

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nodes", nargs="+", default=DEFAULT_NODES)
    ap.add_argument("--scenario", choices=["all","100","isolation","boundary","concurrency"], default="all")
    args = ap.parse_args()

    print(f"Nodes: {', '.join(args.nodes)}")
    if args.scenario in ("all", "100"):
        rows = await scenario_exact_100(args.nodes)
        print("\n[1] 100 RPM boundary across 3 nodes")
        print_table(["customer","200 OK","429","node distribution"], rows)

    if args.scenario in ("all", "isolation"):
        a, b = await scenario_isolation(args.nodes)
        print("\n[2] Per-customer isolation")
        print_table(["customer","200 OK","429"], [
            ("A after 100 requests", a[200], a[429]),
            ("B first request", b[200], b[429]),
        ])

    if args.scenario in ("all", "boundary"):
        first, sixth, near = await scenario_rolling_boundary(args.nodes)
        print("\n[3] Rolling 60-second boundary")
        print(f"Initial 5: {Counter(r[0] for r in first)}")
        print(f"6th immediately: {sixth[0]} Retry-After={sixth[2].get('Retry-After')}")
        print(f"Another request 1.2s later: {near[0]} Retry-After={near[2].get('Retry-After')}")
        print("Expected: 5 accepted, then 429; no new request is admitted merely because a wall-clock minute changed.")

    if args.scenario in ("all", "concurrency"):
        counts = await scenario_concurrency(args.nodes)
        print("\n[4] Concurrent race / atomicity")
        print(f"500 simultaneous requests -> {counts[200]} OK, {counts[429]} rejected")
        print("Expected for 100 RPM: exactly 100 OK and 400 rejected.")

if __name__ == "__main__":
    asyncio.run(main())
