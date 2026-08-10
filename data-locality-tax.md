---
title: "The Data Locality Tax: What a Wrong-Region Vector DB Costs Your RAG Pipeline"
description: "Teams tune HNSW parameters while their vector database sits a continent away from their GPU, paying a physics tax on every retrieval no index setting can recover. This piece derives the tax from first principles, shows how it compounds in multi-hop agentic RAG, and ships a harness to measure your own path on DigitalOcean infrastructure."
conclusion_cta: null
right_side_nav_cta: null
draft: true
header_url: null
tutorial_type: conceptual-article
state: draft
language: en
published_at: null
last_validated_at: null
follow_up_questions_enabled_at: null
comments_locked_at: null
raw_html_allowed_in_markdown_at: null
featured_at: null
authors:
  - slug: anish
editors: []
translators: []
primary_tag: ai-ml
tags:
  - inference
  - rag
  - vector-databases
  - networking
  - ai-ml
teams:
  - do-internal
origins:
  - do-internal
---

*Conceptual Article. Products: [GPU Droplets](https://www.digitalocean.com/products/gpu-droplets), [DigitalOcean Vector Databases](https://docs.digitalocean.com/products/vector-databases/) (Weaviate, OpenSearch, and PostgreSQL with pgvector), and [VPC networking](https://docs.digitalocean.com/products/networking/vpc/). Every external claim was checked against a primary source on August 6, 2026. The physics floors in this piece are my own derivations from the speed of light in fiber, shown with their arithmetic. The measured table was filled from a live harness run on DigitalOcean infrastructure on August 10, 2026 (NYC3 Droplet → NYC3 and SFO3 Managed PostgreSQL with pgvector; raw JSON in the companion repo). Arms B3 (NYC→SGP) and C (third-party SaaS) were not executed in this window and stay blank by design.*

> **Where the numbers in this piece come from.** Two sources, kept strictly apart. The round-trip floors (5.5 ms, 41.3 ms, 62.0 ms, 153.3 ms and the rest) are derived from great-circle distance divided by the propagation speed of light in optical fiber, roughly 200,000 km per second. They are lower bounds set by physics, not measurements, and real paths are slower because fiber does not follow great circles. The measured columns come from the published harness run on August 10, 2026 against live DigitalOcean Droplets and Managed PostgreSQL (pgvector); raw per-cell JSON is in [anishsingh20/data-locality-tax](https://github.com/anishsingh20/data-locality-tax).

Your RAG pipeline's latency conversation is probably stuck on the wrong question. Teams benchmark GPUs, tune HNSW parameters, argue about `ef_search` values, and shave single-digit milliseconds off approximate nearest neighbor search. Meanwhile the vector database holding their embeddings sits in a different region from the GPU running their model, and every single retrieval call pays a round-trip tax set by the distance between two buildings. No index parameter recovers that time. The speed of light does not have a config flag.

Retrieval optimization guides cover chunking, reranking, index tuning, and embedding model choice in depth. Cross-region placement, when mentioned at all, appears as one unmeasured bullet point. This piece does three things about that gap: derives the floor of the tax from physics you check with a calculator, shows how the tax compounds in multi-hop agentic RAG where a per-call cost invisible once becomes seconds of pure geography per task, and ships a harness to measure your own path on [DigitalOcean GPU Droplets](https://www.digitalocean.com/products/gpu-droplets) and [Vector Databases](https://docs.digitalocean.com/products/vector-databases/) so the argument ends with your numbers, not mine.

## Key Takeaways

- **Retrieval latency splits into a part index tuning controls and a part only placement controls.** Server-side ANN search responds to HNSW parameters. Network transit responds to nothing except moving the endpoints closer together. Most optimization effort goes to the first part. The second part is often larger.
- **The floor of the tax is checkable arithmetic, and this piece shows the work.** A round trip between New York and San Francisco is at least 41.3 ms in fiber, New York to Frankfurt at least 62.0 ms, New York to Singapore at least 153.3 ms, from great-circle distance at roughly 200,000 km per second. These are lower bounds. Real routes are slower. Inside one datacenter, the same floor is below one millisecond.
- **Retrieval blocks time to first token directly.** The model cannot begin prefill until the retrieved context arrives, so the user feels every millisecond of the retrieval path before the first token, on top of everything the companion latency pieces already measure about serving.
- **The tax compounds in multi-hop agentic RAG, and that is where the story stops being about milliseconds.** One 62 ms round trip in a single-retrieval chat with a 2-second generation is a 3.1 percent overhead, real but survivable. Eight sequential retrieval hops in an agent task pay 496 ms of pure geography before a single token generates. Same tax, different workload, opposite verdict.
- **A cold connection multiplies the tax before the query even sends.** TCP setup costs one round trip and TLS adds one more on TLS 1.3, two more on TLS 1.2. On a 62 ms cross-region path, a misconfigured client without connection pooling pays 124 to 186 ms of pure handshake per connection, and pays it repeatedly.
- **The measured table is filled for Arms A, B1, and B2 from a live August 10, 2026 run.** Same-DC VPC retrieval p50 at k=5 was 1.90 ms; NYC3→SFO3 public was 66.97 ms (~35×); peered VPC was 69.90 ms — geography, not peering, set the bill. Arms B3 and C remain blank (cluster-limit and no SaaS credentials). Re-run the harness for your own path: [anishsingh20/data-locality-tax](https://github.com/anishsingh20/data-locality-tax).

## Anatomy of a retrieval round trip

Before measuring anything, decompose what one vector search call consists of, because the decomposition is the argument.

A single retrieval call, from the moment your application decides to search until results are usable, spends time in five places. Connection setup, if no pooled connection exists: TCP and TLS handshakes, paid per new connection. Query serialization: encoding the query vector and parameters, microseconds, ignorable. Network transit, outbound: your query crossing the wire to the database. Server-side ANN search: the index walk itself, the part every tuning guide optimizes. Network transit, return: the result payload crossing back, and its cost is payload size times available bandwidth plus the same propagation delay, which is why top-k 100 with full documents behaves differently across regions than top-k 5 with IDs.

Sort those five by what controls them. ANN search time responds to index parameters, hardware, and corpus size. Everything else responds to placement and connection discipline. That is the core distinction this piece exists to make: **index tuning optimizes the component placement cannot touch, and placement determines the components tuning cannot touch.** A team benchmarking `ef_search` values while their database sits across a continent is polishing the fast part of a slow path.

![Decomposition of one retrieval call into five segments on a timeline: connection setup, query serialization, outbound transit, server-side ANN search, and return transit, with the placement-dependent segments marked in brick red and the tuning-dependent segment marked in teal.](diagram-dl-1-anatomy.png)
*Five segments, two owners. Tuning owns the teal segment. Geography owns the red ones, and no index parameter reaches them. Source: author's decomposition of one retrieval call; the retrieval-blocks-prefill behavior follows the pipeline stages in [DigitalOcean's end-to-end RAG tutorial](https://www.digitalocean.com/community/tutorials/end-to-end-rag-pipeline) and the TTFT framing in [p50 vs p99 Latency](https://www.digitalocean.com/community/tutorials/p50-vs-p99-latency-llm-inference).*

The reason this lands on user experience directly, rather than hiding in a dashboard: retrieval blocks prefill. In a standard RAG flow, the model cannot begin processing the prompt until the retrieved context is in hand, so every millisecond of the retrieval path adds to time to first token, the metric the user stares at before anything appears. The companion piece on [p50 versus p99 latency](https://www.digitalocean.com/community/tutorials/p50-vs-p99-latency-llm-inference) covers why TTFT is the number interactive users feel. This piece adds the network hop that sits in front of everything that piece measures. For background on the pipeline stages themselves, the [end-to-end RAG pipeline tutorial](https://www.digitalocean.com/community/tutorials/end-to-end-rag-pipeline) covers the build. This piece adds the dimension the build guides skip: where each stage physically runs.

## The floor of the tax, derived rather than asserted

Light in optical fiber propagates at roughly 200,000 kilometers per second, about two-thirds of its speed in vacuum, because of the fiber's refractive index. That single number turns distance into a latency floor no engineering removes. Divide the great-circle distance between two cities by 200,000 km/s, double it for the round trip, and you have the minimum possible round-trip time between them, before queueing, before routing detours, before the server does any work at all.

The following table is my own derivation using that method. I computed each great-circle distance with the haversine formula and the coordinates of each metro area. These are floors, not estimates of real performance: production fiber routes do not follow great circles, so real round trips exceed every number here.

| Path | Great-circle distance | Round-trip floor in fiber |
| --- | --- | --- |
| Inside one datacenter | under 1 km | under 0.01 ms |
| New York to Toronto | 550 km | 5.5 ms |
| New York to San Francisco | 4,129 km | 41.3 ms |
| New York to London | 5,570 km | 55.7 ms |
| New York to Amsterdam | 5,863 km | 58.6 ms |
| New York to Frankfurt | 6,203 km | 62.0 ms |
| New York to Bangalore | 13,368 km | 133.7 ms |
| New York to Singapore | 15,332 km | 153.3 ms |
| New York to Sydney | 15,989 km | 159.9 ms |

Read the first row against the rest, because the first row is the whole architectural argument. A GPU Droplet and a managed vector database in the same DigitalOcean datacenter, communicating over a [VPC network](https://docs.digitalocean.com/products/networking/vpc/), have a propagation floor three orders of magnitude below any cross-region pairing. DigitalOcean's own VPC documentation confirms the relevant properties: VPC networks are scoped to a single datacenter region, traffic within a VPC is free and private, and connecting VPCs across datacenters requires [VPC peering](https://docs.digitalocean.com/products/networking/vpc/details/availability/), which is available between all datacenters except BLR1 and billed at $0.01 per GiB for inter-datacenter traffic. The physics and the pricing point the same direction.

![Bar chart of round-trip latency floors derived from the speed of light in fiber, from under 0.01 ms inside one datacenter through 5.5 ms New York to Toronto, 41.3 ms to San Francisco, 62.0 ms to Frankfurt, and 153.3 ms to Singapore, with a callout marking every bar as a lower bound real routes exceed.](diagram-dl-2-floors.png)
*Derived, not measured. Real paths are slower than every bar shown, because fiber does not follow great circles. The first bar is the argument. Source: author's derivation, haversine great-circle distance divided by ~200,000 km/s propagation in fiber, doubled for the round trip; method and full table shown in this article's floor section.*

## The experiment: one query, three placements

This is the section the harness exists for. The design below is fully specified; the harness and raw results live in [anishsingh20/data-locality-tax](https://github.com/anishsingh20/data-locality-tax). The August 10, 2026 run filled Arms A, B1, and B2 from a NYC3 Droplet against Managed PostgreSQL 16 + pgvector in NYC3 and SFO3 (100,000 synthetic 768-d vectors, HNSW cosine, 75 trials after 10 warmups per cell). Arms B3 and C were not executed in that window. This mirrors the approach the [continuous batching piece](https://www.digitalocean.com/community/tutorials/continuous-vs-static-batching) took: disclose the method, run the paid measurement, and let the numbers speak.

### Fixed variables

One GPU Droplet in a fixed region, NYC recommended, running the embedding model and the LLM. One corpus, roughly 1 million vectors at a realistic dimensionality such as 768 or 1,024, loaded identically into every store under test. Identical index type and parameters across arms wherever the engine allows, so server-side ANN time cancels out of the comparison and the delta isolates the path.

### The three arms

**Arm A, same datacenter over VPC.** A [DigitalOcean Vector Database](https://docs.digitalocean.com/products/vector-databases/) in the same datacenter as the GPU Droplet, attached to the same VPC, queried over the private network. PostgreSQL with pgvector is the safest engine choice because Managed PostgreSQL is broadly available across regions. OpenSearch is the alternative for hybrid search workloads, and [Managed Weaviate](https://docs.digitalocean.com/products/vector-databases/weaviate/) entered public preview on July 1, 2026, per the Vector Databases release notes, so check the [availability page](https://docs.digitalocean.com/products/vector-databases/details/availability/) for your region pair before provisioning it as an arm. The [choosing-an-engine guide](https://docs.digitalocean.com/products/vector-databases/concepts/choosing-an-engine/) covers the selection tradeoffs this piece does not.

**Arm B, distant DigitalOcean region.** The identical database, same engine, same plan, same index, provisioned in a distant region: NYC to SFO for the continental case, NYC to SGP for the intercontinental case if budget allows both. Queried over the public endpoint, and additionally over inter-datacenter VPC peering where configured, with both paths recorded separately.

**Arm C, third-party managed vector store.** A SaaS vector database, region-matched as closely as its plan tiers allow. One framing rule, stated now so the results section inherits it: this arm does not exist to name and shame any vendor for physics it does not control. It exists because many teams default to a SaaS vector store without ever checking which region their cluster landed in, and arm C measures what that unexamined default costs. Disclose the region-matching attempt and the vendor's stated region in the results. The target is the decision pattern, not the vendor.

### What gets measured

Per arm, per configuration: at least 75 requests per cell after discarded warmups, across two time windows, reporting p50, p95, and p99, following the measurement standards from [Metrics that Matter with Serverless Inference](https://www.digitalocean.com/community/tutorials/metrics-that-matter-serverless-inference) and the companion consistency work. Each cell runs at top-k values of 5, 20, and 100 to expose the payload-size times distance interaction, and each cell records cold-connection and pooled-connection timings separately, because the pooling confounder deserves its own column rather than contaminating the average. The harness also runs a bare TCP connect probe per arm, which approximates one network round trip with no database work at all, giving you the measured path floor to place next to the derived physics floor.

![Experiment design diagram: one GPU Droplet in NYC holding the embedding model and LLM, querying three arms, a same-datacenter vector database over VPC, the same database in a distant region, and a third-party managed store, all loaded with the identical corpus and index parameters, each arm reporting latency distributions plus a bare TCP round-trip probe.](diagram-dl-3-experiment.png)
*Same corpus, same index, same query. The only variable is the path, which is the point. Source: this article's experiment design; arm definitions per [DigitalOcean Vector Databases](https://docs.digitalocean.com/products/vector-databases/) and [VPC documentation](https://docs.digitalocean.com/products/networking/vpc/details/features/); trial counts per [Metrics that Matter with Serverless Inference](https://www.digitalocean.com/community/tutorials/metrics-that-matter-serverless-inference).*

## Results: the tax, itemized

### The measured table (August 10, 2026 run)

Client: Droplet `locality-tax-bench-nyc3` (`s-2vcpu-4gb`, Ubuntu 24.04) in **NYC3**. Stores: Managed PostgreSQL 16 + pgvector, plan `db-s-1vcpu-1gb`, identical 100k × 768-d HNSW corpora. Window: 10:04–10:05 UTC. Full JSON: [anishsingh20/data-locality-tax](https://github.com/anishsingh20/data-locality-tax).

| Arm | Path | TCP RTT probe p50 | Retrieval p50 (k=5) | Retrieval p95 (k=5) | Retrieval p50 (k=100) | Cold-connection first call |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| A | Same DC, VPC (NYC3 private) | 2.43 ms | 1.90 ms | 3.51 ms | 11.37 ms | 111.34 ms |
| B1 | NYC3 to SFO3, public | 68.63 ms | 66.97 ms | 69.55 ms | 70.11 ms | 717.91 ms |
| B2 | NYC3 to SFO3, peered VPC | 67.73 ms | 69.90 ms | 70.57 ms | 75.44 ms | 668.87 ms |
| B3 | NYC to SGP, public | *not run — account cluster limit* | | | | |
| C | Third-party SaaS, region as disclosed | *not run — no SaaS credentials in this window* | | | | |

Physics already guaranteed the ordering: arm A's TCP probe under a few milliseconds, B1 and B2 above the 41.3 ms NYC–SFO floor. The run filled the gaps: real NYC–SFO TCP p50 sat ~27 ms above that floor; pooled retrieval on the distant arms tracked the TCP probe rather than ANN time; cold first calls on B1/B2 were roughly 10× the pooled path; and peered VPC (B2) did not beat public (B1) in a way that erases geography. The k=100 vs k=5 separation was larger on arm A (11.37 vs 1.90 ms) than on B1 (70.11 vs 66.97 ms), where the network floor dominates.

### The compounding table, which is arithmetic and therefore already fillable

Single-shot RAG performs one retrieval per user query. Agentic RAG performs several, sequentially, because each hop's result decides the next hop's query: retrieve, reason, retrieve again, rerank, fetch neighbors, verify. Five to ten sequential retrievals per task is an ordinary agentic pattern. Sequential means the taxes sum.

| Per-call tax | 1 hop | 5 hops | 8 hops | 10 hops |
| --- | --- | --- | --- | --- |
| ~1 ms (same DC, expected order) | 1 ms | 5 ms | 8 ms | 10 ms |
| 41.3 ms (NYC-SFO floor) | 41 ms | 207 ms | 330 ms | 413 ms |
| 62.0 ms (NYC-FRA floor) | 62 ms | 310 ms | 496 ms | 620 ms |
| 153.3 ms (NYC-SGP floor) | 153 ms | 767 ms | 1,226 ms | 1,533 ms |

These are floors multiplied by hop counts, pure arithmetic on the derived numbers, and real totals sit above every cell. The middle rows are the story: a continental misplacement costs a third to half a second of pure geography per 8-hop agent task, and an intercontinental one costs more than a second, before any query executes, before any token generates, on every single task, forever, until someone moves the data.

![Compounding chart showing total geography tax versus number of sequential retrieval hops, with four lines for same-datacenter, NYC to SFO, NYC to Frankfurt, and NYC to Singapore floors, the same-DC line staying flat near zero while the Singapore line passes one second at eight hops.](diagram-dl-4-compounding.png)
*The same per-call tax, multiplied by how agents actually retrieve. The flat line is what colocation buys. Source: author's arithmetic, the derived fiber floors from this article multiplied by hop counts; real totals sit above every line.*

### The proportionality check, which is where this piece refuses to overclaim

Put the tax next to generation time, because a latency number without its denominator is marketing. For a single-retrieval chat query with a 2-second generation, a 62 ms cross-region tax is 3.1 percent of the response time: real, measurable, and survivable, and if this describes your workload, index tuning and caching are better uses of your week than a migration. For an 8-hop agent task whose steps each generate briefly, the 496 ms summed tax is no longer a rounding error: against steps averaging 300 ms of generation each, geography adds roughly 17 percent to the task's critical path, and against shorter tool-selection steps it approaches parity with the compute itself. Both statements are arithmetic on the same derived tax. The workload, not the tax, decides the verdict, and any version of this piece claiming a 60 ms tax ruins every RAG application would deserve the correction it would get.

### The pooling confounder, which multiplies the tax for free

A cold connection pays TCP setup, one round trip, then TLS setup, one more round trip on TLS 1.3 and two more on TLS 1.2, before the query sends. This is protocol arithmetic, not measurement. On a same-datacenter path those handshakes cost single-digit milliseconds and nobody notices. On a 62 ms cross-region path, the identical handshakes cost 124 to 186 ms of pure setup, per connection, and a client misconfigured to open a fresh connection per request, which is a common default in serverless functions and quickly written scripts, pays the setup tax on every call and roughly triples the geography bill. Connection pooling is free and removes the entire multiplier, which makes it the single cheapest fix in this piece: it does not shrink the tax, it stops you paying it three times.

![Two-lane comparison of a pooled connection paying one round trip per query against a cold connection paying TCP plus TLS handshakes before each query, with the cross-region case showing 124 to 186 ms of setup ahead of the first byte of the query.](diagram-dl-5-pooling.png)
*Same path, same query, triple the bill. Pooling is the cheapest line item in this entire piece. Source: handshake round-trip counts per the TLS 1.3 specification ([RFC 8446](https://www.rfc-editor.org/rfc/rfc8446)) and TLS 1.2 ([RFC 5246](https://www.rfc-editor.org/rfc/rfc5246)), applied to this article's derived 62 ms NYC-Frankfurt floor.*

## The placement hierarchy

Generalize the arms into rungs, from floor to ceiling. Each rung's tax is the derived floor where physics sets it and a template entry where only measurement answers.

**Rung 1, same datacenter over private networking.** GPU Droplet and vector database in one DC, one VPC. Propagation floor under 0.01 ms, expected real-world round trips in the low single-digit milliseconds, intra-VPC traffic free per [DigitalOcean's VPC documentation](https://docs.digitalocean.com/products/networking/vpc/details/features/). This is the measured floor the harness establishes, and every other rung is priced relative to it.

**Rung 2, same region, different placement.** Same metro, public endpoint instead of VPC, or resources in sibling datacenters of one region. Floor under 1 ms, real cost dominated by routing rather than distance. Usually tolerable, usually also unnecessary, since rung 1 is available.

**Rung 3, cross-region, same provider.** The NYC-to-SFO and NYC-to-SGP arms: floors of 41.3 and 153.3 ms respectively, plus inter-datacenter VPC peering at $0.01 per GiB if you keep the path private. The tax is now larger than most well-tuned ANN searches, meaning the network dominates the retrieval call.

**Rung 4, cross-provider, third-party SaaS store.** Everything in rung 3 plus a region you may never have chosen deliberately, an internet path between providers, and the vendor's own load you cannot observe. Arm C measures what this rung actually costs. The recurring failure pattern is not choosing this rung, it is landing on it by default and never checking.

**Rung 5, flagged without full measurement: object-storage-backed retrieval.** Indexes served from object storage, the true cold-storage rung. One indicative measurement in the harness if feasible, disclosed as indicative only. The floor logic still applies, with storage latency stacked on top of it.

The architectural implication inverts the usual optimization order: **co-locate data with compute first, tune indexes second.** Index tuning recovers milliseconds from the one segment placement never touches. Placement recovers tens to hundreds of milliseconds per call from the segments tuning never touches. Do the big, boring, structural fix before the small, interesting, parameterized one.

![Placement hierarchy ladder with five rungs from same-datacenter VPC at the floor through same region, cross-region, third-party SaaS, and object-storage-backed retrieval, each rung annotated with its derived floor or a to-be-measured marker.](diagram-dl-6-hierarchy.png)
*Five rungs, priced by physics where physics answers and by the harness where only measurement does. Climb no higher than your workload can afford. Source: floors from this article's derivation; VPC scoping, free intra-VPC traffic, and $0.01/GiB inter-datacenter peering per [DigitalOcean VPC Features](https://docs.digitalocean.com/products/networking/vpc/details/features/) and [VPC Availability](https://docs.digitalocean.com/products/networking/vpc/details/availability/), verified August 6, 2026.*

## Decision framework: when locality matters and when it does not

**Locality is critical when** your workload is agentic or multi-hop RAG, since sequential hops multiply the tax. When you hold a strict TTFT budget, since retrieval blocks prefill and the tax lands entirely on the number users feel first. When query volume is high, since the tax times volume is also an egress and peering cost story at $0.01 per GiB across datacenters. And when your architecture reranks or fetches neighbors in sequential stages, which is multi-hop RAG wearing a different name.

**Locality is negotiable when** your flow performs one retrieval ahead of a long generation, where the proportionality check showed 3 percent overhead. When your pipeline is asynchronous or batch, where no person waits on any single call. And when the corpus must live in a specific region for compliance or residency reasons, in which case the decision is made for you and the remaining move is relocating compute toward the data or replicating the index into the compute region, whichever your update rate makes cheaper: a slowly changing corpus replicates well, a rapidly changing one usually pulls compute toward it instead.

**Practical guidance, three checks in order.** First, find out where your vector store actually runs, because many teams cannot answer this: for DigitalOcean managed engines the region is explicit at [cluster creation](https://docs.digitalocean.com/products/vector-databases/how-to/create/), and for a SaaS store the region hides in the cluster settings page most people last saw at signup. Second, match regions deliberately across GPU Droplet, vector database, and Knowledge Base if you use the managed RAG path: the [Knowledge Bases and MCP tutorial](https://www.digitalocean.com/community/tutorials/build-rag-agent-digitalocean-knowledge-bases-mcp) already carries region-placement guidance, precedent that placement is a live consideration in DO's own docs rather than an invention of this piece. Third, before provisioning experiment arms, confirm engine availability in your chosen pair on the [availability page](https://docs.digitalocean.com/products/vector-databases/details/availability/), since Weaviate is in public preview and its region list may trail PostgreSQL and OpenSearch. Engine selection itself is covered by the existing [vector database selection guide](https://www.digitalocean.com/community/conceptual-articles/how-to-choose-the-right-vector-database); this piece adds the placement dimension selection guides omit.

## Runbook: running this experiment on DigitalOcean

**DigitalOcean products you need.** One [GPU Droplet](https://www.digitalocean.com/products/gpu-droplets) in your fixed region if you want to measure from the machine that actually serves your model, and a plain CPU [Droplet](https://docs.digitalocean.com/products/droplets/) in the same datacenter works identically for the network measurement itself, since the harness exercises the path, not the GPU. Two [Vector Database clusters](https://docs.digitalocean.com/products/vector-databases/how-to/create/) with the PostgreSQL engine, one in the same datacenter as the Droplet for arm A and one in a distant region for arm B, smallest plan on both, since the corpus is synthetic and the index is small. The default [VPC](https://docs.digitalocean.com/products/networking/vpc/) in each region, which every resource joins automatically, plus an optional [VPC peering connection](https://docs.digitalocean.com/products/networking/vpc/how-to/) between the two regions if you want the B2 private-path cell. A third-party SaaS vector store account for arm C, with its region setting screenshotted for the disclosure.

**Tools on the Droplet.** Python 3 (preinstalled on DigitalOcean images), the harness's one dependency via `pip install "psycopg[binary]"`, and the PostgreSQL client via `apt install postgresql-client` for loading the corpus. [doctl](https://docs.digitalocean.com/reference/doctl/) is optional for creating clusters from the command line instead of the Control Panel.

**Step 1. Create the two clusters.** From the [Vector Databases page](https://cloud.digitalocean.com/vectordatabases), create a PostgreSQL cluster in the Droplet's datacenter (arm A) and another in the distant region (arm B), identical plan. Record both regions in your results file.

**Step 2. Lock down access and collect connection strings.** Add the Droplet to each cluster's trusted sources. Each managed cluster exposes two hostnames: the private hostname reaches the cluster over the VPC and only works from inside the same datacenter's network, and the public hostname routes over the internet. Arm A uses the private hostname. Arm B1 uses the public hostname, and B2 uses the private hostname over the peered VPC if you configured peering. Export each as its own DSN environment variable so runs cannot mix arms silently.

**Step 3. Load the identical corpus into both clusters.** Same table, same dimensionality, same index, same parameters. With `psql "$DSN_ARM_A"` and then again for arm B:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE items (id bigserial PRIMARY KEY, embedding vector(768));
INSERT INTO items (embedding)
SELECT ARRAY(SELECT random()*2-1 FROM generate_series(1,768))::vector
FROM generate_series(1,100000);
CREATE INDEX ON items USING hnsw (embedding vector_cosine_ops);
```

100,000 synthetic vectors keep the load fast and the comparison honest, since identical corpora and identical index parameters cancel ANN time out of the arm-to-arm delta. Scale to 1 million if you want production-shaped index depth, and note whichever count you used. Random vectors are fine here because this experiment measures the path, not recall.

**Step 4. Run the TCP probe against every arm first.** DigitalOcean Managed PostgreSQL listens on port 25060. The probe needs no database credentials and approximates one raw network round trip:

```bash
python3 locality_bench.py --mode tcp --host <arm-a-private-host> --port 25060 --out a_tcp.json
python3 locality_bench.py --mode tcp --host <arm-b-public-host>  --port 25060 --out b1_tcp.json
```

Put each probe's p50 next to the derived floor for that path. The gap is your route's overhead above physics, and if a probe lands below its floor, something is mislabeled, since nothing lands below the floor.

**Step 5. Run the retrieval cells.** For each arm, at k of 5, 20, and 100:

```bash
python3 locality_bench.py --mode pgvector --dsn "$DSN_ARM_A" --k 5   --out a_k5.json
python3 locality_bench.py --mode pgvector --dsn "$DSN_ARM_A" --k 20  --out a_k20.json
python3 locality_bench.py --mode pgvector --dsn "$DSN_ARM_A" --k 100 --out a_k100.json
```

Repeat the full set in a second time window on another day or overnight, per the measurement standards this cluster of articles already uses. The harness records the cold-connection first call separately from pooled steady state on every run, so the pooling confounder gets its own column for free.

**Step 6. Run arm C.** Point the same harness at the SaaS store if its endpoint speaks PostgreSQL wire protocol, and otherwise time its native client with the same trial counts and the same k values, disclosing the client difference in the results. Record the vendor's stated region next to the numbers.

**Step 7. Fill the template and tear down.** Copy every JSON file off the Droplet, fill the measured table in this article, and destroy both clusters from the [destroy page](https://docs.digitalocean.com/products/vector-databases/how-to/destroy/) so the smallest-plan clusters stop billing. Total infrastructure cost for the full run is a few dollars if you tear down the same day.

## The harness

Runnable on any GPU Droplet with Python 3. The TCP probe mode uses only the standard library. The pgvector mode needs one dependency, installed with `pip install "psycopg[binary]"`. Point `--dsn` at each arm in turn and keep the output files.

```python
#!/usr/bin/env python3
"""
Data-locality retrieval latency harness.

Modes:
  tcp     : bare TCP connect probe, approximates one network RTT (stdlib only)
  pgvector: timed vector similarity queries against a pgvector database

Per cell: >=75 trials after warmup discards, p50/p95/p99, cold-connection
first-call time recorded separately from pooled steady state.

Run each arm from the same GPU Droplet:
  python3 locality_bench.py --mode tcp --host db-host --port 25060 --out a_tcp.json
  python3 locality_bench.py --mode pgvector --dsn "$DSN_ARM_A" --k 5 --out a_k5.json
"""
import argparse, json, os, random, socket, statistics, time

def pctl(xs, p):
    xs = sorted(xs)
    k = (len(xs) - 1) * p / 100
    f = int(k); c = min(f + 1, len(xs) - 1)
    return xs[f] if f == c else xs[f] * (c - k) + xs[c] * (k - f)

def summarize(xs):
    return {"n": len(xs), "p50_ms": round(pctl(xs, 50), 2),
            "p95_ms": round(pctl(xs, 95), 2), "p99_ms": round(pctl(xs, 99), 2),
            "mean_ms": round(statistics.fmean(xs), 2)}

def tcp_probe(host, port, trials, warmup):
    times = []
    for i in range(trials + warmup):
        start = time.perf_counter()
        s = socket.create_connection((host, port), timeout=10)
        elapsed = (time.perf_counter() - start) * 1000
        s.close()
        if i >= warmup:
            times.append(elapsed)
        time.sleep(0.05)
    return {"mode": "tcp", "host": host, "port": port, "summary": summarize(times),
            "note": "TCP connect approximates one network round trip, no DB work"}

def pgvector_bench(dsn, k, dim, trials, warmup, table):
    import psycopg  # pip install "psycopg[binary]"
    rng = random.Random(7)
    qvec = "[" + ",".join(f"{rng.uniform(-1, 1):.6f}" for _ in range(dim)) + "]"
    sql = f"SELECT id FROM {table} ORDER BY embedding <=> %s::vector LIMIT %s"

    # cold connection: connect + first query, timed together
    start = time.perf_counter()
    conn = psycopg.connect(dsn)
    with conn.cursor() as cur:
        cur.execute(sql, (qvec, k))
        cur.fetchall()
    cold_ms = (time.perf_counter() - start) * 1000

    # pooled steady state: reuse the connection
    times = []
    with conn.cursor() as cur:
        for i in range(trials + warmup):
            q = "[" + ",".join(f"{rng.uniform(-1, 1):.6f}" for _ in range(dim)) + "]"
            start = time.perf_counter()
            cur.execute(sql, (q, k))
            cur.fetchall()
            elapsed = (time.perf_counter() - start) * 1000
            if i >= warmup:
                times.append(elapsed)
    conn.close()
    return {"mode": "pgvector", "k": k, "dim": dim,
            "cold_connection_first_call_ms": round(cold_ms, 2),
            "pooled": summarize(times)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["tcp", "pgvector"], required=True)
    ap.add_argument("--host"); ap.add_argument("--port", type=int, default=25060)
    ap.add_argument("--dsn", default=os.environ.get("PG_DSN"))
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--dim", type=int, default=768)
    ap.add_argument("--table", default="items")
    ap.add_argument("--trials", type=int, default=75)
    ap.add_argument("--warmup", type=int, default=10)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    if args.mode == "tcp":
        result = tcp_probe(args.host, args.port, args.trials, args.warmup)
    else:
        result = pgvector_bench(args.dsn, args.k, args.dim,
                                args.trials, args.warmup, args.table)
    result["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(args.out, "w") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
```

Run the TCP probe first on every arm and put its p50 next to the derived floor for that path. The gap between them is your route's overhead above physics. Then run the pgvector mode at k of 5, 20, and 100, twice per arm in separate time windows, and fill the template table. For readers debugging a surprising path, the [network performance diagnosis tutorial](https://www.digitalocean.com/community/tutorials/how-to-fix-network-performance-issues) covers asymmetric route problems this harness will surface but not explain.

## What this piece verifies, and what it does not

The physics floors are derivations shown with their method, checkable with a calculator, and certain as lower bounds. The compounding and proportionality tables are arithmetic on those floors. The VPC properties, peering price, engine lineup, Weaviate public preview status and date, and every linked DigitalOcean capability were verified against DigitalOcean's own documentation on August 6, 2026. The measured Arms A/B1/B2 numbers are from one harness window on August 10, 2026 (disclosed infra, 75 trials after warmup, synthetic corpus). This piece does not yet contain a second time window, an NYC→SGP arm, or a third-party SaaS arm — those cells stay blank rather than estimated. If your measured run lands somewhere these derivations say it cannot, the derivations lose, and publishing that result would improve this piece.

## Conclusion

The industry benchmarks the GPU and ignores the pipe. The derived hierarchy prices each rung of placement, the compounding table shows why agentic workloads change the verdict, and the harness turns the argument into your own numbers in an afternoon on a GPU Droplet.

The optimizations across this cluster compose or fail together across the whole path. A [warm prompt cache](https://www.digitalocean.com/community/tutorials/prompt-caching-cost-break-even) saves prefill milliseconds a wrong-region vector database hands right back. A [tuned serving tail](https://www.digitalocean.com/community/conceptual-articles/when-your-vllm-p99) means little behind 496 ms of geography, and the [inference trilemma](https://www.digitalocean.com/blog/llm-inference-tradeoffs) framing applies to placement exactly as it applies to serving: you choose which constraint to pay, and this piece prices one that most teams never noticed they were paying. Co-locate first. Tune second. Measure both.

## FAQ

**Does VPC peering fix cross-region vector DB latency?**  
No. In the August 10, 2026 run, NYC3→SFO3 peered private hostname (B2) matched public (B1) within a few milliseconds on TCP and retrieval. Peering changes privacy and egress accounting; it does not move the buildings closer.

**Is ~60–70 ms of continental tax worth a migration for single-shot RAG?**  
Often no. Against a 2-second generation, a 67 ms retrieval tax is a few percent of response time. Index tuning and caching may be better uses of the week. For multi-hop agentic RAG, the same tax times hop count — and the verdict flips.

**Why was my cold pgvector call ~10× the pooled p50?**  
A cold connection pays TCP plus TLS handshakes before the first query. On a ~68 ms NYC–SFO path, that setup alone can land in the hundreds of milliseconds. Pool the client; do not open a new connection per request.

**Should the vector database always sit next to the GPU?**  
Yes when you control both and residency allows it. Same-DC VPC was 1.90 ms pooled k=5 versus 66.97 ms cross-region in this run. Compliance residency can force the opposite move: relocate compute toward the data, or replicate a slowly changing index.

**Can I reproduce these numbers?**  
Yes. The harness, load SQL, and raw JSON are in [anishsingh20/data-locality-tax](https://github.com/anishsingh20/data-locality-tax). Expect the same ordering and floors; absolute milliseconds will vary by path and time of day.

## Companion repository

Harness, load script, raw per-cell JSON, and run metadata: [https://github.com/anishsingh20/data-locality-tax](https://github.com/anishsingh20/data-locality-tax).

## References

### DigitalOcean documentation

- [DigitalOcean Vector Databases](https://docs.digitalocean.com/products/vector-databases/) (engines, release notes, Weaviate public preview announcement of July 1, 2026)
- [Choosing Between OpenSearch, Weaviate, and pgvector](https://docs.digitalocean.com/products/vector-databases/concepts/choosing-an-engine/)
- [Vector Databases Availability](https://docs.digitalocean.com/products/vector-databases/details/availability/)
- [Create a Vector Database Cluster](https://docs.digitalocean.com/products/vector-databases/how-to/create/)
- [VPC Features](https://docs.digitalocean.com/products/networking/vpc/details/features/) and [VPC Availability](https://docs.digitalocean.com/products/networking/vpc/details/availability/) (datacenter scoping, free intra-VPC traffic, peering availability)
- [Regional Availability](https://docs.digitalocean.com/platform/regional-availability/)
- [GPU Droplets](https://www.digitalocean.com/products/gpu-droplets)

### DigitalOcean community and blog

- [p50 vs p99 Latency: Why Median Benchmarks Mislead AI Agent Workloads](https://www.digitalocean.com/community/tutorials/p50-vs-p99-latency-llm-inference)
- [When Your vLLM p99 is Worse Than Your p50](https://www.digitalocean.com/community/conceptual-articles/when-your-vllm-p99)
- [How Does Prompt Caching Work: The Cost Break-Even](https://www.digitalocean.com/community/tutorials/prompt-caching-cost-break-even)
- [Build an End-to-End RAG Pipeline](https://www.digitalocean.com/community/tutorials/end-to-end-rag-pipeline)
- [Zero-Infrastructure RAG Agent with Knowledge Bases and MCP](https://www.digitalocean.com/community/tutorials/build-rag-agent-digitalocean-knowledge-bases-mcp)
- [How to Choose the Right Vector Database](https://www.digitalocean.com/community/conceptual-articles/how-to-choose-the-right-vector-database)
- [Metrics that Matter with Serverless Inference](https://www.digitalocean.com/community/tutorials/metrics-that-matter-serverless-inference)
- [The LLM Inference Trilemma](https://www.digitalocean.com/blog/llm-inference-tradeoffs)
- [How to Diagnose and Fix Asymmetric Network Performance Issues](https://www.digitalocean.com/community/tutorials/how-to-fix-network-performance-issues)
