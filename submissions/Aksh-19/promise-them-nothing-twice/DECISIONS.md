Core design I chose

The important conflict resolution is explicit:

CTO wins on quota enforcement. Northwind does not get a hidden bypass.

Northwind's contract says 300 RPM, while its batch sends 800–1200 RPM, so the service deliberately returns 429 above 300 RPM. The support memo is addressed as a commercial/quota renegotiation problem, rather than violating the signed SLA.

For the limiter I used an exact Redis sliding-window log, rather than token bucket/fixed window

Harness demonstrations

The harness specifically tests:

Scenario	Expected
101 requests for 100-RPM customer	100 × 200, 1 × 429
Another 100-RPM customer simultaneously	Unaffected
500 concurrent requests across 3 nodes	100 × 200, 400 × 429
Rolling 60-second boundary	No fixed-window reset exploit
Requests distributed among 3 processes	One shared customer budget

I also ran Python compilation checks on the generated application and harness successfully.
