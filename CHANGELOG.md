# Changelog

All notable changes to Silicon-Oracle will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Email validation on signup**: format check, disposable domain block (mailinator, yopmail, 35+ services), and MX record DNS lookup — fake/nonexistent domains rejected before account creation. Inline frontend feedback debounced at 700 ms via `/auth/validate-email`.
- **Email confirmation required**: users must verify their email before they can log in (Supabase confirmation flow). Unconfirmed login attempts show a clear error.
- **Duplicate email check**: signup checks `user_profiles` before calling Supabase auth, giving an explicit "already registered" message instead of a silent no-op.
- **US-only ticker enforcement**: non-US exchange suffixes (`.NS`, `.BO`, `.L`, `.DE`, etc.) are rejected at all API entry points with a clear error.
- **SPY benchmark label**: home page chart shows a `SPY · benchmark` pill when no sentinel portfolio history exists yet.
- **Simulation page 50/50 layout**: Performance History area chart and Allocation Donut chart displayed side-by-side (50/50 grid on desktop, stacked on mobile). Donut re-renders on every data refresh and supports hover labels showing per-position dollar value and % weight.
- **Portfolio page enhancements**:
  - **Today's P&L toggle** — switch between total unrealized P&L and today's intraday P&L on the portfolio summary card.
  - **Mini sparklines** in each position row showing recent price history at a glance.
  - **Allocation donut** on the portfolio page mirroring the Sentinel donut design.
- **Gemini-powered agent tool planning** (`AgentRuntime._gemini_plan_tools`): instead of pure keyword scoring, the agent now sends available tool names/descriptions to Gemini 2.0 Flash to decide which tools to call and with what arguments. Falls back to keyword routing if Gemini is unavailable.
- **Gemini synthesis step** (`AgentRuntime._gemini_synthesize`): after tool execution, Gemini writes a natural-language answer from the structured tool results. Falls back to a formatted text summary if Gemini is unavailable.

### Fixed
- `SUPABASE_SERVICE_KEY` validation — non-JWT values (e.g. `sb_secret_*`) are detected and rejected with a clear warning, falling back to anon key with an RLS notice.
- `update_user_profile` logs when UPDATE matches 0 rows (missing profile row).
- `save_user_api_keys` self-heals a missing profile row via admin API before updating.
- Password placeholder corrected to "Min 12 characters".
- Dot-stripping middleware no longer corrupts exchange suffixes in query params.
- Resolved unresolved git merge conflict markers committed into `flask_app/agent/runtime.py`, `flask_app/agent/execution_registry.py`, and `flask_app/services/agentic_intel_service.py` — all three files were restored to valid Python and re-committed.

### Performance
- `--preload` added to gunicorn: app initialises once before workers fork, eliminating per-request cold start.
- DB migrations moved to a background daemon thread — no longer block server startup.
- `pip3.11` used explicitly in Render build command.

---

## [3.0.0] - 2026-03-31

### Added
- **TradingView-Style UI**: Complete visual overhaul using TradingView dark palette (`#101010`/`#131722` backgrounds, `#00C853` gain, `#FF5252` loss, `#F0C060` gold)
- **Lightweight Charts v4**: Replaced Chart.js with TradingView's Lightweight Charts for financial charts
  - Area and candlestick series with period switcher (1D / 5D / 1M / 6M / 1Y)
  - Chart type toggle (line ↔ candlestick) without page reload
  - Correct cache-keying per ticker + period + chart type
- **Public Demo Page**: Full live demo at `/demo` — no account required
  - Oracle analysis, chart, news, technicals, and factor breakdown
  - Technical Indicators strip in left column below chart
- **Agent Orchestration Module** (`flask_app/agent/`):
  - `AgentRuntime` — keyword-scored tool-call routing loop
  - `ExecutionRegistry` — typed `AgentTool` / `AgentCommand` registry with real service handlers
  - `ToolPermissionContext` — deny-list permission gating by name and prefix
  - `AgentSession` / `AgentTurnResult` dataclasses for structured turn output
- **Trading Profile System**: Day / Swing / Long-Term profiles that adapt all AI outputs
  - Deep-dive analysis, Oracle factor interpretations, email content, backtesting defaults, and rebalancer thresholds all respond to trading style
- **AI Market Intelligence**: Automated hourly email alerts via Gemini 2.0 Flash with Google Search grounding
  - Personalized BUY/HOLD/SELL recommendations with confidence scores
  - Portfolio impact analysis with Oracle-based stop-loss suggestions
  - Market catalysts with clickable source links
  - Watchlist generation for emerging opportunities
  - TL;DR summaries and portfolio health metrics
- **Market Preview & Close Summary**: Pre-market heads-up at 9 AM and end-of-day recap at 5 PM (Mon–Fri)
- **Portfolio Sentinel Monitor**: Real-time position monitoring every 5 minutes during market hours
- **Portfolio Rebalancer**: Style-aware rebalancing thresholds and drift analysis
- **Backtesting Engine**: Style-matched defaults, historical P&L simulation
- **Macro Intelligence Service**: Geopolitical and macro event monitoring
  - Free RSS sources (BBC, Reuters, Al Jazeera, MarketWatch, CNBC, Fed)
  - Sector impact scoring and trade suggestion generation
  - Risk-profile-aware BUY/SELL suggestions
