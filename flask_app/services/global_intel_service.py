"""
Silicon Oracle - Global Intelligence Service
=============================================
Extends the existing MacroIntelService with data layers it doesn't cover:

  1. Global stock markets  (Nikkei, FTSE, DAX, Hang Seng, KOSPI, BSE, Shanghai, ASX)
  2. Sector ETF rotation   (SOXX, XLK, XLV, XLE, XLF, ARKK, XLP, XLU)
  3. Fear & Greed composite (VIX + HYG + TLT + ARKK — calculated, not scraped)
  4. Real yield curve       (3M / 2Y / 10Y / 30Y from Yahoo Finance)
  5. Key peers for holdings (NVDA, AMD, INTC, MU for TSM/ASML context)
  6. Dividend screener      (JEPI, JEPQ, SCHD, ABBV, O, KO — with NRA tax-adjusted yield)
  7. Swing candidate screen (RSI proxy, off-52wk-high filter, momentum)

All data from Yahoo Finance (same source Silicon Oracle already uses via yfinance).
No new API keys required.  Cached at module level — TTL configurable per section.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level caches  (shared across requests — same pattern as macro_intel)
# ---------------------------------------------------------------------------
_CACHES: Dict[str, Dict[str, Any]] = {
    "global_markets": {"data": None, "expires": 0.0},
    "sector_rotation": {"data": None, "expires": 0.0},
    "fear_greed": {"data": None, "expires": 0.0},
    "yield_curve": {"data": None, "expires": 0.0},
    "peers": {"data": None, "expires": 0.0},
    "dividend_screen": {"data": None, "expires": 0.0},
    "swing_screen": {"data": None, "expires": 0.0},
}

_TTL = {
    "global_markets": 120,  # 2 min  — markets move fast
    "sector_rotation": 120,
    "fear_greed": 120,
    "yield_curve": 300,  # 5 min  — yields are slower
    "peers": 120,
    "dividend_screen": 300,
    "swing_screen": 300,
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _cached(key: str):
    """Return cached data if still fresh, else None."""
    entry = _CACHES.get(key, {})
    if entry.get("data") is not None and time.time() < entry.get("expires", 0):
        return entry["data"]
    return None


def _store(key: str, data: Any) -> Any:
    _CACHES[key] = {"data": data, "expires": time.time() + _TTL.get(key, 120)}
    return data


def _yf_quote(symbol: str, timeout: int = 8) -> Optional[Dict[str, Any]]:
    """
    Fetch a single quote from Yahoo Finance chart API.
    Returns dict with price, prev_close, change_pct, hi52, lo52 or None on error.
    Uses urllib (no extra dependency — same as MacroIntelService).
    """
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(symbol)
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = json.loads(resp.read())

        meta = raw["chart"]["result"][0]["meta"]
        price = float(meta.get("regularMarketPrice") or 0)
        prev = float(meta.get("chartPreviousClose") or meta.get("previousClose") or price)
        chg_pct = round(((price - prev) / prev * 100) if prev else 0, 2)
        return {
            "price": round(price, 2),
            "prev_close": round(prev, 2),
            "change_pct": chg_pct,
            "hi52": round(float(meta.get("fiftyTwoWeekHigh") or 0), 2),
            "lo52": round(float(meta.get("fiftyTwoWeekLow") or 0), 2),
        }
    except Exception as exc:
        logger.debug("_yf_quote(%s) failed: %s", symbol, exc)
        return None


def _off_high_pct(q: Dict) -> float:
    """Return % below 52-week high (negative means below high)."""
    if not q or not q.get("hi52"):
        return 0.0
    return round((q["price"] - q["hi52"]) / q["hi52"] * 100, 1)


def _rsi_proxy(chg_pct: float, hi52: float, lo52: float, price: float) -> int:
    """
    Very lightweight RSI proxy from a single quote (no history needed).
    Maps position-in-52wk-range → approximate RSI bucket.
    Good enough for a quick pass/fail screen; not a substitute for real RSI.
    """
    if hi52 <= lo52:
        return 50
    pct_range = (price - lo52) / (hi52 - lo52) * 100
    # Rough mapping: bottom of range ≈ 30, middle ≈ 50, top ≈ 75
    return round(30 + pct_range * 0.45)


# ---------------------------------------------------------------------------
# 1. Global stock markets
# ---------------------------------------------------------------------------

GLOBAL_MARKETS = [
    # Label,          Yahoo symbol,   Region
    ("Nikkei 225", "^N225", "Asia-Pacific"),
    ("FTSE 100", "^FTSE", "Europe"),
    ("DAX", "^GDAXI", "Europe"),
    ("Hang Seng", "^HSI", "Asia-Pacific"),
    ("BSE Sensex", "^BSESN", "Asia-Pacific"),
    ("KOSPI", "^KS11", "Asia-Pacific"),
    ("Shanghai Comp", "000001.SS", "Asia-Pacific"),
    ("ASX 200", "^AXJO", "Asia-Pacific"),
    ("CAC 40", "^FCHI", "Europe"),
    ("Euro Stoxx 50", "^STOXX50E", "Europe"),
    ("IBOV Brazil", "^BVSP", "Americas"),
    ("TSX Canada", "^GSPTSE", "Americas"),
]


def get_global_markets(force: bool = False) -> List[Dict[str, Any]]:
    """Return live prices for all global indices."""
    if not force:
        cached = _cached("global_markets")
        if cached is not None:
            return cached

    results = []
    for label, symbol, region in GLOBAL_MARKETS:
        q = _yf_quote(symbol)
        if q:
            results.append(
                {
                    "label": label,
                    "symbol": symbol,
                    "region": region,
                    "price": q["price"],
                    "change_pct": q["change_pct"],
                    "direction": "up" if q["change_pct"] >= 0 else "down",
                }
            )

    return _store("global_markets", results)


# ---------------------------------------------------------------------------
# 2. Sector ETF rotation
# ---------------------------------------------------------------------------

SECTOR_ETFS = [
    # ETF,    Sector label,          Key for your holdings
    ("SOXX", "Semiconductors", True),  # TSM, ASML
    ("XLK", "Technology", True),  # GOOGL
    ("XLV", "Healthcare/Biotech", True),  # TRVI
    ("XLE", "Energy", False),
    ("XLF", "Financials", True),  # BRK.B
    ("ARKK", "Innovation/Growth", False),  # risk appetite gauge
    ("XLP", "Consumer Staples", False),  # defensive
    ("XLU", "Utilities", False),  # defensive
    ("XLI", "Industrials", False),
    ("XLB", "Materials", False),
    ("XLRE", "Real Estate", False),
    ("XLY", "Consumer Discret.", False),
]


def get_sector_rotation(force: bool = False) -> Dict[str, Any]:
    """Return sector ETF changes and rotation signal."""
    if not force:
        cached = _cached("sector_rotation")
        if cached is not None:
            return cached

    sectors = []
    for sym, label, in_your_holdings in SECTOR_ETFS:
        q = _yf_quote(sym)
        if q:
            sectors.append(
                {
                    "symbol": sym,
                    "label": label,
                    "price": q["price"],
                    "change_pct": q["change_pct"],
                    "in_your_holdings": in_your_holdings,
                    "direction": "up" if q["change_pct"] >= 0 else "down",
                }
            )

    if not sectors:
        return _store("sector_rotation", {"sectors": [], "top": None, "bottom": None})

    sorted_s = sorted(sectors, key=lambda x: -x["change_pct"])
    result = {
        "sectors": sectors,
        "top": sorted_s[0] if sorted_s else None,  # money flowing in
        "bottom": sorted_s[-1] if sorted_s else None,  # money flowing out
        "risk_on": sorted_s[0]["change_pct"] > 0 if sorted_s else False,
    }
    return _store("sector_rotation", result)


# ---------------------------------------------------------------------------
# 3. Fear & Greed composite
# ---------------------------------------------------------------------------


def get_fear_greed(
    vix_value: Optional[float] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Composite fear/greed index built from:
      - VIX level & change   (40% weight)
      - HYG (high-yield bond ETF change)  (20%)
      - TLT (long-duration treasury change) (20%)
      - ARKK change          (20%) — risk appetite proxy

    Score: 0 = extreme fear, 100 = extreme greed.
    Caller can pass vix_value if already fetched (avoids duplicate request).
    """
    if not force:
        cached = _cached("fear_greed")
        if cached is not None:
            return cached

    components: Dict[str, float] = {}

    # VIX
    if vix_value is not None:
        vix = vix_value
    else:
        q = _yf_quote("^VIX")
        vix = q["price"] if q else 20.0
    # VIX contribution: <12=max greed(100), >35=max fear(0), linear between
    vix_score = max(0, min(100, (35 - vix) / (35 - 12) * 100))
    components["vix"] = round(vix_score, 1)

    # HYG — credit health (higher = less fear)
    q_hyg = _yf_quote("HYG")
    if q_hyg:
        hyg_score = max(0, min(100, 50 + q_hyg["change_pct"] * 10))
        components["hyg"] = round(hyg_score, 1)
    else:
        components["hyg"] = 50.0

    # TLT — flight to safety (TLT up = fear, down = greed)
    q_tlt = _yf_quote("TLT")
    if q_tlt:
        tlt_score = max(0, min(100, 50 - q_tlt["change_pct"] * 10))
        components["tlt"] = round(tlt_score, 1)
    else:
        components["tlt"] = 50.0

    # ARKK — risk appetite
    q_arkk = _yf_quote("ARKK")
    if q_arkk:
        arkk_score = max(0, min(100, 50 + q_arkk["change_pct"] * 8))
        components["arkk"] = round(arkk_score, 1)
    else:
        components["arkk"] = 50.0

    # Weighted composite
    score = (
        components["vix"] * 0.40
        + components["hyg"] * 0.20
        + components["tlt"] * 0.20
        + components["arkk"] * 0.20
    )
    score = round(score, 1)

    if score >= 75:
        label, color = "Extreme Greed", "#00C853"
    elif score >= 60:
        label, color = "Greed", "#76FF03"
    elif score >= 40:
        label, color = "Neutral", "#FFD600"
    elif score >= 25:
        label, color = "Fear", "#FF6D00"
    else:
        label, color = "Extreme Fear", "#D50000"

    result = {
        "score": score,
        "label": label,
        "color": color,
        "components": components,
        "vix_raw": round(vix, 1),
    }
    return _store("fear_greed", result)


