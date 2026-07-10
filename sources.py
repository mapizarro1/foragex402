import httpx

TIMEOUT = httpx.Timeout(10.0)
USDC_DECIMALS = 1_000_000

def _normalize_item(item):
    accepts = item.get("accepts") or []
    best = accepts[0] if accepts else {}
    raw_amount = best.get("maxAmountRequired")
    atomic = None
    if raw_amount is not None:
        try:
            atomic = int(raw_amount)
        except (ValueError, TypeError):
            atomic = None
    return {
        "resource": item.get("resource") or best.get("resource", ""),
        "description": best.get("description", "") or item.get("description", ""),
        "price_usdc": (atomic / USDC_DECIMALS) if atomic is not None else None,
        "max_amount_atomic": atomic,
        "network": best.get("network", ""),
        "asset": best.get("asset", ""),
        "mime_type": best.get("mimeType", ""),
    }

class CdpBazaar:
    name = "cdp_bazaar"
    SEARCH_URL = "https://api.cdp.coinbase.com/platform/v2/x402/discovery/search"

    async def search(self, query):
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(self.SEARCH_URL, params={"query": query})
            r.raise_for_status()
            data = r.json()
        items = data.get("items") or data.get("resources") or []
        return [_normalize_item(i) for i in items]

class X402OrgFacilitator:
    name = "x402_org"
    LIST_URL = "https://x402.org/facilitator/discovery/resources"

    async def search(self, query):
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(self.LIST_URL)
            r.raise_for_status()
            data = r.json()
        items = data.get("items") or data.get("resources") or []
        normalized = [_normalize_item(i) for i in items]
        terms = [t for t in query.lower().split() if len(t) > 2]
        if not terms:
            return normalized[:25]
        return [n for n in normalized if any(t in (n["resource"] + " " + n["description"]).lower() for t in terms)]

ALL_SOURCES = [CdpBazaar(), X402OrgFacilitator()]
