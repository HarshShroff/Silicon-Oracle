# Silicon Oracle — API Reference

All API endpoints are prefixed with `/api`. Authentication is required unless noted.

---

## Authentication

### POST /auth/login
Login with email and password.

**Body:** `{ "email": string, "password": string }`

**Response:** Redirects to `/` on success, renders login with flash error on failure.

### POST /auth/signup
Create a new account.

**Body:** `{ "email": string, "password": string, "username": string, "confirm_password": string }`

**Validation (server-side):**
- Username ≥ 3 characters
- Password ≥ 12 characters
- Email format, disposable domain block, MX record lookup
- Duplicate email check against `user_profiles` table

When email confirmation is enabled in Supabase, the user is redirected to login with a "check your inbox" message — no session is created until confirmed.

### POST /auth/validate-email
Public AJAX endpoint. Validates an email address in real time before form submission.

**Body:** `{ "email": string }`

**Response:**
```json
{ "valid": true, "error": "" }
{ "valid": false, "error": "The domain 'example.xyz' doesn't appear to accept email." }
```

**Checks performed:** regex format → disposable domain blocklist → MX DNS record.

### POST /auth/login
Login with email and password. Returns a session cookie on success.

**Body (form):** `email`, `password`

Unconfirmed accounts are blocked with a clear message. Redirects to `/settings` if no Finnhub key is configured.

### GET /auth/logout
Ends the current session and redirects to `/auth/login`.

---

## Health

### GET /health
Public. Returns service health status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-04-08T12:00:00",
  "version": "3.0.0"
}
```

---

## Stock Data

### GET /api/stock/quote?ticker=AAPL
Real-time quote for a ticker.

**Response:**
```json
{
  "current": 189.45,
  "change": 1.23,
  "percent_change": 0.65,
  "high": 190.10,
  "low": 187.80,
  "open": 188.00,
  "previous_close": 188.22,
  "source": "finnhub"
}
```

### GET /api/stock/analysis?ticker=AAPL
Full Oracle AI analysis for a ticker.

**Response:**
```json
{
  "ticker": "AAPL",
  "score": 9,
  "max_score": 15,
  "confidence": 60,
  "verdict": "BUY",
  "verdict_text": "STRONG BUY",
  "factors": [...],
  "quote": {...},
  "company": {...}
}
```

### GET /api/stock/history?ticker=AAPL&period=1y&interval=1d
Historical OHLCV data.

### GET /api/stock/news?ticker=AAPL
Latest news headlines for a ticker (Google News RSS, last 7 days).

### GET /api/stock/peers?ticker=AAPL
Peer/competitor tickers.

### GET /api/stock/earnings?ticker=AAPL
Next earnings date and EPS estimate.

---

## Portfolio

### GET /api/portfolio/summary
Current portfolio value, positions, and P&L.

### GET /api/portfolio/trades?limit=50
Trade history (default limit 50).

### POST /api/portfolio/trade
Submit a paper trade via Alpaca.

**Body:** `{ "ticker": string, "side": "buy"|"sell", "quantity": number, "order_type": "market"|"limit", "limit_price": number? }`

---

## Watchlist

### GET /api/watchlist
All user watchlists plus pre-configured watchlists.

### POST /api/watchlist
Create a new watchlist.

**Body:** `{ "name": string, "tickers": string[] }`

### DELETE /api/watchlist/:id
Delete a watchlist by ID.

---

## Scanner

### GET /api/scanner/scan?watchlist=AI_TECH
Scan a named watchlist for Oracle-scored opportunities.

**Response:**
```json
{
  "results": [
    { "ticker": "NVDA", "score": 12, "verdict": "STRONG BUY", "price": 875.20, "change_percent": 2.1 }
  ]
}
```

---

## Alerts

### GET /api/alerts
All active price alerts for the current user.

### POST /api/alerts
Create a new price alert.

**Body:** `{ "ticker": string, "alert_type": "above"|"below"|"percent_change", "threshold": number }`

### DELETE /api/alerts/:id
Delete an alert.

---

## Demo

### GET /api/demo/chart?ticker=AAPL&period=1y&candle=false
Public chart data for the demo page. No auth required.

---

## Email Jobs (manual trigger)

### POST /api/jobs/trigger/:job_name
Manually trigger a scheduled job. Requires auth.

Jobs: `market_preview`, `sentinel`, `market_intelligence`, `market_close`, `daily_digest`

---

## Macro Intelligence

### GET /api/macro/events
Geopolitical and macro events with sector impact scores.

### GET /api/macro/suggestions
AI-generated trade suggestions based on current macro events.

---

## Agent / Command Center

### POST /api/agent/run
Run a natural-language command through the Agent. Requires auth and a valid Gemini API key.

**Body:** `{ "prompt": string, "session_id": string? }`

**Flow:**
1. `AgentRuntime._gemini_plan_tools` asks Gemini 2.0 Flash which tools to call and with what arguments (falls back to keyword scoring if Gemini is unavailable).
2. Planned tool calls are executed through `ExecutionRegistry` subject to `ToolPermissionContext` deny-lists.
3. `AgentRuntime._gemini_synthesize` turns the structured tool results into a natural-language answer (falls back to formatted text summary).

**Response:**
```json
{
  "answer": "NVDA is currently trading at $875.20 with an Oracle score of 12/15 (Strong Buy)...",
  "tools_used": ["get_quote", "oracle_score"],
  "session_id": "abc123"
}
```

### GET /api/agent/session/:session_id
Retrieve the turn history for an agent session.

### DELETE /api/agent/session/:session_id
Clear an agent session.