# ---------------------------------------------------------------------------
# 4. Real yield curve
# ---------------------------------------------------------------------------

YIELD_SYMBOLS = [
    ("3M", "^IRX"),
    ("2Y", "^TBL"),
    ("10Y", "^TNX"),
    ("30Y", "^TYX"),
]


def get_yield_curve(force: bool = False) -> Dict[str, Any]:
    """Return actual 3M/2Y/10Y/30Y yields and inversion signal."""
    if not force:
        cached = _cached("yield_curve")
        if cached is not None:
            return cached

    yields: Dict[str, float] = {}
    for label, sym in YIELD_SYMBOLS:
        q = _yf_quote(sym)
        if q and q["price"]:
            yields[label] = round(q["price"], 2)

    # Inversion check
    inverted = False
    flat = False
    spread_2_10 = None
    if "2Y" in yields and "10Y" in yields:
        spread_2_10 = round(yields["10Y"] - yields["2Y"], 2)
        inverted = spread_2_10 < 0
        flat = 0 <= spread_2_10 < 0.30

    if inverted:
        curve_signal = "INVERTED ⚠"
        curve_color = "#D50000"
        curve_note = "Recession risk elevated — historically precedes downturn by 6-18mo"
    elif flat:
        curve_signal = "FLAT"
        curve_color = "#FF6D00"
        curve_note = "Slowing growth expected — watch credit spreads"
    else:
        curve_signal = "NORMAL"
        curve_color = "#00C853"
        curve_note = "Healthy curve — growth expected"

    result = {
        "yields": yields,
        "spread_2_10": spread_2_10,
        "inverted": inverted,
        "flat": flat,
        "signal": curve_signal,
        "signal_color": curve_color,
        "note": curve_note,
    }
    return _store("yield_curve", result)


