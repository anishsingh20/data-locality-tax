# The Data Locality Tax: Measured Retrieval Latency Across DigitalOcean Regions

**A reproducible measurement of how much RAG retrieval latency you pay when a DigitalOcean Managed PostgreSQL (pgvector) cluster sits in a different region from the Droplet issuing the query.**

- **Run date:** August 10, 2026, 10:04:37–10:05:45 UTC (one time window)
- **Client:** DigitalOcean Droplet (`s-2vcpu-4gb`, Ubuntu 24.04), **NYC3**
- **Stores:** Managed PostgreSQL 16 + pgvector, plan `db-s-1vcpu-1gb`, identical 100,000 × 768-d HNSW corpora in **NYC3** (Arm A) and **SFO3** (Arms B1/B2)
- **Volume:** 12 measured cells, 75 trials after 10 warmups per cell, plus a cold-connection first call on every pgvector cell
- **Everything in this repository is what actually ran:** the harness, the load SQL, the raw per-cell JSON, the plotting code, and the charts it produced.

This repository is the evidence base for a companion article, *"The Data Locality Tax: What a Wrong-Region Vector DB Costs Your RAG Pipeline"* (DigitalOcean Community, forthcoming). Related study (different question, same measurement discipline): [serverless-inference-tail-latency-study](https://github.com/anishsingh20/serverless-inference-tail-latency-study).

---

## Abstract

Retrieval optimization guides spend their pages on chunking, reranking, and HNSW knobs. This study measures the part those guides usually skip: the round-trip between the machine that embeds and generates, and the database that holds the vectors.

The protocol held the corpus, the index, the query, and the client fixed, then changed only the path. A DigitalOcean Droplet in NYC3 queried Managed PostgreSQL 16 with pgvector in three placements: the same datacenter over a VPC private hostname (Arm A), an identical cluster in SFO3 over the public hostname (Arm B1), and that same SFO3 cluster over VPC peering (Arm B2). Each cell recorded a bare TCP connect probe (no SQL), a pooled vector search, and a cold first call that times TCP, TLS, and the first query together.

The headline result is a **placement tax measured on live infrastructure**: pooled k=5 retrieval was **1.90 ms** in the same datacenter and **66.97 ms** New York to San Francisco public, a **35×** gap. The TCP probe on the distant arm (68.63 ms) sat next to the full search, which means the index walk was not the bill. VPC peering (69.90 ms) did not beat the public path in a way that erases geography. A cold connection on B1 cost **717.91 ms**, roughly ten times the pooled search. Eight sequential hops at the measured B1 median sum to **536 ms** of geography before a token generates.

The conclusion is architectural, not a database bake-off: **co-locate the vector store with the GPU first, then tune the index**. Index parameters recover milliseconds from the one segment placement cannot touch. Placement recovers tens to hundreds of milliseconds per call from the segments tuning cannot touch.

---

## Key findings

### 1. Same query, 35× the wait

| Arm | Path | TCP RTT p50 | Retrieval p50 (k=5) | Retrieval p95 (k=5) | Retrieval p50 (k=100) | Cold first call (k=5) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| A | Same DC, VPC (NYC3 private) | **2.43 ms** | **1.90 ms** | 3.51 ms | 11.37 ms | 111.34 ms |
| B1 | NYC3 → SFO3, public | **68.63 ms** | **66.97 ms** | 69.55 ms | 70.11 ms | 717.91 ms |
| B2 | NYC3 → SFO3, peered VPC | **67.73 ms** | **69.90 ms** | 70.57 ms | 75.44 ms | 668.87 ms |
| B3 | NYC → SGP, public | *not run* | | | | |
| C | Third-party SaaS | *not run* | | | | |

![Pooled retrieval p50 at k=5](figures/fig-01-retrieval-p50-k5.png)

*Same query, same index, same corpus. The only variable is the path. Arm A is the floor this study exists to establish. B1 / A = 35× on pooled k=5. Lower is better. Source: `results/a_k5.json`, `results/b1_k5.json`, `results/b2_k5.json`; 75 trials after 10 warmups.*

![Study design](figures/fig-00-study-design.png)

*One NYC3 client, three paths, identical 100k × 768-d HNSW corpora. Arms B3 and C were not executed and are omitted rather than estimated.*

### 2. On the long path, retrieval tracks TCP

A bare TCP connect to SFO3, with no credentials and no SQL, already took 68.63 ms at p50. The full pooled search (66.97 ms) sat on top of that number. Once the buildings are a continent apart, most of the wait is the trip, not HNSW.

![TCP connect vs pooled retrieval vs cold first call](figures/fig-02-tcp-retrieval-cold.png)

*Blue: TCP connect to port 25060, no database work. Forest: pooled k=5 search on a reused connection. Brick: cold first call (connect + TLS + first query). Distant retrieval does not beat the TCP probe. Cold first calls land around 670–718 ms. Source: matching `*_tcp.json` and `*_k5.json` files.*

### 3. Peering does not erase geography

Arm B2 used the SFO3 private hostname over an active VPC peering (`locality-tax-nyc3-sfo3`). Pooled k=5 was 69.90 ms, within a few milliseconds of the public path. Peering changes privacy and how inter-datacenter bytes are billed. It does not move New York closer to San Francisco.

### 4. Physics set the floor; the run landed above it

Light in fiber cannot beat about 41.3 ms New York to San Francisco (great-circle distance at ~200,000 km/s, doubled). Measured TCP p50 was 68.63 ms public and 67.73 ms peered, about 27 ms of routing overhead above that floor. Arm A's TCP probe was 2.43 ms. Nothing landed below its floor.

![Physics floor vs measured TCP](figures/fig-04-floor-vs-measured-tcp.png)

*Grey: derived fiber floor. Blue: measured TCP connect p50. Real fiber does not follow great circles, so every honest path must sit at or above its floor. This run did. Source: TCP probes plus the haversine floors documented in the companion article.*

### 5. Extra neighbors, cold connections, and sequential hops

Returning 100 neighbors instead of 5 slowed the local arm from 1.90 ms to 11.37 ms, because extra payload is visible when the network is already fast. On B1, k=100 was 70.11 ms versus 66.97 ms at k=5: a rounding error next to the 67 ms trip.

A cold connection pays TCP plus TLS before the query runs. Locally that first call was 111.34 ms. Across the continent it was 717.91 ms public and 668.87 ms peered, roughly ten times the pooled search.

Sequential agent hops add. Eight hops at the measured B1 median sum to 536 ms of geography before a token generates. The same eight hops on Arm A stay under 16 ms. Distant p50 and p95 sat close together (66.97 vs 69.55 ms on B1): the path is consistently slow, not occasionally noisy.

![top-k 5 / 20 / 100](figures/fig-03-topk-payload.png)

*Payload size versus distance. Extra neighbors cost real time on Arm A and almost vanish behind the continental trip on B1/B2. n=75 per cell.*

![Measured tax compounded across hops](figures/fig-05-compounding-measured.png)

*Arithmetic on the measured pooled k=5 p50, not a second experiment. Sequential hops add; they do not overlap. Eight hops on B1 = 536 ms before any token generates.*

![p50 vs p95 at k=5](figures/fig-06-p50-vs-p95.png)

*Median versus tail. B1 p95 is 2.6 ms above p50. That is placement, not a noisy index.*

---

## Methodology

**Fixed variables**

- One Droplet in NYC3 running `harness/locality_bench.py`
- One corpus: 100,000 synthetic 768-d vectors, HNSW (`vector_cosine_ops`), identical `harness/load_corpus.sql` on both clusters
- One query generator (seed `7` inside the harness)
- 75 measured trials + 10 discarded warmup per cell
- top-k of 5, 20, and 100

**The three arms**

1. **Arm A.** Managed PostgreSQL 16 + pgvector in NYC3, queried on the private hostname over the same-DC VPC.
2. **Arm B1.** Identical engine, plan, and index in SFO3, queried on the public hostname.
3. **Arm B2.** The same SFO3 cluster, queried on the private hostname over VPC peering between `default-nyc3` and `default-sfo3`.

**What each cell records**

- **TCP probe:** `socket.create_connection` to port 25060. No credentials, no SQL. Approximates one network round trip.
- **Pooled retrieval:** one `psycopg` connection reused; `ORDER BY embedding <=> query LIMIT k`.
- **Cold first call:** connect + TLS + first query, timed together, stored separately so it does not contaminate the pooled average.

**Infrastructure (destroyed after JSON was copied off the Droplet)**

| Resource | Name | Region |
| --- | --- | --- |
| Droplet | `locality-tax-bench-nyc3` (`s-2vcpu-4gb`) | nyc3 |
| PostgreSQL 16 + pgvector | `locality-tax-pg-nyc3` (`db-s-1vcpu-1gb`) | nyc3 |
| PostgreSQL 16 + pgvector | `locality-tax-pg-sfo3` (`db-s-1vcpu-1gb`) | sfo3 |
| VPC peering | `locality-tax-nyc3-sfo3` | nyc3 ↔ sfo3 |

Tags at create time: `created-by-anish-for-testing-purposes`, `data-locality-tax`. IDs and timestamps: `results/run_metadata.json`.

**Known limitations, stated plainly**

- One time window. These numbers describe what this path did during that hour, not a daily average.
- Synthetic random vectors measure the **path**, not recall. Do not read this as an ANN quality comparison.
- Smallest database plan (`db-s-1vcpu-1gb`). ANN time is not the comparison target; both arms shared index parameters so that time would cancel out of the delta.
- Arms B3 (NYC → Singapore) and C (third-party SaaS) were not executed. Those cells stay blank rather than estimated.
- If prose and JSON disagree, trust `results/*.json`.

Expanded protocol notes: [METHODS.md](METHODS.md).

---

## Repository layout

```
harness/
  locality_bench.py      TCP probe + pgvector modes. This is the script that ran.
  load_corpus.sql        100k × 768-d synthetic vectors + HNSW index.
analysis/
  plot_results.py        Recomputes every chart from the raw JSON.
results/
  a_*.json, b1_*.json, b2_*.json
                         Untouched per-cell output from the August 10, 2026 run.
  summary_table.json
  run_metadata.json      Infra IDs, regions, disclosures (no passwords).
figures/
  fig-00 … fig-06.png    Charts generated by analysis/plot_results.py.
METHODS.md               Protocol in long form.
```

## Reproducing

Against the archived data (no account needed):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 analysis/plot_results.py
```

This regenerates every chart in `figures/` from `results/*.json`.

Against live infrastructure (your own numbers, which are the ones that matter):

```bash
# 1. Create a Droplet in a fixed region (NYC recommended) and two Managed
#    PostgreSQL clusters: one in that region, one in a distant region.
#    https://docs.digitalocean.com/products/databases/postgresql/
#    https://docs.digitalocean.com/products/networking/vpc/
# 2. Add the Droplet to each cluster's trusted sources.
# 3. Load the identical corpus:
psql "$DSN_ARM_A" -f harness/load_corpus.sql
psql "$DSN_ARM_B" -f harness/load_corpus.sql

# 4. TCP probe, then retrieval cells:
python3 harness/locality_bench.py --mode tcp --host <host> --port 25060 --out results/a_tcp.json
python3 harness/locality_bench.py --mode pgvector --dsn "$DSN_ARM_A" --k 5 --out results/a_k5.json
```

Run it once during business hours and once overnight. This study only covered one window, and the second window is the part of the protocol it did not execute. If your results differ from anything reported here, that difference is the finding.

---

## Citation

If you use this data or method, please cite:

```
Anish Singh Walia (2026). The Data Locality Tax: Measured Retrieval Latency
Across DigitalOcean Regions.
https://github.com/anishsingh20/data-locality-tax
```

## License

MIT. See [LICENSE](LICENSE).