- **Command Center**: Chat-style interface with agent tool routing
- **Insider Transaction Tracker**: Normalized Finnhub insider trade data (S-Sale / P-Purchase / A-Award)
- **Sector Heatmap & Rotation Components**: Visual sector performance tracking
- **Earnings Calendar Component**: Upcoming earnings dates
- **Correlation Matrix Component**: Asset correlation visualization
- **Manual Job Trigger**: `/api/jobs/trigger/:job_name` for testing scheduled jobs
- **mypy Type Safety**: Full mypy compliance across all modules with pre-commit hook
- **Docker Non-Root User**: Production container now runs as `appuser` (non-root)
- **build-docker.yml**: GitHub Actions workflow to build and push Docker image to GHCR on release tags
- **docs/API.md**: Full API reference for all endpoints
- **docs/ARCHITECTURE.md**: Detailed architecture documentation with data flow diagrams
- **tests/test_services.py**: 21 additional pytest tests covering services and agent module

### Changed
- `pyproject.toml` version bumped to `3.0.0`
- `@cache.memoize` on `/api/demo/chart` replaced with explicit `cache.get/set` keyed on `ticker + period + candle` to correctly cache per query params
- `build_execution_registry()` now accepts `extra_tools` and `extra_commands` for extensibility
- `StockService._get_yfinance_quote` return type corrected to `Optional[Dict[str, Any]]`
- `create_secure_permission_context` uses `tuple[str, ...]` internally for deny prefixes
- Watchlist handler in agent module correctly converts `List[Dict]` from database to `Dict` for merging
- Market pre-market hours boundary corrected (pre-market ends at 9:00 AM, not 9:30 AM)
- `upload-artifact` GitHub Action upgraded from v3 to v4 (v3 deprecated)

### Fixed
- Blinking dot on Market Collections: was incorrectly animating only the first collection (AI/Tech); removed per-item animation
- Demo chart: `setChartType` and `changePeriod` now call `initChart()` as guard before reload
- Demo chart: applies `visible: false` + `setData([])` on both series before switching type
- Homepage chart rendering, positioning, and error handling
- Template rendering errors across multiple pages
- Signup error message now provides actionable guidance when Supabase email confirmation fails
- Auth route improvements for email confirmation failure detection

### Security
- All service files fully mypy-typed — no implicit `Optional` defaults
- Dockerfile runs as non-root `appuser`
- `types-pytz` and `types-requests` added to dev dependencies

### Removed
- Stale `streamlit` optional dependency block from `pyproject.toml`
- `py313` from black `target-version` (not supported by installed version)
- Unused `COMPLETION_SUMMARY.md`, `NEXT_STEPS.md`, `QUICK_REFERENCE.txt`
- `Co-Authored-By` lines removed from entire git history

---

## [2.1.0] - 2025-03-31

### Added
- **Live Backend Integration**: Connected homepage to live Supabase backend
  - Account overview with real position data
  - Active watchlists loaded from database
  - Live activity feed
- **LightweightCharts v4 API**: Updated charting library for better performance
  - Candlestick charts with multiple timeframes
  - Volume bars with customizable indicators
  - Touch-friendly mobile controls
- **Portfolio-Aware AI**: Gemini now has access to user portfolios
  - Context-aware stock recommendations
  - Position-specific insights
  - Risk analysis based on actual holdings
- **UI Refinements**: Oracle color tokens, macro dashboard enhancements

### Changed
- Shadow portfolio now used exclusively for all portfolio stats (read-only)
- Improved navigation sync across all pages
- Enhanced macro dashboard with revised color scheme

### Fixed
- Fixed API integration issues with live Supabase backend
- Corrected period mapping for multi-timeframe charts
- Resolved Oracle color token inheritance in components

---

## [2.0.0] - 2025-01-30

### Added
- **Complete Flask Rewrite**: Professional web UI replacing Streamlit
  - Responsive Tailwind CSS design
  - Modern component library
- **Advanced Scanner**: Stock screening with 15+ technical indicators
  - Custom filters (price, volume, PE ratio, etc.)
  - Alert thresholds
- **Macro Dashboard**: Real-time macro indicators
  - Treasury yields, VIX, inflation rates
  - Oil/gold/crypto prices
- **Portfolio Management**: Full position tracking with P&L
- **AI Integration**: Gemini integration for natural language stock queries
- **Paper Trading**: Alpaca integration with buy/sell orders
- **Email Notifications**: APScheduler + Gmail SMTP
- **Database**: Supabase PostgreSQL with multi-user support and encrypted API key storage

### Changed
- Migrated from SQLite to PostgreSQL (Supabase)
- Updated yfinance to v1.0+ (curl_cffi support)

### Security
- AES-256 (Fernet) encryption for stored API keys
- BYOK model for user data privacy
- CSRF protection enabled
- Rate limiting on sensitive endpoints

---

## [1.0.0] - 2024-Q4

### Added
- **Initial Streamlit Release**
  - Stock data retrieval (yfinance)
  - Technical analysis (pandas-ta)
  - Sentiment analysis (transformers)
  - Backtesting engine
  - Paper trading simulation (Alpaca)
  - News aggregation (feedparser)

### Known Limitations
- Single-user (no authentication)
- SQLite database (no cloud backup)
- No API key encryption
- Manual data refresh (no scheduling)

---

## [0.1.0] - 2024-Q3

### Added
- Early beta: core market data, technical indicators, basic Plotly charting

---

## Migration Guide

### v2.1 → v3.0

No breaking changes to the database schema. Update dependencies and restart:

```bash
pip install -r requirements.txt
python run_flask.py
```

New environment variables (all optional):
- No new required env vars in v3.0

### v1.0 → v2.0

```bash
cp .env.example .env
# Add SUPABASE_URL and SUPABASE_SERVICE_KEY
python run_flask.py
```

---

## How to Report Issues

- **Bug**: [GitHub Issues](https://github.com/HarshShroff/Silicon-Oracle/issues)
- **Security**: harshrofff@gmail.com (see [SECURITY.md](SECURITY.md))
- **Feature Request**: [GitHub Discussions](https://github.com/HarshShroff/Silicon-Oracle/discussions)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.
