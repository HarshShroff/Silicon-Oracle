"""
Silicon Oracle - Macro Intelligence Service
Real-time geopolitical & macro event monitoring with AI-powered trade implications.
Sources: GDELT 2.0 (free, no key), RSS feeds (Reuters/BBC/Fed/Al Jazeera), Finnhub
"""

import json
import logging
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Module-level event cache — RSS+Gemini results shared across all users/source modes
_event_cache: Dict[str, Any] = {"data": None, "expires": 0.0}
EVENT_CACHE_TTL = 1800  # 30 minutes

# Free RSS feeds — no API key needed, no rate limits
RSS_FEEDS = [
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("Federal Reserve", "https://www.federalreserve.gov/feeds/press_all.xml"),
    ("MarketWatch", "https://feeds.marketwatch.com/marketwatch/topstories/"),
    (
        "CNBC Economy",
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
    ),
    (
        "CNBC Finance",
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
    ),
    ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
]

# Sector ETF universe for trade suggestions
SECTOR_ETF_MAP = {
    "energy": {"tickers": ["XLE", "XOM", "CVX", "OXY"], "name": "Energy"},
    "defense": {"tickers": ["ITA", "LMT", "RTX", "NOC"], "name": "Defense"},
    "technology": {"tickers": ["XLK", "SMH", "SOXX", "QQQ"], "name": "Technology"},
    "financials": {"tickers": ["XLF", "JPM", "GS"], "name": "Financials"},
    "healthcare": {"tickers": ["XLV", "JNJ", "UNH"], "name": "Healthcare"},
    "gold": {"tickers": ["GLD", "GDX", "IAU"], "name": "Gold / Metals"},
    "bonds": {"tickers": ["TLT", "IEF", "AGG"], "name": "Bonds"},
    "consumer_staples": {"tickers": ["XLP", "WMT", "PG"], "name": "Consumer Staples"},
    "consumer_discretionary": {"tickers": ["XLY", "AMZN", "TGT"], "name": "Consumer Discretionary"},
    "utilities": {"tickers": ["XLU", "NEE", "DUK"], "name": "Utilities"},
    "real_estate": {"tickers": ["VNQ", "O", "AMT"], "name": "Real Estate"},
    "crypto": {"tickers": ["MSTR", "COIN", "IBIT"], "name": "Crypto-linked"},
}

# Ticker → sector lookup for portfolio impact mapping
TICKER_SECTOR_MAP = {
    "XLE": "energy",
    "XOM": "energy",
    "CVX": "energy",
    "OXY": "energy",
    "COP": "energy",
    "SLB": "energy",
    "HAL": "energy",
    "MPC": "energy",
    "PSX": "energy",
    "VLO": "energy",
    "ITA": "defense",
    "LMT": "defense",
    "RTX": "defense",
    "NOC": "defense",
    "GD": "defense",
    "BA": "defense",
    "HII": "defense",
    "L3H": "defense",
    "XLK": "technology",
    "AAPL": "technology",
    "MSFT": "technology",
    "NVDA": "technology",
    "AMD": "technology",
    "INTC": "technology",
    "SMH": "technology",
    "SOXX": "technology",
    "QQQ": "technology",
    "TSM": "technology",
    "ASML": "technology",
    "META": "technology",
    "GOOGL": "technology",
    "GOOG": "technology",
    "XLF": "financials",
    "JPM": "financials",
    "GS": "financials",
    "BAC": "financials",
    "C": "financials",
    "WFC": "financials",
    "MS": "financials",
    "BRK-B": "financials",
    "AXP": "financials",
    "XLV": "healthcare",
    "JNJ": "healthcare",
    "PFE": "healthcare",
    "UNH": "healthcare",
    "ABBV": "healthcare",
    "MRK": "healthcare",
    "LLY": "healthcare",
    "TMO": "healthcare",
    "XLY": "consumer_discretionary",
    "AMZN": "consumer_discretionary",
    "TSLA": "consumer_discretionary",
    "HD": "consumer_discretionary",
    "UAL": "consumer_discretionary",
    "DAL": "consumer_discretionary",
    "AAL": "consumer_discretionary",
    "LUV": "consumer_discretionary",
    "XLP": "consumer_staples",
    "WMT": "consumer_staples",
    "PG": "consumer_staples",
    "KO": "consumer_staples",
    "PEP": "consumer_staples",
    "GLD": "gold",
    "GDX": "gold",
    "IAU": "gold",
    "GOLD": "gold",
    "TLT": "bonds",
    "IEF": "bonds",
    "AGG": "bonds",
    "BND": "bonds",
    "XLU": "utilities",
    "NEE": "utilities",
    "DUK": "utilities",
    "SO": "utilities",
    "VNQ": "real_estate",
    "O": "real_estate",
    "AMT": "real_estate",
    "SPG": "real_estate",
    "MSTR": "crypto",
    "COIN": "crypto",
    "IBIT": "crypto",
}

