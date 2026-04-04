#  Silicon Oracle

**AI-Powered Stock Analysis & Paper Trading Platform**

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)](https://flask.palletsprojects.com/)

> A professional trading platform combining real-time market data, AI-powered analysis, and paper trading in a sleek, modern interface. Built with Flask, powered by Gemini AI, and deployed for free on Render.
> A personal full-stack financial engineering project demonstrating Cloud Architecture, Python, and Generative AI.

**[Live Demo →](https://silicon-oracle.onrender.com/demo)** — Try it without an account.

**DISCLAIMER:** This is an educational project for portfolio demonstration purposes. Not financial advice. See [DISCLAIMER.md](DISCLAIMER.md) for full details.

---

##  Features

###  Real-Time Market Analysis
- Live stock quotes and price tracking
- Technical indicators (RSI, MACD, Bollinger Bands)
- Volume analysis and market trends
- Multiple timeframe charts (1D, 5D, 1M, 6M, 1Y)

###  AI-Powered Insights
- **Oracle Score™** - Proprietary 15-factor technical analysis system
- **Trading Profile** - Set your style (Day / Swing / Long-Term) and every AI output adapts:
  - Deep-dive analysis, Oracle factor interpretations, email recommendations, backtesting defaults, and rebalancer thresholds all adjust to your horizon
- **AI Market Intelligence** - Automated hourly email alerts with:
  - Gemini 2.0 Flash AI with Google Search grounding
  - Personalized stock recommendations (BUY/HOLD/SELL) with confidence scores, locked to your trading-style timeframe
  - Portfolio impact analysis with Oracle-based stop-loss suggestions
  - Market catalysts with clickable source links
  - Watchlist generation for emerging opportunities
  - TL;DR summaries and portfolio health metrics
  - Customizable frequency (hourly/daily/weekly)
- **Market Preview** — Pre-market heads-up every weekday at 9 AM
- **Market Close Summary** — End-of-day recap at 5 PM (Mon-Fri)
- Sentiment analysis from news and social media
- Pattern recognition and trend prediction

###  Paper Trading
- Risk-free practice trading with Alpaca
- Real-time portfolio tracking
- P&L analysis and performance metrics
- Order history and transaction logs

###  Smart Alerts
- Price alerts (above/below thresholds)
- Percentage change notifications
- Technical indicator triggers
- Email and in-app notifications

###  Watchlists
- Pre-configured industry watchlists (Tech Giants, EV, AI, Crypto)
- Custom watchlist creation
- Real-time tracking of multiple stocks
- Quick access to favorite symbols

###  Security & Privacy
- **BYOK (Bring Your Own Keys)** - Each user uses their own API keys
- End-to-end encryption for API credentials
- Secure session management
- No shared rate limits between users

---

##  Why Silicon Oracle?

| Feature | Silicon Oracle | Traditional Platforms |
|---------|----------------|----------------------|
| **Cost** | 100% Free | $10-50/month |
| **Setup** | 15 minutes | Hours of configuration |
| **API Keys** | Your own (BYOK) | Shared (rate limited) |
| **AI Analysis** | Gemini AI included | Extra cost or unavailable |
| **Deployment** | One-click cloud | Complex self-hosting |
| **Multi-User** | Built-in support | Usually single-user |
| **Mobile** | Responsive PWA | Native app required |

---

##  Quick Deploy (15 Minutes)

### Option 1: Deploy to Render (Recommended - FREE)

1. **Fork this repository**
   ```bash
   # Or clone it
   git clone https://github.com/HarshShroff/Silicon-Oracle.git
   cd Silicon-Oracle
   ```

2. **Push to your GitHub**
   ```bash
   git remote set-url origin https://github.com/YOUR_USERNAME/silicon-oracle.git
   git push -u origin main
   ```

3. **Set up Supabase Database (REQUIRED for production)**
   - Go to [supabase.com](https://supabase.com) and create free account
   - Create new project (takes ~2 minutes to provision)
   - Go to Settings → Database → Copy the **URI** connection string
   - It looks like: `postgresql://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres`

4. **Deploy on Render**
   - Go to [dashboard.render.com](https://dashboard.render.com)
   - Click **"New +"** → **"Blueprint"**
   - Connect your GitHub repo
   - Click **"Apply"**
   - **CRITICAL:** Add environment variable:
     ```
     DATABASE_URL=<your-supabase-connection-string>
     ```
   - Wait 5-10 minutes

5. **Done!** Visit your URL and sign up

 **Important:** Without Supabase, your data will be lost on every deploy/restart!

[ Detailed Deployment Guide](DEPLOYMENT.md)

---

##  BYOK System

**Your app, your keys!** Silicon Oracle uses a unique BYOK (Bring Your Own Keys) architecture:

### How It Works
1. Deploy the app (no API keys needed during deployment)
2. Users sign up for their own accounts
3. Each user adds their own API keys in Settings
4. Keys are encrypted and stored per-user in database
5. Everyone has independent rate limits and usage

### Benefits
 **No shared rate limits** - Your keys, your quota
 **More secure** - Keys encrypted per-user
 **Cost-effective** - App owner doesn't pay for everyone
 **Scalable** - Add unlimited users
 **Transparent** - Users control their own API usage

### Required API Keys (All FREE)

| Service | Purpose | Free Tier | Get It |
|---------|---------|-----------|--------|
| **Finnhub** | Market data | 60 calls/min | [finnhub.io](https://finnhub.io) |
| **Alpaca** | Paper trading | Unlimited paper trading | [alpaca.markets](https://alpaca.markets) |
| **Gemini** | AI analysis & market intelligence | 60 requests/min | [ai.google.dev](https://ai.google.dev) |
| **Gmail** | Email alerts (optional) | Free | Use your Gmail + [App Password](https://support.google.com/accounts/answer/185833) |

---

##  Email Schedule (all times server-local, Mon-Fri unless noted)

| Job | When | What |
|-----|------|------|
| **Market Preview** | 9:00 AM | Pre-market heads-up & portfolio impact |
| **Sentinel Monitor** | Every 5 min, 9 AM – 4 PM | Real-time position alerts |
| **AI Market Intelligence** | Every hour, 10 AM – 4 PM | Personalized stock picks via Gemini |
| **Market Close Summary** | 5:00 PM | Today's performance recap |
| **Daily Digest** | 5:30 PM | Full portfolio summary + top opportunities |

> All jobs respect your per-user notification preferences (toggle in Settings → Email).
> Any job can be triggered manually from the browser console — see [API docs](DOCS.md).

---

##  Local Development

### Prerequisites
- Python 3.11+
- Node.js (for Tailwind CSS)
- Git

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/HarshShroff/Silicon-Oracle.git
   cd Silicon-Oracle
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Node dependencies (for Tailwind CSS)**
   ```bash
   npm install
   ```

4. **Build Tailwind CSS**
   ```bash
   npm run build:css
   # Or for watch mode:
   # npm run build:css -- --watch
   ```

5. **Set up secrets (optional)**
   ```bash
   cp .env.example .env
   # Edit .env with your keys
   ```

6. **Run the app**
   ```bash
   python run_flask.py
   ```

7. **Open your browser**
   ```
   http://localhost:5001
   ```

---

##  Architecture

```

             Frontend (Jinja2)

    Analysis  Portfolio    Watchlist
     Page       Page         Page




          Flask Backend (Python)

    Routes (main, api, auth, sentinel)


    Services Layer
    • StockService (market data)
    • OracleService (AI scoring)
    • TradingService (Alpaca)
    • PortfolioService (tracking)
    • AlertEngine (notifications)




           External Services
  • Finnhub API (market data)
  • Alpaca API (paper trading)
  • Gemini API (AI analysis)
  • News APIs (sentiment)

```

---

##  Project Structure

```
Silicon-Oracle/
 flask_app/              # Main Flask application
    routes/            # URL routes (main, api, auth, sentinel)
    services/          # Business logic services
    templates/         # Jinja2 HTML templates
    static/            # CSS, JS, images
    models/            # Data models
 flask_app/agent/       # Agent orchestration module
    runtime.py        # AgentRuntime — tool-call loop
    execution_registry.py  # Tool & command registry
    permissions.py    # Permission-gated tool blocking
    session_store.py  # JSON-persisted session store
 utils/                 # Utility modules
    database.py       # Database operations
    encryption.py     # API key encryption
    ticker_utils.py   # Ticker validation helpers
 run_flask.py          # Application entry point
 requirements.txt      # Python dependencies
 render.yaml           # Render deployment config
 Dockerfile            # Docker configuration
```

---

##  Tech Stack

### Backend
- **Flask** - Web framework
- **Gunicorn** - WSGI server
- **APScheduler** - Background tasks
- **PostgreSQL** - Database (Supabase recommended)
- **SQLite** - Local development only
- **Cryptography** - Encryption

### Frontend
- **Jinja2** - Templating
- **Tailwind CSS** - Styling (TradingView-inspired dark palette)
- **Alpine.js** - Reactive interactivity
- **Lightweight Charts v4** - TradingView-style financial charts
- **Chart.js** - Sector heatmaps & supplementary charts

### APIs & Services
- **Finnhub** - Market data
- **Alpaca** - Paper trading
- **Google Gemini** - AI analysis
- **yfinance** - Historical data

### DevOps
- **Render/Railway/Fly.io** - Hosting
- **GitHub Actions** - CI/CD (optional)
- **Docker** - Containerization

---

##  Security Features

 **Encryption at Rest** - API keys encrypted with Fernet
 **Secure Sessions** - HTTPOnly, Secure cookies
 **CSRF Protection** - Flask-WTF enabled
 **Environment Variables** - No secrets in code
 **HTTPS Enforced** - Automatic on cloud platforms
 **Input Validation** - All user inputs sanitized
 **Rate Limiting** - Per-user API quotas

---

##  Performance

| Metric | Value |
|--------|-------|
| **Response Time** | <500ms average |
| **Cold Start** | ~30s (free tier) |
| **Concurrent Users** | 100+ (scales automatically) |
| **API Calls/min** | Unlimited (per-user keys) |
| **Database** | PostgreSQL (Supabase free: 500MB) |
| **Build Time** | 5-10 minutes |

---

##  Contributing

We welcome contributions! Here's how you can help:

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/amazing-feature
   ```
3. **Make your changes**
4. **Commit with clear messages**
   ```bash
   git commit -m "Add amazing feature"
   ```
5. **Push to your fork**
   ```bash
   git push origin feature/amazing-feature
   ```
6. **Open a Pull Request**

### Development Guidelines
- Follow PEP 8 for Python code
- Add tests for new features
- Update documentation
- Keep commits atomic and well-described

---

##  License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

##  Acknowledgments

- **Finnhub** for excellent market data API
- **Alpaca** for free paper trading
- **Google** for Gemini AI access
- **Render** for free hosting
- **Flask** community for amazing framework

---

##  Support

- **Full Docs (pages, APIs, architecture)**: [DOCS.md](DOCS.md)
- **Deployment Guide**: [DEPLOYMENT.md](DEPLOYMENT.md)
- **Issues**: [GitHub Issues](https://github.com/HarshShroff/Silicon-Oracle/issues)
- **Discussions**: [GitHub Discussions](https://github.com/HarshShroff/Silicon-Oracle/discussions)

---

##  Roadmap

### Current Version (v3.0)
-  Real-time stock analysis
-  AI-powered Oracle scoring (15-factor system)
-  Trading Profile (Day / Swing / Long-Term) — AI adapts everywhere
-  AI Market Intelligence with automated email alerts
-  Market Preview (pre-market) & Close Summary (post-market) emails
-  Paper trading with Alpaca
-  Multi-user BYOK system
-  Watchlists and smart alerts
-  Portfolio Sentinel monitoring with shadow positions
-  Portfolio rebalancer with style-aware thresholds
-  Backtesting engine with style-matched defaults
-  Agent orchestration module with permission-gated tool loops
-  TradingView-style UI with Lightweight Charts v4
-  Public live demo page (no account required)
-  Manual email-job trigger endpoint for testing
-  Responsive design (mobile + desktop)

### Coming Soon (v3.1)
- [ ] Options trading analysis
- [ ] Crypto portfolio support
- [ ] Multi-agent workflows
- [ ] Portfolio backtesting
- [ ] Mobile app (React Native)
- [ ] Social features (share trades, strategies)

### Future (v4.0)
- [ ] Custom indicators and strategies
- [ ] Machine learning models
- [ ] Automated trading bots
- [ ] API for developers

---

##  Usage Stats

- **Active Deployments**: Growing daily
- **GitHub Stars**:  Star us if you find this useful!
- **Contributors**: Open to contributions
- **License**: MIT - Use freely

---

##  Contact

**Harsh Shroff**

- **Email**: harsh.shroff@vitg.us
- **LinkedIn**: [linkedin.com/in/harshroff](https://linkedin.com/in/harshroff)
- **GitHub**: [@HarshShroff](https://github.com/HarshShroff)
- **Issues**: [GitHub Issues](https://github.com/HarshShroff/Silicon-Oracle/issues)
- **Discussions**: [GitHub Discussions](https://github.com/HarshShroff/Silicon-Oracle/discussions)

---

<div align="center">

**Built with  by traders, for traders**

[Deploy Now](https://dashboard.render.com) • [Documentation](DEPLOYMENT.md) • [Report Bug](https://github.com/HarshShroff/Silicon-Oracle/issues)

---

###  Star this repo if you find it helpful!

</div>
