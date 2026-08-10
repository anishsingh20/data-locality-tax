# The Data Locality Tax — Measured Retrieval Latency Across Regions

**A reproducible harness measuring how much RAG retrieval latency you pay when a DigitalOcean Managed PostgreSQL (pgvector) cluster sits in a different region from the Droplet issuing queries.**

- **Run date:** August 10, 2026, ~10:04–10:05 UTC (one suite window)
- **Client:** DigitalOcean Droplet `locality-tax-bench-nyc3` (`s-2vcpu-4gb`, Ubuntu 24.04), **NYC3**, public IP `45.55.60.167`
- **Arm A:** Managed PostgreSQL 16 + pgvector in **NYC3**, queried over the **private hostname / same-DC VPC**
- **Arm B:** Identical Managed PostgreSQL 16 + pgvector in **SFO3**
  - **B1:** public hostname over the internet
  - **B2:** private hostname over **VPC peering** `locality-tax-nyc3-sfo3`
- **Corpus:** 100,000 synthetic 768-d vectors, HNSW (`vector_cosine_ops`), identical load script on both clusters
- **Trials:** 75 measured + 10 warmup per cell; cold-connection first call recorded separately
- **Not run in this window:** Arm B3 (NYC→SGP) hit the account database-cluster limit; Arm C (third-party SaaS) had no credentials available

This repository is the evidence base for the companion article *"The Data Locality Tax: What a Wrong-Region Vector DB Costs Your RAG Pipeline"* (DigitalOcean Community draft).

Tags on all provisioned resources: `created-by-anish-for-testing-purposes`, `data-locality-tax`.

---

## Headline measured table

Physics floors (great-circle / fiber, ~200,000 km/s): same-DC &lt; 0.01 ms; NYC–SFO ≥ **41.3 ms**. Real paths must sit at or above those floors.

| Arm | Path | TCP RTT probe p50 | Retrieval p50 (k=5) | Retrieval p95 (k=5) | Retrieval p50 (k=100) | Cold-connection first call (k=5) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| A | Same DC, VPC (NYC3→NYC3 private) | **2.43 ms** | **1.90 ms** | 3.51 ms | 11.37 ms | 111.34 ms |
| B1 | NYC3→SFO3, public | **68.63 ms** | **66.97 ms** | 69.55 ms | 70.11 ms | 717.91 ms |
| B2 | NYC3→SFO3, peered VPC | **67.73 ms** | **69.90 ms** | 70.57 ms | 75.44 ms | 668.87 ms |
| B3 | NYC→SGP, public | *not run — cluster limit* | | | | |
| C | Third-party SaaS | *not run — no SaaS creds* | | | | |

### What the numbers say

1. **Same-DC VPC is the floor.** Arm A TCP probe p50 is 2.43 ms; pooled retrieval at k=5 is 1.90 ms. That is the rung every other path should be priced against.
2. **Continental misplacement pays ~35× on pooled k=5.** B1 pooled retrieval p50 (66.97 ms) vs A (1.90 ms) is a ~35× tax on the steady-state path — and the TCP probe alone (68.63 ms) already sits ~27 ms above the 41.3 ms physics floor, which is expected route overhead.
3. **Peering does not erase geography.** B2 (peered private hostname) is within a few milliseconds of B1 on every column. Privacy and egress accounting change; the speed-of-light bill does not.
4. **Cold connections multiply the tax.** B1 cold first call is 717.91 ms vs 66.97 ms pooled — roughly an order of magnitude — matching the article’s TCP+TLS handshake arithmetic on a cross-region RTT.
5. **k=100 vs k=5 separates more on the local arm** (11.37 vs 1.90 ms) than on the distant arms (70 vs 67 ms), where the network floor dominates the payload effect in this corpus size.

---

## Repository layout

```
harness/
  locality_bench.py   # TCP probe + pgvector modes (from the article)
  load_corpus.sql     # 100k × 768-d synthetic vectors + HNSW index
results/
  a_*.json, b1_*.json, b2_*.json
  summary_table.json
  run_metadata.json   # infra IDs, regions, disclosures (no passwords)
requirements.txt
```

## Reproduce

From a Droplet in the fixed region (NYC recommended):

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# apt install postgresql-client   # for loading

psql "$DSN_ARM_A" -f harness/load_corpus.sql
psql "$DSN_ARM_B" -f harness/load_corpus.sql

python3 harness/locality_bench.py --mode tcp --host <private-or-public-host> --port 25060 --out results/a_tcp.json
python3 harness/locality_bench.py --mode pgvector --dsn "$DSN_ARM_A" --k 5 --out results/a_k5.json
```

See the article runbook for trusted sources, VPC peering, and teardown.

## Honest disclosures

- One time window only (article recommends a second window on another day for production claims).
- Synthetic random vectors measure the **path**, not recall quality.
- Smallest DB plan (`db-s-1vcpu-1gb`); ANN time is not the comparison target because both arms share identical index parameters.
- B3 and Arm C were not executed; cells are left blank rather than estimated.
