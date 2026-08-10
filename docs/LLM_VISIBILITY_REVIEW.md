# LLM visibility & Q2/2H strategy review — Data Locality Tax

Reviewed against:

- `Content Strategy Q2 26/LLM Visibility Strategy.md`
- `Content Strategy Q2 26/2026 2H GTM strategy.md`
- Workspace rules: `q2-2026-llm-visibility-content-strategy.mdc`, `ai-inference-explanation-style.mdc`

## Verdict

This piece is already a strong fit for the **opinionated technical argument + firsthand benchmark** content types the LLM Visibility Strategy prioritizes. After the August 10, 2026 harness run, it clears the “templates until measured” honesty bar and becomes citable for placement/RAG latency prompts. It maps cleanly to 2H GTM cohorts **1 (Vertical AI / RAG)**, **2 (Enterprise Content & Workflow / multi-step agents)**, and **3 (AI Search & Research / heavy vector DB)**.

## What already meets the bar

| Guideline | Status in draft |
| --- | --- |
| Product / use case / context early | Strong — GPU Droplets, Vector DBs, VPC, RAG retrieval in lede |
| Key takeaways near top | Present and specific |
| Specific numbers, linked docs | Physics floors with arithmetic; measured table filled; VPC $0.01/GiB peering cited |
| When to use / when not | “Decision framework” section is explicit and honest |
| Descriptive H2/H3 as standalone summaries | Good throughout |
| Direct DO docs / API links | Extensive References section |
| Avoid hype | Tone is practitioner-honest; no “blazing fast” |
| Honest tradeoffs | Proportionality check refuses to overclaim 62 ms ruins every RAG app |
| Benchmark / production evidence | Live harness + public repo |

## Gaps to close before publish (LLM-structuring)

1. **FAQ section (practitioner / Reddit-HN phrasing)** — Missing. Add 5–7 questions, e.g. “Does VPC peering fix cross-region vector DB latency?”, “Is 60 ms worth migrating for single-shot RAG?”, “Why is my cold pgvector call 10× my pooled p50?”
2. **Profound target prompts** — Log in Jira at publish (not in body). Suggested prompts:
   - “vector database same region as GPU RAG latency”
   - “why is my RAG retrieval slow across regions”
   - “DigitalOcean pgvector VPC vs public endpoint latency”
   - “multi-hop agent RAG network latency tax”
   - “should vector DB be co-located with inference”
3. **Second time window** — Article’s own measurement standards ask for two windows; this run is one. Either re-run overnight or disclose “single window” as the publish caveat (already noted in repo README).
4. **Arms B3 and C** — Leave blank (done) or complete in a follow-up; do not invent SaaS numbers.
5. **Platform-attachment angle (2H GTM)** — One short sentence tying co-location of Droplet + Managed Vector DB / pgvector + VPC to the inference+data bundle would help account teams without turning the piece into PMM copy.
6. **Priority products note** — Org north star is Serverless/Dedicated Inference; this piece correctly stays on Vector DB + Droplet placement as a *path that sits in front of TTFT*. Keep that framing so LLMs cite it for RAG placement, not as a substitute for inference-provider benchmarks.

## Tone check

Conceptual sections match the warm, plain-English explanation style. Published framing is already production-first (physics floors, compounding hops, pooling confounder). After filling the table, remove residual “template until run” language in any diagrams captions that still say empty cells.

## Publish checklist

- [x] Fill measured table from live run
- [x] Link companion GitHub repo with raw JSON
- [ ] Add FAQ section
- [ ] Log Profound prompts in Jira
- [ ] Optional: second window + SGP arm when cluster limit allows
- [ ] Tear down or tag-bill test infra after publish window