# Heuristic keyword → sector classification (fallback when Gemini unavailable)
SECTOR_KEYWORDS = {
    "energy": (
        ["oil", "opec", "gas", "energy", "petroleum", "crude", "pipeline", "lng"],
        "bullish",
    ),
    "defense": (
        ["war", "military", "conflict", "weapons", "nato", "army", "missile", "troops", "strike"],
        "bullish",
    ),
    "gold": (["gold", "safe haven", "uncertainty", "crisis", "recession fear"], "bullish"),
    "bonds": (
        ["fed", "rates", "interest", "treasury", "yield", "central bank", "monetary"],
        "neutral",
    ),
    "technology": (
        ["chip", "semiconductor", "ai", "tech", "software", "data center", "cloud"],
        "neutral",
    ),
    "financials": (["bank", "credit", "lending", "financial system", "fed rate"], "neutral"),
    "consumer_discretionary": (
        ["tariff", "consumer spending", "retail sales", "airline"],
        "neutral",
    ),
}


class MacroIntelService:
    """
    Real-time macro & geopolitical intelligence service.

    Pipeline:
      1. Fetch events from GDELT 2.0 + RSS feeds
      2. Classify events with Gemini AI (event type, affected sectors, confidence)
      3. Cross-reference with user's Alpaca/Sentinel positions for portfolio impact
      4. Generate Kelly-lite sized trade suggestions
    """

    def __init__(self, config: Optional[Dict[str, str]] = None):
        self.config = config or {}

    # ------------------------------------------------------------------
    # Data Ingestion
    # ------------------------------------------------------------------

    def fetch_rss_events(self) -> List[Dict[str, Any]]:
        """Fetch recent articles from free RSS feeds."""
        events = []
        for feed_name, feed_url in RSS_FEEDS:
            try:
                req = urllib.request.Request(
                    feed_url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (compatible; SiliconOracle/1.0)",
                        "Accept": "application/rss+xml, application/xml, text/xml, */*",
                    },
                )
                with urllib.request.urlopen(req, timeout=7) as resp:
                    content = resp.read()

                root = ET.fromstring(content)
                # Support both RSS 2.0 and Atom
                # ElementTree elements evaluate to False when they have no children,
                # so we must use explicit `is not None` checks everywhere.
                items = root.findall(".//item")
                if not items:
                    items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

                for item in items[:8]:
                    title_el = item.find("title")
                    if title_el is None:
                        title_el = item.find("{http://www.w3.org/2005/Atom}title")

                    link_el = item.find("link")
                    if link_el is None:
                        link_el = item.find("{http://www.w3.org/2005/Atom}link")

                    pub_el = item.find("pubDate")
                    if pub_el is None:
                        pub_el = item.find("{http://www.w3.org/2005/Atom}published")

                    title = (title_el.text or "").strip() if title_el is not None else ""
                    link = ""
                    if link_el is not None:
                        link = (link_el.text or link_el.get("href", "") or "").strip()
                    published = (pub_el.text or "").strip() if pub_el is not None else ""

                    if title:
                        events.append(
                            {
                                "title": title,
                                "url": link,
                                "source": feed_name,
                                "published_at": published,
                                "source_type": "rss",
                            }
                        )
            except Exception as e:
                logger.warning(f"RSS fetch failed for {feed_name}: {e}")
        return events

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def classify_events_with_gemini(self, raw_events: List[Dict]) -> List[Dict[str, Any]]:
        """Use Gemini to classify events and map to asset class impacts."""
        if not self.config.get("GEMINI_API_KEY") or not raw_events:
            return self._classify_events_heuristic(raw_events)

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.config["GEMINI_API_KEY"])

            event_list = "\n".join(
                [f"{i + 1}. [{e['source']}] {e['title']}" for i, e in enumerate(raw_events[:15])]
            )

            prompt = f"""Analyze these financial/geopolitical news headlines. Today: {datetime.now().strftime("%B %d, %Y")}.

Headlines:
{event_list}

For each headline return a JSON array. Each element must have:
{{
  "index": <1-based int>,
  "event_type": "geopolitical|macro_economic|central_bank|commodity|tech_sector|regulatory|other",
  "affected_sectors": [<list from: energy, defense, technology, financials, healthcare, gold, bonds, consumer_staples, consumer_discretionary, utilities, real_estate, crypto>],
  "sector_direction": {{"<sector>": "bullish"|"bearish"|"neutral"}},
  "confidence": <0-100 int>,
  "time_horizon": "intraday|days|weeks|months",
  "summary": "<one-sentence causal chain: what happened → why it matters → which assets move>",
  "severity": "low|medium|high"
}}

Rules:
- Only include sectors meaningfully affected (skip if impact is minimal)
- Confidence reflects how clearly the event maps to asset movement
- Return ONLY the JSON array, no markdown, no extra text"""

            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.1),
            )

            text = (response.text or "").strip()
            # Strip markdown code fences if present
            if "```" in text:
                parts = text.split("```")
                for part in parts:
                    stripped = part.strip()
                    if stripped.startswith("[") or stripped.startswith("json\n["):
                        text = stripped.replace("json\n", "")
                        break

            classifications = json.loads(text)

            classified = []
            for cls in classifications:
                idx = cls.get("index", 0) - 1
                if 0 <= idx < len(raw_events):
                    event = raw_events[idx].copy()
                    event.update(cls)
                    classified.append(event)
            return classified

        except Exception as e:
            logger.error(f"Gemini classification failed: {e}")
            return self._classify_events_heuristic(raw_events)

    def _classify_events_heuristic(self, events: List[Dict]) -> List[Dict]:
        """Fallback keyword-based classification when Gemini is unavailable."""
        classified = []
        for event in events:
            title_lower = event["title"].lower()
            affected_sectors = []
            sector_direction = {}

            for sector, (keywords, default_dir) in SECTOR_KEYWORDS.items():
                if any(kw in title_lower for kw in keywords):
                    affected_sectors.append(sector)
                    sector_direction[sector] = default_dir

            event_copy = event.copy()
            event_copy.update(
                {
                    "event_type": "other",
                    "affected_sectors": affected_sectors or [],
                    "sector_direction": sector_direction,
                    "confidence": 35,
                    "time_horizon": "days",
                    "summary": event["title"],
                    "severity": "low",
                }
            )
            classified.append(event_copy)
        return classified

    # ------------------------------------------------------------------
    # Portfolio Impact
    # ------------------------------------------------------------------

    def get_portfolio_impact(
        self,
        classified_events: List[Dict],
        positions: List[Dict],
    ) -> List[Dict[str, Any]]:
        """Cross-reference classified events with user's current Alpaca holdings."""
        impacts = []

        for event in classified_events:
            affected_sectors = event.get("affected_sectors", [])
            sector_direction = event.get("sector_direction", {})

            impacted_positions = []
            for pos in positions:
                ticker = pos.get("ticker", "")
                sector = TICKER_SECTOR_MAP.get(ticker)
                if sector and sector in affected_sectors:
                    direction = sector_direction.get(sector, "neutral")
                    impacted_positions.append(
                        {
                            "ticker": ticker,
                            "sector": sector,
                            "direction": direction,
                            "market_value": round(float(pos.get("market_value", 0)), 2),
                            "unrealized_pl": round(float(pos.get("unrealized_pl", 0)), 2),
                        }
                    )

            if impacted_positions or event.get("severity") in ("high",):
                impacts.append(
                    {
                        **event,
                        "impacted_positions": impacted_positions,
                        "has_portfolio_exposure": len(impacted_positions) > 0,
                    }
                )

        # Sort: most portfolio exposure first, then by confidence
        impacts.sort(key=lambda x: (-len(x.get("impacted_positions", [])), -x.get("confidence", 0)))
        return impacts

    # ------------------------------------------------------------------
    # Trade Suggestions
    # ------------------------------------------------------------------

    # Risk-profile config
    _RISK_CONFIG = {
        "conservative": {
            "max_kelly": 0.05,  # max 5% per trade
            "min_confidence": 70,
            "ticker_index": 0,  # prefer ETFs (index 0 = broadest ETF)
            "horizon_ok": {"days", "weeks", "months"},
            "label": "Conservative",
        },
        "moderate": {
            "max_kelly": 0.10,
            "min_confidence": 55,
            "ticker_index": 0,
            "horizon_ok": {"intraday", "days", "weeks", "months"},
            "label": "Moderate",
        },
        "aggressive": {
            "max_kelly": 0.15,
            "min_confidence": 50,
            "ticker_index": 1,  # prefer single stocks (index 1+)
            "horizon_ok": {"intraday", "days", "weeks", "months"},
            "label": "Aggressive",
        },
    }

    # Trading-style time-horizon preference
    _STYLE_HORIZON = {
        "day_trading": {"intraday", "days"},
        "swing_trading": {"days", "weeks"},
        "long_term": {"weeks", "months"},
    }

    def get_trade_suggestions(
        self,
        classified_events: List[Dict],
        account: Optional[Dict],
        positions: List[Dict],
        oracle_scores: Dict[str, int],
        risk_profile: str = "moderate",
        trading_style: str = "swing_trading",
    ) -> List[Dict[str, Any]]:
        """
        Generate actionable trade suggestions personalised to the user's risk profile,
        trading style, and current holdings.

        Rules:
        - BUY:  bullish sector + matches trading horizon → suggest sector ETF or held ticker
        - SELL: bearish sector → ONLY suggest selling a ticker the user ACTUALLY holds
        - Risk profile controls Kelly cap, confidence threshold, and ticker aggressiveness
        - Trading style filters events by time horizon (day / swing / long-term)
        - Current holdings:
            * If already exposed to the sector on a BUY → halve Kelly (adding, not replacing)
            * Suggest the ticker they already own rather than a new one where possible
        """
        risk_cfg = self._RISK_CONFIG.get(risk_profile, self._RISK_CONFIG["moderate"])
        style_ok = self._STYLE_HORIZON.get(trading_style, self._STYLE_HORIZON["swing_trading"])
        min_conf = risk_cfg["min_confidence"]
        max_kelly = risk_cfg["max_kelly"]
        tk_idx = risk_cfg["ticker_index"]

        # Build portfolio value from account or fall back to sum of sentinel market values
        portfolio_value = 0.0
        buying_power = 0.0
        if account:
            portfolio_value = float(account.get("portfolio_value", 0))
            buying_power = float(account.get("buying_power", 0))
        if portfolio_value <= 0 and positions:
            portfolio_value = sum(float(p.get("market_value", 0)) for p in positions)
            buying_power = portfolio_value

        if portfolio_value <= 0:
            return []

        # Map: sector → list of positions the user holds in that sector
        held_by_sector: Dict[str, List[Dict]] = {}
        for pos in positions:
            ticker = pos.get("ticker", "")
            sector = TICKER_SECTOR_MAP.get(ticker)
            if sector:
                held_by_sector.setdefault(sector, []).append(pos)

        suggestions = []
        seen_suggest_keys: set = set()  # (action, ticker)

        for event in classified_events[:10]:
            confidence = event.get("confidence", 50)
            if confidence < min_conf:
                continue

            # Horizon mismatch → reduce Kelly by half instead of skipping entirely.
            # (Macro events are often "weeks/months" but a swing trader can still act.)
            horizon = event.get("time_horizon", "days")
            horizon_penalty = 1.0 if horizon in style_ok else 0.5

            sector_direction = event.get("sector_direction", {})

            for sector, direction in sector_direction.items():
                if direction == "neutral":
                    continue

                sector_info = SECTOR_ETF_MAP.get(sector)
                if not sector_info:
                    continue

                held_in_sector = held_by_sector.get(sector, [])
                already_exposed = bool(held_in_sector)

                # ── SELL ──────────────────────────────────────────────────────
                if direction == "bearish":
                    if not held_in_sector:
                        continue  # never SELL what you don't own

                    for held_pos in held_in_sector:
                        sell_ticker = held_pos.get("ticker", "")
                        if not sell_ticker:
                            continue
                        key = ("SELL", sell_ticker)
                        if key in seen_suggest_keys:
                            continue
                        seen_suggest_keys.add(key)

                        oracle_score = oracle_scores.get(sell_ticker, 50)
                        kelly_fraction = (
                            (confidence / 100) * (oracle_score / 100) * max_kelly * horizon_penalty
                        )
                        kelly_fraction = max(0.01, min(max_kelly, kelly_fraction))

                        pos_value = float(held_pos.get("market_value", 0))
                        dollar_amount = round(min(pos_value * kelly_fraction * 10, pos_value), 2)

                        # No hard minimum — tiny portfolios still get valid % guidance

                        confidence_tier = (
                            "HIGH" if confidence >= 75 else "MEDIUM" if confidence >= 60 else "LOW"
                        )

                        suggestions.append(
                            {
                                "action": "SELL",
                                "ticker": sell_ticker,
                                "sector": sector_info["name"],
                                "dollar_amount": dollar_amount,
                                "allocation_pct": round(kelly_fraction * 100, 1),
                                "confidence": confidence,
                                "confidence_tier": confidence_tier,
                                "oracle_score": oracle_score,
                                "time_horizon": horizon,
                                "reasoning": event.get("summary", event.get("title", "")),
                                "event_title": event.get("title", ""),
                                "event_source": event.get("source", ""),
                                "already_exposed": True,
                                "severity": event.get("severity", "medium"),
                                "trade_url": f"/trade/{sell_ticker}",
                                "risk_profile": risk_cfg["label"],
                                "trading_style": trading_style,
                            }
                        )

                # ── BUY ───────────────────────────────────────────────────────
                else:
                    # Pick ticker: held > profile-preferred index > ETF
                    if held_in_sector:
                        buy_ticker = held_in_sector[0].get("ticker", sector_info["tickers"][0])
                    else:
                        # aggressive → prefer single stock; conservative → ETF
                        pick_idx = min(int(str(tk_idx)), len(sector_info["tickers"]) - 1)
                        buy_ticker = sector_info["tickers"][pick_idx]

                    key = ("BUY", buy_ticker)
                    if key in seen_suggest_keys:
                        continue
                    seen_suggest_keys.add(key)

                    oracle_score = oracle_scores.get(buy_ticker, 50)
                    kelly_fraction = (confidence / 100) * (oracle_score / 100) * max_kelly
                    kelly_fraction = max(0.01, min(max_kelly, kelly_fraction))

                    # Already holds sector → halve (adding to, not initiating)
                    if already_exposed:
                        kelly_fraction *= 0.5

                    dollar_amount = portfolio_value * kelly_fraction
                    dollar_amount = min(dollar_amount, buying_power * 0.9)
                    dollar_amount = round(dollar_amount, 2)

                    # No hard minimum — tiny portfolios still get valid % guidance

                    confidence_tier = (
                        "HIGH" if confidence >= 75 else "MEDIUM" if confidence >= 60 else "LOW"
                    )

                    suggestions.append(
                        {
                            "action": "BUY",
                            "ticker": buy_ticker,
                            "sector": sector_info["name"],
                            "dollar_amount": dollar_amount,
                            "allocation_pct": round(kelly_fraction * 100, 1),
                            "confidence": confidence,
                            "confidence_tier": confidence_tier,
                            "oracle_score": oracle_score,
                            "time_horizon": horizon,
                            "reasoning": event.get("summary", event.get("title", "")),
                            "event_title": event.get("title", ""),
                            "event_source": event.get("source", ""),
                            "already_exposed": already_exposed,
                            "severity": event.get("severity", "medium"),
                            "trade_url": f"/trade/{buy_ticker}",
                            "risk_profile": risk_cfg["label"],
                            "trading_style": trading_style,
                        }
                    )

        # Sort: HIGH confidence first, BUYs before SELLs within same tier
        suggestions.sort(
            key=lambda x: (
                0
                if x["confidence_tier"] == "HIGH"
                else 1
                if x["confidence_tier"] == "MEDIUM"
                else 2,
                0 if x["action"] == "BUY" else 1,
                -x["confidence"],
            )
        )
        return suggestions[:10]

    # ------------------------------------------------------------------
    # Full Pipeline
    # ------------------------------------------------------------------

    def get_classified_events(self, force_refresh: bool = False) -> List[Dict]:
        """
        Fetch + classify events. Results cached 30 min (module-level, all users share it).
        Call with force_refresh=True to bust the cache.
        """
        global _event_cache

        now = time.time()
        if not force_refresh and _event_cache["data"] is not None and now < _event_cache["expires"]:
            logger.info("Returning cached macro events")
            return _event_cache["data"]

        # Fetch
        raw_events: List[Dict] = []
        try:
            raw_events.extend(self.fetch_rss_events())
        except Exception as e:
            logger.error(f"RSS ingestion error: {e}")

        if not raw_events:
            return []

        # Deduplicate
        seen_titles: set = set()
        unique_events: List[Dict] = []
        for event in raw_events:
            key = event["title"][:70].lower().strip()
            if key and key not in seen_titles:
                seen_titles.add(key)
                unique_events.append(event)

        # Classify
        classified = self.classify_events_with_gemini(unique_events[:20])
        classified = [e for e in classified if e.get("affected_sectors")]

        _event_cache["data"] = classified
        _event_cache["expires"] = now + EVENT_CACHE_TTL
        return classified

    def run_full_analysis(
        self,
        positions: List[Dict],
        account: Optional[Dict],
        oracle_scores: Optional[Dict[str, int]] = None,
        force_refresh: bool = False,
        risk_profile: str = "moderate",
        trading_style: str = "swing_trading",
    ) -> Dict[str, Any]:
        """
        Complete pipeline using cached events + fresh position data.
        Returns data for all three dashboard panels.
        """
        oracle_scores = oracle_scores or {}

        classified = self.get_classified_events(force_refresh=force_refresh)

        if not classified:
            return {
                "events": [],
                "portfolio_impact": [],
                "trade_suggestions": [],
                "last_updated": datetime.utcnow().isoformat(),
                "sources": [],
                "error": "No events fetched from any source",
            }

        portfolio_impact = self.get_portfolio_impact(classified, positions)
        trade_suggestions = self.get_trade_suggestions(
            classified,
            account,
            positions,
            oracle_scores,
            risk_profile=risk_profile,
            trading_style=trading_style,
        )
        sources = list({e.get("source", "") for e in classified if e.get("source")})

        return {
            "events": classified[:15],
            "portfolio_impact": portfolio_impact[:10],
            "trade_suggestions": trade_suggestions,
            "last_updated": datetime.utcnow().isoformat(),
            "unique_events_classified": len(classified),
            "sources": sources,
        }
