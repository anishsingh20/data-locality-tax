# Methods

Canonical write-up of this study: [README.md](README.md). This file is the protocol in long form. If prose and JSON disagree, trust `results/*.json`.

## Question

How much extra wait does a RAG pipeline pay, per retrieval call, when the vector store is a continent away from the compute that embeds and generates, holding the corpus and the index fixed?

## What ran

| Piece | Value |
| --- | --- |
| Window | 2026-08-10, 10:04:37–10:05:45 UTC (one suite) |
| Client | Droplet `locality-tax-bench-nyc3`, `s-2vcpu-4gb`, Ubuntu 24.04, region **NYC3** |
| Arm A | Managed PostgreSQL 16 + pgvector, `db-s-1vcpu-1gb`, **NYC3**, private hostname over same-DC VPC |
| Arm B | Identical engine, plan, and load script, **SFO3** |
| B1 path | SFO3 public hostname |
| B2 path | SFO3 private hostname over VPC peering `locality-tax-nyc3-sfo3` |
| Corpus | 100,000 synthetic 768-d vectors, HNSW (`vector_cosine_ops`), identical SQL on both clusters |
| Trials | 75 measured + 10 discarded warmup per cell |
| k values | 5, 20, 100 |
| Harness | `harness/locality_bench.py` |

Resource tags used at create time: `created-by-anish-for-testing-purposes`, `data-locality-tax`. Clusters, Droplet, and peering were destroyed after JSON was copied off the Droplet.

## What stayed fixed

- One client Droplet in one region
- One corpus size, dimensionality, index type, and similarity operator
- One query generator (seed `7` inside the harness)
- Same trial count and warmup policy on every cell
- Same top-k values on every arm

## What changed

Only the path:

1. Same datacenter, private VPC hostname
2. Cross-region public hostname
3. Cross-region peered-VPC hostname

## What each cell reports

- **TCP probe:** `socket.create_connection` to port 25060. No credentials, no SQL. Approximates one network round trip.
- **Pooled retrieval:** one `psycopg` connection reused; `ORDER BY embedding <=> query LIMIT k`.
- **Cold first call:** connect + TLS + first query, timed together, recorded separately so it does not contaminate the pooled average.

## What this study does not claim

- It does not measure recall. Vectors are random. The path is the variable.
- It does not compare ANN engines. Both clusters used pgvector HNSW with the same parameters.
- It is one time window. A production paper would repeat on another day.
- Arms B3 (NYC to Singapore) and C (third-party SaaS) were not executed. Those cells stay blank.

## How to redraw the figures

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 analysis/plot_results.py
```

Figures are written to `figures/fig-00` through `fig-06`. They read JSON; they do not invent numbers.
