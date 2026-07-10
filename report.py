import sys, sqlite3, os

DB_PATH = os.environ.get("FORAGEX402_DB", "/var/lib/foragex402/queries.db")

def main():
    days = 7
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    cutoff = f"-{days} days"

    con = sqlite3.connect(DB_PATH)
    q = lambda sql: con.execute(sql, (cutoff,)).fetchall()

    total = q("SELECT COUNT(*) FROM queries WHERE ts_utc >= datetime('now', ?)")[0][0]
    zeros = q("SELECT COUNT(*) FROM queries WHERE zero_result=1 AND ts_utc >= datetime('now', ?)")[0][0]

    print(f"foragex402 demand report -- last {days} days")
    print(f"total queries : {total}")
    print(f"zero-result   : {zeros}" + (f"  ({100*zeros//total}%)" if total else ""))
    print()

    print("TOP QUERIES")
    for text, n in q("SELECT query, COUNT(*) c FROM queries"
                     " WHERE ts_utc >= datetime('now', ?)"
                     " GROUP BY lower(query) ORDER BY c DESC LIMIT 15"):
        print(f"  {n:>4}  {text[:70]}")
    print()

    print("MISSES (zero results -- unmet demand)")
    for text, n in q("SELECT query, COUNT(*) c FROM queries"
                     " WHERE zero_result=1 AND ts_utc >= datetime('now', ?)"
                     " GROUP BY lower(query) ORDER BY c DESC LIMIT 15"):
        print(f"  {n:>4}  {text[:70]}")
    print()

    print("EXPLICIT MISS REPORTS")
    for text, price in con.execute(
            "SELECT query, max_price_usdc FROM queries"
            " WHERE explicit_miss=1 AND ts_utc >= datetime('now', ?)"
            " ORDER BY ts_utc DESC LIMIT 15", (cutoff,)):
        tag = f" [would pay ${price}]" if price else ""
        print(f"  - {text[:70]}{tag}")
    print()

    print("FALSE-HIT CANDIDATES (re-search within 5 min of served results)")
    for q1, q2, gap in con.execute(
            "SELECT a.query, b.query,"
            " CAST((julianday(b.ts_utc)-julianday(a.ts_utc))*86400 AS INT)"
            " FROM queries a JOIN queries b"
            "   ON a.caller_key = b.caller_key AND b.id > a.id"
            " WHERE a.caller_key IS NOT NULL"
            "   AND a.merged_count > 0 AND a.explicit_miss = 0"
            "   AND julianday(b.ts_utc) - julianday(a.ts_utc) < 5.0/1440"
            "   AND lower(a.query) != lower(b.query)"
            "   AND a.ts_utc >= datetime('now', ?)"
            " ORDER BY a.ts_utc DESC LIMIT 15", (cutoff,)):
        print(f"  [{gap:>3}s] {q1[:32]} -> {q2[:32]}")
    print()

    print("CLIENTS")
    for name, n in q("SELECT client_name, COUNT(*) c FROM queries"
                     " WHERE ts_utc >= datetime('now', ?)"
                     " GROUP BY client_name ORDER BY c DESC"):
        print(f"  {n:>4}  {name}")

if __name__ == "__main__":
    main()