# ---------------------------------------------------------------------------
# 5. Key peers — dynamic based on user's shadow portfolio holdings
# ---------------------------------------------------------------------------

# Maps each holding ticker → list of (peer_ticker, context_note) tuples
PEER_MAP: Dict[str, List[tuple]] = {
    # Semiconductors — foundry/fab
    "TSM": [
        ("NVDA", "NVIDIA — biggest AI customer"),
        ("AMD", "AMD — major customer"),
        ("INTC", "Intel — competitor+customer"),
        ("QCOM", "Qualcomm — mobile chips"),
        ("AVGO", "Broadcom — ASIC customer"),
    ],
    "INTC": [
        ("AMD", "AMD — direct rival"),
        ("TSM", "TSMC — foundry competitor"),
        ("NVDA", "NVIDIA — GPU dominance"),
        ("QCOM", "Qualcomm — ARM rival"),
        ("AVGO", "Broadcom — data center"),
    ],
    # Semiconductor equipment
    "ASML": [
        ("LRCX", "Lam Research — etch peer"),
        ("AMAT", "Applied Materials — CVD peer"),
        ("KLAC", "KLA Corp — inspection peer"),
        ("TER", "Teradyne — test equipment"),
        ("ONTO", "Onto Innovation — metrology"),
    ],
    "LRCX": [
        ("ASML", "ASML — litho leader"),
        ("AMAT", "Applied Materials — peer"),
        ("KLAC", "KLA Corp — peer"),
        ("TER", "Teradyne — test peer"),
    ],
    "AMAT": [
        ("ASML", "ASML — litho leader"),
        ("LRCX", "Lam Research — peer"),
        ("KLAC", "KLA Corp — peer"),
        ("ONTO", "Onto Innovation — peer"),
    ],
    "KLAC": [
        ("ASML", "ASML — litho"),
        ("AMAT", "Applied Materials — peer"),
        ("LRCX", "Lam Research — peer"),
    ],
    # GPU / AI chips
    "NVDA": [
        ("AMD", "AMD — GPU rival"),
        ("INTC", "Intel — Gaudi challenger"),
        ("TSM", "TSMC — foundry"),
        ("AVGO", "Broadcom — ASIC rival"),
        ("QCOM", "Qualcomm — edge AI"),
    ],
    "AMD": [
        ("NVDA", "NVIDIA — GPU/AI leader"),
        ("INTC", "Intel — x86 rival"),
        ("TSM", "TSMC — foundry"),
        ("QCOM", "Qualcomm — ARM rival"),
    ],
    # Memory
    "MU": [
        ("WDC", "Western Digital — NAND peer"),
        ("SKX", "SK Hynix — DRAM rival"),
        ("INTC", "Intel — Optane overlap"),
        ("NVDA", "NVIDIA — HBM customer"),
    ],
    # Broadline mega-cap tech
    "AAPL": [
        ("MSFT", "Microsoft — platform rival"),
        ("GOOG", "Alphabet — services rival"),
        ("META", "Meta — AR/VR rival"),
        ("AMZN", "Amazon — cloud/retail"),
    ],
    "MSFT": [
        ("AAPL", "Apple — platform rival"),
        ("GOOG", "Alphabet — cloud/AI rival"),
        ("AMZN", "Amazon — cloud rival"),
        ("CRM", "Salesforce — enterprise SaaS"),
    ],
    "GOOG": [
        ("META", "Meta — ad duopoly peer"),
        ("MSFT", "Microsoft — cloud/AI rival"),
        ("AMZN", "Amazon — AWS vs GCP"),
        ("SNAP", "Snap — social media"),
    ],
    "META": [
        ("GOOG", "Alphabet — ad rival"),
        ("SNAP", "Snap — social peer"),
        ("PINS", "Pinterest — social peer"),
        ("TTD", "The Trade Desk — ad-tech peer"),
    ],
    "AMZN": [
        ("MSFT", "Microsoft — cloud rival"),
        ("GOOG", "Alphabet — cloud rival"),
        ("WMT", "Walmart — retail rival"),
        ("SHOP", "Shopify — e-commerce"),
    ],
    # Payments / fintech
    "V": [
        ("MA", "Mastercard — direct peer"),
        ("PYPL", "PayPal — digital wallet"),
        ("SQ", "Block — fintech rival"),
        ("ADYEY", "Adyen — merchant processing"),
    ],
    "MA": [
        ("V", "Visa — direct peer"),
        ("PYPL", "PayPal — digital wallet"),
        ("SQ", "Block — fintech rival"),
    ],
    "PYPL": [
        ("SQ", "Block — peer"),
        ("V", "Visa — network peer"),
        ("MA", "Mastercard — network peer"),
    ],
    # EV / Auto
    "TSLA": [
        ("RIVN", "Rivian — EV peer"),
        ("NIO", "NIO — China EV"),
        ("GM", "GM — ICE→EV transition"),
        ("F", "Ford — ICE→EV transition"),
    ],
    # ETFs — show top holdings as peers
    "QQQ": [
        ("NVDA", "NVDA — top QQQ weight"),
        ("AAPL", "AAPL — top QQQ weight"),
        ("MSFT", "MSFT — top QQQ weight"),
        ("AMZN", "AMZN — top QQQ weight"),
    ],
    "SPY": [
        ("AAPL", "AAPL — top SPY weight"),
        ("MSFT", "MSFT — top SPY weight"),
        ("NVDA", "NVDA — top SPY weight"),
        ("AMZN", "AMZN — top SPY weight"),
    ],
}

