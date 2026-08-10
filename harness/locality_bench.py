#!/usr/bin/env python3
"""
Data-locality retrieval latency harness.

Modes:
  tcp     : bare TCP connect probe, approximates one network RTT (stdlib only)
  pgvector: timed vector similarity queries against a pgvector database

Per cell: >=75 trials after warmup discards, p50/p95/p99, cold-connection
first-call time recorded separately from pooled steady state.

Run each arm from the same Droplet:
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
