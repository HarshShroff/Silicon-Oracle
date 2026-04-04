# Silicon Oracle — Architecture

## Overview

Silicon Oracle is a multi-user, cloud-native stock analysis and paper trading platform. The backend is a Flask application with a service-oriented architecture; the frontend is server-rendered Jinja2 templates enhanced with Alpine.js reactivity and Lightweight Charts for financial visualization.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (Client)                      │
│  Jinja2 Templates + Alpine.js + Lightweight Charts v4    │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP / SSE
┌──────────────────────▼──────────────────────────────────┐
│                  Flask Application                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │  main.py │ │  api.py  │ │  auth.py │ │sentinel.py│  │
│  │  (pages) │ │  (JSON)  │ │  (login) │ │ (monitor) │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────┘  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │                  Services Layer                     │ │
│  │  StockService  OracleService  TradingService        │ │
│  │  PortfolioService  AlertEngine  EmailService        │ │
│  │  MacroIntelService  ScannerService  AgentRuntime    │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│  │ APScheduler│  │  Flask-Cache │  │  utils/database │ │
│  │ (cron jobs)│  │  (Redis/mem) │  │  (Supabase ORM) │ │
│  └────────────┘  └──────────────┘  └─────────────────┘ │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                  External Services                       │
│  Finnhub (quotes)   Alpaca (paper trading)               │
│  Google Gemini (AI) yfinance (history)                   │
│  Google News RSS    Supabase (database + auth)           │
└─────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
Silicon-Oracle/
├── flask_app/
│   ├── __init__.py          # App factory (create_app)
│   ├── config.py            # Config classes (Dev/Prod/Test)
│   ├── routes/
│   │   ├── main.py          # Page routes (/, /demo, /portfolio, ...)
│   │   ├── api.py           # JSON API endpoints (/api/*)
│   │   ├── auth.py          # Auth routes (/auth/login, /auth/signup)
│   │   ├── sentinel.py      # Sentinel monitor API
│   │   └── sentinel_ui.py   # Sentinel dashboard pages
│   ├── services/
│   │   ├── stock_service.py         # Finnhub + yfinance market data
│   │   ├── oracle_service.py        # 15-factor Oracle scoring
│   │   ├── enhanced_oracle_service.py  # Extended scoring + volume spikes
│   │   ├── trading_service.py       # Alpaca paper trading
│   │   ├── portfolio_service.py     # Portfolio tracking + P&L
│   │   ├── alert_engine.py          # Price alert logic
│   │   ├── email_service.py         # Gmail SMTP notifications
│   │   ├── scanner_service.py       # Watchlist scanning
│   │   ├── macro_intel_service.py   # Geopolitical + macro events
│   │   ├── market_intelligence_service.py  # AI-powered market analysis
│   │   ├── news_intelligence_service.py    # News sentiment
│   │   ├── notifications_service.py        # Scheduled email jobs
│   │   └── market_data.py           # Market data aggregator
│   ├── agent/
│   │   ├── runtime.py               # AgentRuntime — tool-call loop
│   │   ├── execution_registry.py    # Tool/command registry + handlers
│   │   ├── permissions.py           # Permission-gated tool blocking
│   │   └── session_store.py         # JSON-persisted session store
│   ├── models/
│   │   └── user.py                  # User model
│   ├── templates/
│   │   ├── layouts/                 # base.html, auth_base.html
│   │   ├── pages/                   # Full page templates
│   │   └── components/              # Reusable partial templates
│   └── static/
│       ├── css/tailwind.css         # Compiled Tailwind output
│       └── js/                      # Custom JS modules
├── utils/
│   ├── database.py          # Supabase client + CRUD helpers
│   ├── encryption.py        # Fernet key encryption for API keys
│   └── ticker_utils.py      # Ticker validation and normalization
├── tests/
│   └── test_basic.py        # Pytest test suite
├── docs/
│   ├── API.md               # API reference
│   └── ARCHITECTURE.md      # This file
├── .github/
│   ├── workflows/
│   │   ├── tests.yml        # CI: lint + test
│   │   ├── release.yml      # CD: GitHub release on tag
│   │   └── build-docker.yml # CD: Docker build + push on tag
│   └── CODEOWNERS
├── run_flask.py             # Dev server entry point
├── Dockerfile               # Production container
├── render.yaml              # Render.com deployment blueprint
├── pyproject.toml           # Package metadata + tool config
├── requirements.txt         # Pinned runtime dependencies
└── requirements-dev.txt     # Dev/test dependencies
```

---

## Key Design Decisions

### BYOK (Bring Your Own Keys)
Each user provides and stores their own API keys (Finnhub, Alpaca, Gemini, Gmail). Keys are encrypted at rest using Fernet symmetric encryption before storage in Supabase. This means:
- No shared rate limits between users
- The app operator never needs API keys for market data or AI
- Users have full control over their API quota

### Auth & Signup Validation
Signup enforces three layers before creating an account:
1. **Format + length** — username ≥ 3 chars, password ≥ 12, email regex
2. **Email quality** — disposable domain blocklist (35+ services) + MX DNS record lookup via `dnspython`
3. **Duplicate check** — queries `user_profiles` before calling Supabase auth (Supabase silently reuses existing users on duplicate when confirmation is enabled)

When email confirmation is enabled in Supabase, no session is created on signup — the user must click the confirmation link first.

### US-Only Ticker Constraint
All user-facing ticker inputs in `api.py` are validated against a set of known non-US exchange suffixes (`.NS`, `.BO`, `.L`, `.DE`, `.HK`, etc.) and rejected with a clear error. The app relies on Finnhub (US-only on free tier) and Alpaca (US equities only) — non-US tickers would silently return empty data.

### Service Layer
All business logic lives in `flask_app/services/`. Routes are thin — they validate input, call services, and return responses. Services are stateless and instantiated per-request where possible, or held as module-level singletons for connection-heavy clients (Finnhub, Alpaca).

### Oracle Score™
A proprietary 15-factor scoring system implemented in `oracle_service.py`. Factors include: RSI position, SMA trend, volume analysis, earnings proximity, analyst consensus, price momentum, and more. Each factor returns a score 0–1; the aggregate drives BUY/HOLD/SELL verdicts.

### Agent Module
`flask_app/agent/` implements a lightweight tool-routing loop:
- `ExecutionRegistry` holds named `AgentTool` objects with typed handlers
- `AgentRuntime` scores prompts against tool names/descriptions, filters by `ToolPermissionContext`, and executes the top matches
- Used by the Command Center chat interface

### Scheduled Jobs (APScheduler)
Jobs run on UTC schedule via APScheduler. All jobs are per-user and fire conditionally on user preferences (stored in Supabase). Jobs are also manually triggerable via `/api/jobs/trigger/:name`.

### Caching
Flask-Caching with in-memory backend (configurable to Redis). Cache keys for API endpoints explicitly include all query parameters to avoid stale data — e.g., `demo_chart_{ticker}_{period}_{candle}`.

---

## Data Flow: Stock Analysis Request

```
User clicks "Analyze AAPL"
  → GET /api/stock/analysis?ticker=AAPL
  → api.py route handler
  → _is_non_us_ticker("AAPL") → False (passes)
  → OracleService.calculate_oracle_score("AAPL")
      → StockService.get_complete_data("AAPL")  [parallel via ThreadPoolExecutor]
          → Finnhub quote
          → yfinance history
          → company info
          → technicals (RSI, SMA, volatility)
          → earnings, news, peers, insiders
      → Score 15 factors
      → Return { score, verdict, factors, quote, company }
  → JSON response to frontend
  → Alpine.js renders Oracle card
```

---

## Deployment Targets

| Target | Config | Notes |
|--------|--------|-------|
| **Render** | `render.yaml` | Recommended; free tier available |
| **Docker** | `Dockerfile` | Multi-stage, non-root user |
| **Local** | `run_flask.py` | Dev server on port 5001 |
| **Railway/Fly.io** | Manual | Use Dockerfile |