# Fallback peers shown when holdings are empty or not in PEER_MAP
_DEFAULT_PEERS = [
    ("NVDA", "NVIDIA — AI/GPU leader"),
    ("MSFT", "Microsoft — cloud/AI leader"),
    ("AAPL", "Apple — consumer tech leader"),
    ("TSM", "TSMC — foundry leader"),
    ("AMZN", "Amazon — cloud/retail leader"),
    ("GOOG", "Alphabet — search/AI leader"),
]


def get_peers(holdings: Optional[List[str]] = None, force: bool = False) -> Dict[str, Any]:
    """
    Return live peer data based on the user's shadow portfolio holdings.
    Falls back to default market leaders if holdings are empty or unmapped.
    """
    # Build peer list from holdings
    seen: set = set()
    peer_list: List[tuple] = []
    matched_holdings: List[str] = []

    if holdings:
        for ticker in holdings:
            t = ticker.upper()
            if t in PEER_MAP:
                matched_holdings.append(t)
                for peer_sym, peer_note in PEER_MAP[t]:
                    if peer_sym not in seen and peer_sym != t:
                        seen.add(peer_sym)
                        peer_list.append((peer_sym, peer_note))

    if not peer_list:
        peer_list = _DEFAULT_PEERS
        matched_holdings = []

    # Limit to top 9
    peer_list = peer_list[:9]

    results = []
    for sym, note in peer_list:
        q = _yf_quote(sym)
        if q:
            results.append(
                {
                    "symbol": sym,
                    "note": note,
                    "price": q["price"],
                    "change_pct": q["change_pct"],
                    "hi52": q["hi52"],
                    "lo52": q["lo52"],
                    "off_high": _off_high_pct(q),
                    "direction": "up" if q["change_pct"] >= 0 else "down",
                }
            )

    return {
        "peers": results,
        "based_on": matched_holdings,  # which holdings drove the selection
    }


