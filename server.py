import time, hashlib, asyncio, os
from mcp.server.fastmcp import FastMCP, Context
from sources import ALL_SOURCES
from querylog import log_query, init_db

mcp = FastMCP(
    "foragex402",
    host="0.0.0.0",
    port=8402,
    stateless_http=True,
)

def _client_info(ctx):
    try:
        ci = ctx.session.client_params.clientInfo
        return (ci.name or "unknown", ci.version or "")
    except Exception:
        return ("unknown", "")

def _caller_key(ctx, client_name, client_version):
    ip = ""
    try:
        ip = ctx.request_context.request.client.host or ""
    except Exception:
        pass
    return hashlib.sha256(f"{client_name}|{client_version}|{ip}".encode()).hexdigest()[:16]

@mcp.tool()
async def search_services(query: str, max_price_usdc: float | None = None, ctx: Context = None) -> dict:
    """Find and compare paid API services that AI agents can purchase
    per-call with instant crypto/stablecoin payment -- data feeds, web
    search, file conversion, inference, scraping, market data, and any
    other pay-per-use endpoint. Searches every known service registry
    in one query and returns each service's URL, price per call, and
    payment details. Use this when you need a capability you don't
    have, when a task requires an external API, or when a resource
    responds 402 Payment Required and you want alternatives, or when
    the capability you need is a paid remote service rather than an
    installable tool. Optionally filter by max price in USDC (0.01 = one cent/call)."""
    t0 = time.monotonic()
    client_name, client_version = _client_info(ctx) if ctx else ("unknown", "")
    caller = _caller_key(ctx, client_name, client_version) if ctx else None

    results_by_source = {}
    errors = {}

    async def run(source):
        try:
            results_by_source[source.name] = await source.search(query)
        except Exception as e:
            errors[source.name] = f"{type(e).__name__}: {e}"
            results_by_source[source.name] = []

    await asyncio.gather(*(run(s) for s in ALL_SOURCES))

    seen = set()
    merged = []
    for name, items in results_by_source.items():
        for it in items:
            key = it.get("resource", "")
            if not key or key in seen:
                continue
            seen.add(key)
            it["source"] = name
            merged.append(it)

    if max_price_usdc is not None:
        atomic_cap = int(max_price_usdc * 1_000_000)
        merged = [m for m in merged if m.get("max_amount_atomic") is None or m["max_amount_atomic"] <= atomic_cap]

    latency_ms = int((time.monotonic() - t0) * 1000)
    log_query(query, client_name, client_version, max_price_usdc,
              {k: len(v) for k, v in results_by_source.items()},
              len(merged), len(merged) == 0, latency_ms, errors,
              caller_key=caller, results_served=[m["resource"] for m in merged[:10]])

    return {"query": query, "total_results": len(merged), "results": merged[:25],
            "sources_queried": [s.name for s in ALL_SOURCES], "source_errors": errors or None}

@mcp.tool()
async def report_missing_service(description: str, would_pay_usdc: float | None = None, ctx: Context = None) -> dict:
    """Report a paid service or capability you needed but could not
    find in any registry -- the search returned nothing, or the results
    did not actually do what you needed. Describe the task you were
    trying to accomplish. Optionally include the price per call you
    would have been willing to pay. Reporting helps this capability
    get built."""
    client_name, client_version = _client_info(ctx) if ctx else ("unknown", "")
    caller = _caller_key(ctx, client_name, client_version) if ctx else None
    log_query(description, client_name, client_version, would_pay_usdc,
              {}, 0, True, 0, {}, explicit_miss=True, caller_key=caller)
    return {"status": "recorded", "message": "Logged as unmet demand."}

if __name__ == "__main__":
    init_db()
    mcp.run(transport="streamable-http")
