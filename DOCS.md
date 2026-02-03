# Silicon Oracle — Developer & User Documentation

> Complete reference for every page, every API endpoint, and how the system works end-to-end.

---

## Table of Contents

1. [Architecture at a Glance](#1-architecture-at-a-glance)
2. [BYOK (Bring Your Own Keys)](#2-byok-bring-your-own-keys)
3. [Trading Profile — the style that adapts everything](#3-trading-profile)
4. [Pages](#4-pages)
   - [Login & Signup](#41-login--signup)
   - [Analysis](#42-analysis)
   - [AI Guidance](#43-ai-guidance)
   - [Scanner](#44-scanner)
   - [Portfolio](#45-portfolio)
   - [Trade](#46-trade)
   - [Watchlist](#47-watchlist)
   - [Settings](#48-settings)
   - [Portfolio Sentinel (Simulation)](#49-portfolio-sentinel--simulation)
5. [API Endpoints](#5-api-endpoints)
   - [Stock Data](#51-stock-data)
   - [Oracle & AI](#52-oracle--ai)
   - [Scanner & Watchlists](#53-scanner--watchlists)
   - [Trading (Alpaca)](#54-trading--alpaca)
   - [Portfolio](#55-portfolio)
   - [Notifications & Email](#56-notifications--email)
   - [Settings](#57-settings)
   - [Market Intelligence](#58-market-intelligence)
   - [Advanced Analytics](#59-advanced-analytics)
   - [Sentinel (Position Management)](#510-sentinel-position-management)
   - [Sentinel UI (Dashboard Data)](#511-sentinel-ui--dashboard-data)
6. [Background Email Jobs](#6-background-email-jobs)
7. [Manually Triggering Email Jobs (Testing)](#7-manually-triggering-email-jobs)
8. [Database Schema](#8-database-schema)
9. [Key Design Decisions](#9-key-design-decisions)

---

## 1. Architecture at a Glance

```
┌────────────────────────────────────────────────────────────┐
│                        Browser                             │
│   Jinja2 pages  ←→  Alpine.js AJAX  ←→  Chart.js charts   │
└───────────────────────────┬────────────────────────────────┘
                            │ HTTP
┌───────────────────────────▼────────────────────────────────┐
│                     Flask (Gunicorn)                        │
│                                                            │
│  Blueprints                                                │
│    auth_bp      – login / signup / logout                  │
│    main_bp      – page rendering (SSR)                     │
│    api_bp       – AJAX JSON endpoints                      │
│    sentinel_bp  – position add / sync                      │
│    sentinel_ui_bp – dashboard data & bulk import           │
│                                                            │
│  Services                                                  │
│    StockService         – Finnhub quotes & charts          │
│    OracleService        – 12-factor quantitative score     │
│    EnhancedOracleService– 15-factor score (adds 3 more)    │
│    GeminiService        – Gemini AI deep-dive & insights   │
│    ScannerService       – multi-ticker parallel scan       │
│    TradingService       – Alpaca paper-trade orders        │
│    PortfolioService     – trade history & P&L              │
│    MarketIntelligenceService – email content generation    │
│    AlertEngine          – threshold-based alerts           │
│    SentinelEngine       – background position monitor      │
│    EmailService         – SMTP via user's Gmail            │
│                                                            │
│  APScheduler            – 5 cron jobs (see §6)            │
└───────────────┬──────────────────┬─────────────────────────┘
                │                  │
     ┌──────────▼──┐    ┌─────────▼─────────┐
     │  Supabase   │    │  External APIs     │
     │ PostgreSQL  │    │  Finnhub (data)    │
     │             │    │  Alpaca (trades)   │
     │  user data  │    │  Gemini (AI)       │
     │  positions  │    │  yfinance (hist)   │
     │  API keys   │    │  Gmail (email)     │
     └─────────────┘    └────────────────────┘
```

**Request flow (typical AJAX call):**
1. Alpine.js `fetch()` hits `/api/…`
2. Flask middleware (`__init__.py`) loads `g.user` from the session cookie
3. Route handler calls `get_config()` → pulls the user's own decrypted API keys from Supabase
4. Service layer calls the external API (Finnhub / Gemini / Alpaca)
5. JSON response returns to the browser; Alpine.js updates the DOM reactively

---

## 2. BYOK (Bring Your Own Keys)

Silicon Oracle does **not** hold any shared API keys. Every user brings their own:

| Key | Used by | Required? |
|-----|---------|-----------|
| **Finnhub API Key** | Stock quotes, news, company info | Yes |
| **Alpaca API + Secret** | Paper-trading orders & positions | Optional |
| **Gemini API Key** | All AI analysis, email content | Optional (locks AI features) |
| **Gmail Address + App Password** | Sending alert emails | Optional (locks email features) |

Keys are **encrypted at rest** in Supabase using Fernet symmetric encryption (`utils/encryption.py`). They are decrypted only at request time via `db.get_user_api_keys(user_id, decrypt=True)`.

The Gmail App Password is masked in the UI (`***xxxx`) after it is saved — it is never sent back to the frontend in plain text.

---

## 3. Trading Profile

Each user picks one of three trading styles in **Settings → Trading Profile**:

| Style | Meaning | How it affects the app |
|-------|---------|------------------------|
| **Day Trading** | Intraday momentum, tight stops | AI deep-dive & Oracle interpretation focus on same-day catalysts. Backtest default hold = 1 day. Rebalancer reacts at 3 % drift. |
| **Swing Trading** | 2–10 day breakouts *(default)* | Standard AI analysis. Backtest hold = 5 days. Rebalancer reacts at 5 % drift. |
| **Long-Term Investing** | Fundamentals, multi-month holds | AI focuses on growth & moat. Backtest hold = 30 days. Rebalancer tolerates up to 8 % drift. |

**Where trading_style is consumed:**

| Layer | What changes |
|-------|--------------|
| `GeminiService.analyze_ticker()` | Prompt context sentence tailored to style |
| `GeminiService.get_factor_interpretation()` | Takeaway framed for the style's horizon |
| `MarketIntelligenceService` (all 3 email generators) | CRITICAL RULE in prompt enforces timeframe alignment |
| `/api/backtest` | Default `hold_days` |
| `/api/portfolio-rebalance` | Min-drift / moderate / high thresholds |
| `/api/multi-timeframe` response | Returns `trading_style_label`; component shows badge |
| All three scheduler email jobs | Pass style through to the service |

The style is stored in the `simulation_settings` table under the key `trading_style`.

---

## 4. Pages

### 4.1 Login & Signup

**Routes:** `GET/POST /login`, `GET/POST /signup`, `GET /logout`
**Blueprint:** `auth_bp`

- Supabase Auth handles password hashing and verification.
- On login a persistent server-side session is created (`session.permanent = True`).
- New users are redirected straight to Settings so they can add their BYOK keys.
- A Supabase trigger auto-creates a `user_profiles` row; the signup handler fills in the `username`.

---

### 4.2 Analysis

**Route:** `GET /analysis/<ticker>` (default `NVDA`)
**Blueprint:** `main_bp`

The main stock-analysis page. Server-renders the initial Oracle score and stock data; everything else loads via AJAX as the user interacts.

**What's on this page:**

| Section | Data source | Notes |
|---------|-------------|-------|
| Ticker search bar | Client-side | Navigates to `/analysis/<new ticker>` |
| Live quote card | `GET /api/stock/<ticker>/quote` | Finnhub real-time |
| Price chart | `GET /api/stock/<ticker>/chart` | yfinance historical; 5 period options (1D/5D/1M/3M/1Y) |
| Quick metrics (RSI, P/E, Volatility, Trend) | Embedded in chart data | Computed from yfinance |
| Oracle Score gauge | Server-rendered via `EnhancedOracleService` | 15-factor score, 0–15 scale |
| AI Deep Dive | `GET /api/stock/<ticker>/ai-analysis` | Gemini + Google Search grounding; **style-aware** |
| Monte Carlo simulation | Client-side JS | Uses historical volatility |
| News feed | `GET /api/stock/<ticker>/news` | Finnhub company news |
| Peer stocks | Static list per sector | Links to their analysis pages |
| Multi-Timeframe panel | `GET /api/multi-timeframe?ticker=…` | Weekly / Daily / 4H alignment; shows **Trading Profile badge** |
| Risk Calculator panel | Client-side | Position-size calculator |

---

### 4.3 AI Guidance

**Route:** `GET /ai-guidance`
**Blueprint:** `main_bp`

Oracle's AI-powered scanning page. The user enters a comma-separated list of tickers (or picks a preset watchlist) and hits **Scan Now**. Each ticker is scored sequentially:

1. `GET /api/oracle/<ticker>` → 15-factor Oracle Score
2. `GET /api/stock/<ticker>/quote` → live price/change
3. Auto-loaded: `GET /api/oracle/ai-interpretation/<ticker>` → Gemini reads the Oracle factors and explains them in plain English — **framed for the user's trading style**
4. On-demand: `GET /api/oracle/insight/<ticker>` → 2-sentence "Deep Dive Thesis"

Results split into **Top Picks** (Strong Buy / Buy) cards and a full results table with a verdict filter.  Scan results are cached in `localStorage` for 1 hour so a page refresh doesn't lose them.

---

### 4.4 Scanner

**Route:** `GET /scanner`
**Blueprint:** `main_bp`

A lighter, table-oriented scanner. Picks a watchlist, clicks scan, gets a quick 3-factor signal (Trend / RSI / Market) per ticker.

| Signal | Meaning |
|--------|---------|
| **BUY** | All 3 factors positive |
| **WATCH** | 2 of 3 positive |
| **AVOID** | 0–1 positive |

Uses `ScannerService.scan_watchlist()` which runs tickers in parallel via `ThreadPoolExecutor`.

---

### 4.5 Portfolio

**Route:** `GET /portfolio`
**Blueprint:** `main_bp`

Live Alpaca paper-trading portfolio.

| Card | Source |
|------|--------|
| Portfolio Value / Buying Power / Cash / Equity | Alpaca account API |
| Active positions with live P&L | Alpaca positions API |
| Performance chart | `GET /api/portfolio/history` (Alpaca + local snapshots) |
| Trade history | `GET /api/portfolio/trades` (local `trades` table) |
| Earnings Calendar | `GET /api/earnings-calendar` (Finnhub) |
| Correlation Matrix | `GET /api/portfolio-correlation` |
| Portfolio Rebalancer | `GET /api/portfolio-rebalance` — thresholds depend on **Trading Profile** |

> Note: The Portfolio page shows **Alpaca** paper positions. The Sentinel dashboard (§4.9) shows **shadow** positions imported from a real brokerage.

---

### 4.6 Trade

**Route:** `GET /trade/<ticker>`
**Blueprint:** `main_bp`

Paper-trade execution page for a single ticker. Shows the live quote, current Alpaca position (if any), and open orders. Buy / Sell forms POST to `/api/trading/order`.

---

### 4.7 Watchlist

**Route:** `GET /watchlist`
**Blueprint:** `main_bp`

Manage custom watchlists. Pre-built lists (AI/Tech, Energy, Dividend, Speculative, ETFs, Magnificent 7) plus user-created ones stored in session. If Alpaca is connected, can sync local lists to Alpaca watchlists.

---

### 4.8 Settings

**Route:** `GET/POST /settings`
**Blueprint:** `main_bp`

Central configuration page with four sections:

1. **Account Info** — username, email, sign-out button
2. **Trading Profile** — Day / Swing / Long-Term selector → saved to `simulation_settings.trading_style`
3. **API Keys (BYOK)** — Finnhub, Alpaca, Gemini. Saved encrypted to `user_profiles`
4. **Email Notifications** — Gmail address + App Password (masked after save), toggle switches for Price Alerts, News Alerts, Daily Digest

All forms POST via `fetch()` with CSRF token; the server returns `{"success": true}` JSON.

---

### 4.9 Portfolio Sentinel (Simulation)

**Route:** `GET /simulation`
**Blueprint:** `sentinel_ui_bp`

The monitoring dashboard for **shadow positions** — positions imported from a real brokerage (e.g. Robinhood) that Silicon Oracle tracks but does not trade.

| Section | API | Notes |
|---------|-----|-------|
| Live positions with P&L | `GET /sentinel/positions/enriched` | Enriches each position with Finnhub live price + Oracle score |
| News for holdings | `GET /sentinel/news` | Aggregated from Finnhub |
| Breaking news alerts | `GET /sentinel/news/breaking` | Last 24 hours |
| Performance chart | `GET /sentinel/history` | Auto-backfills last 24 h if sparse |
| Settings panel | `GET/POST /sentinel/settings` | Starting capital, alert thresholds |
| Bulk import | `POST /sentinel/import` | JSON array of positions |

Shadow positions are created via `POST /sentinel/add` (from the Analysis page "Add to Sentinel" button) or bulk-imported. They live in the `shadow_positions` table.

**Sentinel Engine** runs every 5 minutes (Mon–Fri, market hours) as a background cron job. It checks each position for:
- Price breaches (above/below alert thresholds)
- New earnings dates approaching
- Oracle score changes

Alerts are emailed via the user's Gmail if configured.

---

## 5. API Endpoints

All endpoints under `/api/…` are served by `api_bp`. They return JSON. Most require an authenticated session (via cookie); unauthenticated requests get an empty config and features that need API keys will gracefully degrade.

### 5.1 Stock Data

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stock/<ticker>` | Full stock data package (quote + fundamentals) |
| GET | `/api/stock/<ticker>/quote` | Real-time quote from Finnhub (`{current, change, percent_change, …}`) |
| GET | `/api/stock/<ticker>/chart` | Historical OHLCV for charting (period & interval via query params) |
| GET | `/api/stock/<ticker>/news` | Latest news articles from Finnhub |
| GET | `/api/stock/<ticker>/analysis` | Technical indicators (RSI, SMA, MACD, volume) |
| GET | `/api/stock/<ticker>/ai-analysis` | Gemini deep-dive HTML + sentiment score — **trading-style aware** |
| GET | `/api/market/status` | Whether the US market is currently open |

### 5.2 Oracle & AI

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/oracle/<ticker>` | Full 15-factor Enhanced Oracle Score |
| POST | `/api/oracle/scan` | Batch-score a list of tickers (body: `{tickers: [...]}`) |
| GET | `/api/oracle/insight/<ticker>` | 2-sentence AI thesis (cached 1 h) |
| GET | `/api/oracle/ai-interpretation/<ticker>` | AI reads all Oracle factors and explains them — **framed for trading style** |
| GET | `/api/oracle/pattern-analysis/<ticker>` | Chart-pattern detection via Gemini |

### 5.3 Scanner & Watchlists

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/scanner/watchlists` | List all user watchlists (session-stored) |
| POST | `/api/scanner/watchlists/create` | Create a new watchlist |
| DELETE | `/api/scanner/watchlists/<name>` | Delete a watchlist |
| POST | `/api/scanner/watchlists/add-ticker` | Add a ticker to a watchlist |
| POST | `/api/scanner/watchlists/remove-ticker` | Remove a ticker |
| POST | `/api/scanner/scan` | Run a quick 3-factor scan on a list of tickers |
| GET | `/api/scanner/volume-spikes` | Detect unusual volume across holdings |
| GET | `/api/scanner/relative-strength` | Compare holdings' 3-month returns vs SPY |

### 5.4 Trading (Alpaca)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/trading/account` | Alpaca account details |
| GET | `/api/trading/positions` | All open Alpaca positions |
| GET | `/api/trading/orders` | Open / filled orders |
| POST | `/api/trading/order` | Place a market or limit order |
| DELETE | `/api/trading/order/<order_id>` | Cancel an open order |
| DELETE | `/api/trading/position/<ticker>` | Close (sell) an entire position |
| GET | `/api/trading/history` | Recent filled orders |
| GET | `/api/trading/watchlists` | Alpaca watchlists |
| DELETE | `/api/trading/watchlists/<id>` | Delete an Alpaca watchlist |
| POST | `/api/trading/watchlists/<id>/sync` | Sync an Alpaca watchlist from local |
| POST | `/api/trading/watchlists/sync-local` | Push local watchlist tickers to Alpaca |

### 5.5 Portfolio

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/portfolio/trades` | User's trade history (local DB) |
| GET | `/api/portfolio/metrics` | Win rate, P&L, total trades |
| GET | `/api/portfolio/history` | Account-value snapshots over time |

### 5.6 Notifications & Email

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/notifications/test-email` | Send a test email to verify config |
| POST | `/api/notifications/price-alert` | Manually fire a price-alert email |
| POST | `/api/notifications/ai-signal` | Manually fire an AI-signal alert |
| POST | `/api/notifications/position-alert` | Manually fire a position-alert email |
| POST | `/api/notifications/daily-digest` | Manually fire a daily-digest email |

### 5.7 Settings

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/settings/load` | Load current settings from session |
| POST | `/api/settings/save-api-keys` | Save encrypted API keys |
| POST | `/api/settings/save-email` | Save Gmail credentials + alert toggles |
| POST | `/api/settings/test-connections` | Test Finnhub & Alpaca connectivity |
| GET | `/api/settings/data-summary` | Count of trades, positions, watchlists |
| GET | `/api/settings/export` | Download all user data as CSV or Excel |

### 5.8 Market Intelligence

These endpoints drive the AI-powered email system. They all respect the user's **Trading Profile**.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/market-intelligence/trigger` | Manually run the hourly intelligence scan for the logged-in user |
| GET | `/api/market-intelligence/status` | Last-run timestamp and status |
| POST | `/api/market-intelligence/debug` | Run intelligence + return the raw recommendations JSON (no email) |
| POST | `/api/market-intelligence/force-send` | Force an email even if no "significant" news |
| POST | `/api/news-intelligence/trigger` | Trigger the news-only intelligence scan |
| GET | `/api/news-intelligence/status` | News intelligence last-run status |

### 5.9 Advanced Analytics

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/macro-data` | SPY, VIX, 10Y yield, DXY, BTC, Gold, Oil |
| GET | `/api/earnings-calendar` | Upcoming earnings for user's holdings |
| GET | `/api/insider-trades/<ticker>` | Recent insider transactions (Finnhub) |
| GET | `/api/sector-rotation` | 11-sector ETF performance heatmap |
| GET | `/api/portfolio-correlation` | Pairwise correlation of holdings |
| POST | `/api/backtest` | Run a strategy backtest — **default hold_days from Trading Profile** |
| GET | `/api/multi-timeframe` | Weekly / Daily / 4H analysis — **returns trading_style in response** |
| GET | `/api/volatility-surface` | Implied & realized volatility analysis |
| GET | `/api/portfolio-rebalance` | Drift analysis with style-aware thresholds |
| POST | `/api/portfolio-rebalance/execute` | Execute rebalancing trades via Alpaca |

#### Backtest body

```json
{
  "ticker": "NVDA",
  "strategy": "rsi",        // rsi | ma_crossover | breakout
  "period": "1y",           // 1y | 6mo | 3mo | 2y
  "hold_days": 5            // optional; defaults to style (day=1, swing=5, long=30)
}
```

#### Rebalancer drift thresholds (per Trading Profile)

| Style | Action triggered at | Moderate warning | High warning |
|-------|--------------------:|:---:|:---:|
| Day Trading | > 3 % | > 8 % | > 12 % |
| Swing Trading | > 5 % | > 10 % | > 15 % |
| Long-Term | > 8 % | > 15 % | > 25 % |

### 5.10 Sentinel (Position Management)

Mounted under `/sentinel/…` by `sentinel_bp`.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/sentinel/add` | Add a shadow position (ticker, quantity, avg entry price) |
| GET | `/sentinel/dashboard` | Raw list of active shadow positions |
| POST | `/sentinel/sync` | Manually run one Sentinel monitoring cycle |

### 5.11 Sentinel UI (Dashboard Data)

Mounted under `/sentinel/…` by `sentinel_ui_bp`. Powers the Simulation page.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/sentinel/positions/enriched` | Positions + live prices + Oracle scores + alerts |
| DELETE | `/sentinel/position/<id>` | Deactivate a shadow position |
| GET | `/sentinel/news` | Aggregated news for all holdings |
| GET | `/sentinel/news/breaking` | Breaking news (last 24 h) |
| GET | `/sentinel/settings` | Simulation config (capital, alert prefs) |
| POST | `/sentinel/settings` | Update simulation config |
| GET | `/sentinel/history` | Portfolio value over time (with 24 h backfill) |
| POST | `/sentinel/test-email` | Send a test notification |
| POST | `/sentinel/send-digest` | Manual portfolio digest email |
| POST | `/sentinel/import` | Bulk-import positions from JSON |
| POST | `/sentinel/test-alert` | Fire a dummy alert to test email plumbing |
| GET | `/sentinel/debug` | Raw position + user_id debug info |

---

## 6. Background Email Jobs

All jobs run via **APScheduler** inside the Flask process. They are registered in `flask_app/scheduler.py → init_scheduler()`. Double-scheduling in debug/reloader mode is prevented by checking `WERKZEUG_RUN_MAIN`.

**All times are in the server's local timezone.** If you deploy to a cloud region that is not EST/EDT, set the server TZ accordingly (e.g. `TZ=America/New_York` in your Render environment).

| Job ID | Cron schedule | Function | What it does |
|--------|---------------|----------|--------------|
| `market_preview_job` | Mon–Fri 9:00 AM | `market_preview_job()` | Pre-market email: what to watch today, impact on holdings |
| `sentinel_monitor` | Mon–Fri 9:00 AM – 4:00 PM, every 5 min | `sentinel_job()` | Checks each user's shadow positions for alerts |
| `market_intelligence_job` | Mon–Fri 10:00 AM – 4:00 PM, on the hour | `market_intelligence_job()` | Hourly AI scan: broad news → personalized recommendations |
| `market_close_summary_job` | Mon–Fri 5:00 PM | `market_close_summary_job()` | End-of-day recap of market + holdings performance |
| `daily_digest_job` | Mon–Fri 5:30 PM | `daily_digest_job()` | Full portfolio summary with live P&L, top scan results |

**Per-user gating:** Every job loops over `user_profiles`, skips users who have `notifications_enabled = false`, checks their individual notification preferences (`news_alerts`, `daily_digest`, etc.), and skips users missing Gmail or Gemini credentials.

**Frequency preference** (Market Intelligence only): Users can choose `hourly`, `daily` (fires only at 8 AM), or `weekly` (fires only Monday 8 AM) inside their notification prefs.

---

## 7. Manually Triggering Email Jobs

Useful during development or when you want to test an email without waiting for the cron schedule.

### Browser console (fetch)

Open DevTools on any authenticated page and run:

```js
// Market Preview
fetch('/api/trigger-email-job', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({job:'preview'})}).then(r=>r.json()).then(console.log)

// Hourly AI Market Intelligence
fetch('/api/trigger-email-job', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({job:'intelligence'})}).then(r=>r.json()).then(console.log)

// Market Close Summary
fetch('/api/trigger-email-job', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({job:'close'})}).then(r=>r.json()).then(console.log)

// Daily Digest
fetch('/api/trigger-email-job', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({job:'digest'})}).then(r=>r.json()).then(console.log)
```

Valid `job` values: `preview`, `intelligence`, `close`, `digest`.

> The trigger runs the job function directly in the request thread. It operates on **all users** that meet the notification-preference criteria — same as the cron run.

---

## 8. Database Schema

All tables live in the Supabase project specified by `DATABASE_URL`. The schema is auto-created on first run via `utils/database.py → ensure_tables()`.

### user_profiles
| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | Matches Supabase Auth user id |
| email | text | |
| username | text | |
| finnhub_api_key_encrypted | text | Fernet-encrypted |
| alpaca_api_key_encrypted | text | |
| alpaca_secret_key_encrypted | text | |
| gemini_api_key_encrypted | text | |
| gmail_address | text | Plain text (not a secret) |
| gmail_app_password_encrypted | text | Fernet-encrypted |
| notifications_enabled | boolean | Master toggle |
| created_at | timestamp | |

### simulation_settings
| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| user_id | UUID (FK → user_profiles) | Unique per user |
| starting_capital | numeric | Initial portfolio value |
| current_cash | numeric | Cash remaining |
| trading_style | text | `day_trading` / `swing_trading` / `long_term` |
| risk_profile | text | `conservative` / `moderate` / `aggressive` |
| price_alerts | boolean | |
| news_alerts | boolean | |
| daily_digest | boolean | |
| email_alerts | boolean | |
| alert_threshold_percent | numeric | |
| market_intel_frequency | text | `hourly` / `daily` / `weekly` |

### shadow_positions
| Column | Type | Notes |
|--------|------|-------|
| id | integer (PK, auto) | |
| user_id | UUID (FK) | |
| ticker | text | Normalised (e.g. BRK-B) |
| quantity | numeric | Number of shares |
| average_entry_price | numeric | Cost basis per share |
| highest_price_seen | numeric | For trailing-stop logic |
| last_oracle_score | numeric | Cached score |
| next_earnings_date | date | |
| is_active | boolean | NULL treated as active (legacy rows) |
| created_at | timestamp | |

### trades
| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| user_id | UUID (FK) | |
| ticker | text | |
| action | text | BUY / SELL |
| shares | numeric | |
| price | numeric | |
| total_value | numeric | shares × price |
| reason | text | |
| order_id | text | Alpaca order id (if any) |
| source | text | `manual` / `alpaca` |
| timestamp | timestamp | |

### account_history
Periodic snapshots of total portfolio value, cash, and equity. Used for the performance chart.

### ai_scan_results
Cached Oracle scan results so the AI Guidance page can reload quickly.

### market_intelligence_reports
Stores past AI-generated report content for context / memory across runs.

---

## 9. Key Design Decisions

### Shadow Positions vs Alpaca Positions
- **Alpaca positions** are live paper-trade positions managed inside Silicon Oracle (Portfolio page, Trade page).
- **Shadow positions** are read-only mirrors of a real brokerage portfolio. The user imports them manually or via bulk import. Silicon Oracle monitors them and sends alerts but never places orders against them.

### `is_active` can be NULL
Older shadow positions created before the `is_active` field was added have `NULL` in that column. The query uses `.neq("is_active", False)` rather than `.eq("is_active", True)` so that both `True` and `NULL` rows are returned. New positions explicitly set `is_active = True`.

### Trading Style as a Cross-Cutting Concern
Rather than forcing every page to fetch the style independently, a `get_trading_style()` helper in `api.py` centralises the lookup. Each endpoint that generates user-facing AI content or sets numeric defaults simply calls this helper. The style is stored once in `simulation_settings` and saved via the Settings page.

### Email Cron Runs on All Users
Each scheduled job iterates over every `user_profiles` row. This keeps the scheduler simple (one job, not one per user) and means new users get emails automatically once they enable notifications. Each iteration checks the user's individual preferences before doing any work.

### Gemini Prompt Engineering
The AI prompts use a layered approach:
1. **System context** — date, trading-style description
2. **Output format** — exact HTML template (for deep-dive) or structured JSON (for market intelligence)
3. **Critical rules** — numbered constraints that prevent hallucination, enforce timeframe alignment, and control output length
4. **Structured markers** — `{{SCORE:XX}}` / `{{LABEL:YY}}` for extracting metadata from free-text responses via regex

### Caching
- `/api/oracle/insight/<ticker>` is memoised for 1 hour (Flask-Caching). This is a global cache (not per-user) and intentional — the 2-sentence insight doesn't change between users.
- Heavier calls (Oracle score, chart data) are not cached server-side; the browser's Alpine.js layer caches scan results in `localStorage` with a 1-hour TTL.

### CSRF Protection
All POST/PUT/DELETE requests from the frontend include the Flask CSRF token in an `X-CSRFToken` header, set via `{{ csrf_token() }}` in Jinja2 templates.