# ---------------------------------------------------------------------------
# 6. Dividend screener (F1 NRA-adjusted)
# ---------------------------------------------------------------------------

# Gross yield estimates (updated periodically) — used when live data unavailable
_GROSS_YIELD_ESTIMATES: Dict[str, float] = {
    "JEPI": 7.5,
    "JEPQ": 9.2,
    "DIVO": 4.8,
    "SCHD": 3.8,
    "VYM": 2.9,
    "HDV": 3.7,
    "DGRO": 2.4,
    "ABBV": 3.6,
    "PEP": 3.5,
    "JNJ": 3.2,
    "O": 5.8,
    "MO": 7.8,
    "T": 5.9,
    "KO": 3.1,
}

# NRA withholding rate for non-resident aliens (F1 visa holders)
# India-US tax treaty may reduce this to 15-25%; 30% is the default
NRA_WITHHOLDING = 0.30


def _nra_effective_yield(gross: float, rate: float = NRA_WITHHOLDING) -> float:
    """After-tax yield for a non-resident alien."""
    return round(gross * (1 - rate), 2)


def get_dividend_screen(
    nra_rate: float = NRA_WITHHOLDING,
    force: bool = False,
) -> List[Dict[str, Any]]:
    """
    Return dividend candidates with gross + NRA-adjusted effective yields.
    Sorted by effective_yield descending.
    """
    if not force:
        cached = _cached("dividend_screen")
        if cached is not None:
            return cached

    results = []
    for sym, gross_yield in _GROSS_YIELD_ESTIMATES.items():
        q = _yf_quote(sym)
        eff = _nra_effective_yield(gross_yield, nra_rate)
        entry: Dict[str, Any] = {
            "symbol": sym,
            "gross_yield": gross_yield,
            "effective_yield": eff,
            "nra_rate_pct": round(nra_rate * 100, 0),
            "off_high": 0.0,
            "rsi_proxy": 50,
            "price": 0.0,
            "change_pct": 0.0,
            "hi52": 0.0,
            "lo52": 0.0,
            "type": "Covered-Call ETF"
            if sym in ("JEPI", "JEPQ", "DIVO")
            else "Dividend ETF"
            if sym in ("SCHD", "VYM", "HDV", "DGRO")
            else "Stock",
            "rate_sensitive": sym not in ("JEPI", "JEPQ", "DIVO", "ABBV", "KO", "PEP"),
        }
        if q:
            entry.update(
                {
                    "price": q["price"],
                    "change_pct": q["change_pct"],
                    "hi52": q["hi52"],
                    "lo52": q["lo52"],
                    "off_high": _off_high_pct(q),
                    "rsi_proxy": _rsi_proxy(q["change_pct"], q["hi52"], q["lo52"], q["price"]),
                }
            )
        results.append(entry)

    results.sort(key=lambda x: -x["effective_yield"])
    return _store("dividend_screen", results)


