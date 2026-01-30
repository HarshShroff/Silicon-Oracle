#  Silicon Oracle

**AI-Powered Stock Analysis & Paper Trading Platform**

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)](https://flask.palletsprojects.com/)

> A professional trading platform combining real-time market data, AI-powered analysis, and paper trading in a sleek, modern interface. Built with Flask, powered by Gemini AI, and deployed for free on Render.
> A personal full-stack financial engineering project demonstrating Cloud Architecture, Python, and Generative AI.

**DISCLAIMER:** This is an educational project for portfolio demonstration purposes. Not financial advice. See [DISCLAIMER.md](DISCLAIMER.md) for full details.

---

##  Features

###  Real-Time Market Analysis
- Live stock quotes and price tracking
- Technical indicators (RSI, MACD, Bollinger Bands)
- Volume analysis and market trends
- Multiple timeframe charts (1D, 5D, 1M, 6M, 1Y)

###  AI-Powered Insights
- **Oracle Score™** - Proprietary AI rating system (0-100)
- Sentiment analysis from news and social media
- Pattern recognition and trend prediction
- AI-generated investment recommendations

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

[ Detailed Deployment Guide](DEPLOYMENT.md) | [ Quick Start](QUICKSTART.md)

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
| **Gemini** | AI analysis | 60 requests/min | [ai.google.dev](https://ai.google.dev) |

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
   mkdir -p .streamlit
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   # Edit .streamlit/secrets.toml with your keys
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
 utils/                 # Utility modules
    database.py       # Database operations
    encryption.py     # API key encryption
    alpaca.py         # Trading integration
    gemini.py         # AI integration
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
- **Tailwind CSS** - Styling
- **Alpine.js** - Interactivity
- **Chart.js** - Visualizations

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

- **Documentation**: [DEPLOYMENT.md](DEPLOYMENT.md)
- **Quick Start**: [QUICKSTART.md](QUICKSTART.md)
- **Issues**: [GitHub Issues](https://github.com/HarshShroff/Silicon-Oracle/issues)
- **Discussions**: [GitHub Discussions](https://github.com/HarshShroff/Silicon-Oracle/discussions)

---

##  Roadmap

### Current Version (v2.0)
-  Real-time stock analysis
-  AI-powered Oracle scoring
-  Paper trading with Alpaca
-  Multi-user BYOK system
-  Watchlists and alerts
-  Responsive design

### Coming Soon (v2.1)
- [ ] Options trading analysis
- [ ] Crypto support
- [ ] Advanced charting (TradingView integration)
- [ ] Portfolio backtesting
- [ ] Mobile app (React Native)
- [ ] Social features (share trades, strategies)

### Future (v3.0)
- [ ] Real money trading (broker integration)
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

<div align="center">

**Built with  by traders, for traders**

[Deploy Now](https://dashboard.render.com) • [Documentation](DEPLOYMENT.md) • [Report Bug](https://github.com/HarshShroff/Silicon-Oracle/issues)

---

###  Star this repo if you find it helpful!

</div>