# ---------------------------------------------------------------------------
# 7. Swing candidate screener
# ---------------------------------------------------------------------------

SWING_UNIVERSE = [
    # Ticker, rough sector
    ("SOUN", "AI Voice"),
    ("CRML", "Rare Earths"),
    ("PENG", "AI Memory"),
    ("TRVI", "Biotech"),
    ("SNAP", "Social/Ad Tech"),
    ("CPRX", "Pharma M&A"),
    ("IONQ", "Quantum"),
    ("NNOX", "Medical Imaging"),
    ("RXRX", "AI Biotech"),
    ("CELH", "Consumer Health"),
    ("HOOD", "Fintech"),
    ("SOFI", "Fintech"),
    ("NN", "Navigation Tech"),
]

# Swing screen thresholds
_MAX_RSI_PROXY = 72  # avoid overbought
_MIN_OFF_HIGH = -60  # don't screen out stocks too far from high (may be falling knives)
_MAX_OFF_HIGH = -5  # must be below 52wk high — not already at top


def get_swing_screen(force: bool = False) -> List[Dict[str, Any]]:
    """
    Screen SWING_UNIVERSE for: RSI-proxy ≤ 72, 5-60% off 52wk high, price ≤ $50.
    Returns ranked list with score.
    """
    if not force:
        cached = _cached("swing_screen")
        if cached is not None:
            return cached

    results = []
    for sym, sector in SWING_UNIVERSE:
        q = _yf_quote(sym)
        if not q or not q["price"]:
            continue

        off_high = _off_high_pct(q)
        rsi_proxy = _rsi_proxy(q["change_pct"], q["hi52"], q["lo52"], q["price"])
        price_ok = q["price"] <= 50
        rsi_ok = rsi_proxy <= _MAX_RSI_PROXY
        off_high_ok = _MIN_OFF_HIGH <= off_high <= _MAX_OFF_HIGH

        # Simple composite score (higher = better setup)
        score = 0
        if rsi_ok:
            score += 40
        if off_high_ok:
            score += 30
        if price_ok:
            score += 20
        if q["change_pct"] > 0:
            score += 10  # positive momentum today

        results.append(
            {
                "symbol": sym,
                "sector": sector,
                "price": q["price"],
                "change_pct": q["change_pct"],
                "hi52": q["hi52"],
                "lo52": q["lo52"],
                "off_high": off_high,
                "rsi_proxy": rsi_proxy,
                "score": score,
                "passes": rsi_ok and off_high_ok,
                "flags": {
                    "rsi_ok": rsi_ok,
                    "off_high_ok": off_high_ok,
                    "price_ok": price_ok,
                },
            }
        )

    results.sort(key=lambda x: (-x["score"], x["off_high"]))
    return _store("swing_screen", results)


# ---------------------------------------------------------------------------
# 8. Unified "all intel" call  (single fetch for the macro page)
# ---------------------------------------------------------------------------


def get_all_intel(
    vix_value: Optional[float] = None,
    nra_rate: float = NRA_WITHHOLDING,
    holdings: Optional[List[str]] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Fetch all global intelligence layers in one call.
    Designed to be called from the /api/global-intel endpoint.
    Each sub-call uses its own cache so repeated hits are cheap.
    """
    peers_data = get_peers(holdings=holdings, force=force)
    return {
        "global_markets": get_global_markets(force=force),
        "sector_rotation": get_sector_rotation(force=force),
        "fear_greed": get_fear_greed(vix_value=vix_value, force=force),
        "yield_curve": get_yield_curve(force=force),
        "peers": peers_data["peers"],
        "peers_based_on": peers_data["based_on"],
        "dividend_screen": get_dividend_screen(nra_rate=nra_rate, force=force),
        "swing_screen": get_swing_screen(force=force),
    }
