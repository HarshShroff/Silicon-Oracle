# Changelog

All notable changes to Silicon-Oracle will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- (Features coming in next release)

### Changed

### Deprecated

### Removed

### Fixed

### Security

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
- **Portfolio-Aware AI**: Gemini Claude now has access to user portfolios
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
  - Real-time WebSocket updates (foundation laid)
- **Advanced Scanner**: Stock screening with 15+ technical indicators
  - Custom filters (price, volume, PE ratio, etc.)
  - Save/load scan templates
  - Alert thresholds
- **Macro Dashboard**: Real-time macro indicators
  - Treasury yields, VIX, inflation rates
  - Oil/gold/crypto prices
  - Economic calendar integration
- **Portfolio Management**: Full position tracking
  - Cost basis calculations
  - Unrealized P&L tracking
  - Tax loss harvesting recommendations
- **AI Integration**: Gemini Claude integration
  - Natural language stock queries
  - Portfolio analysis
  - Risk assessment
- **Paper Trading**: Alpaca integration
  - Buy/sell orders
  - Portfolio simulation
  - Performance tracking
- **Email Notifications**: APScheduler + SendGrid
  - Daily market summary
  - Scanner alerts
  - Portfolio updates
- **Database**: Supabase PostgreSQL
  - Multi-user support
  - Per-user API key storage (encrypted)
  - RLS (Row Level Security) enforcement

### Changed
- Migrated from SQLite to PostgreSQL (Supabase)
- Updated yfinance to v1.0+ (curl_cffi support)
- Modernized technical analysis with pandas-ta-classic

### Security
- Implemented AES-256 encryption for stored API keys
- BYOK (Bring Your Own Key) model for user data privacy
- CSRF protection enabled
- SQL injection protection via SQLAlchemy ORM
- Rate limiting on sensitive endpoints

---

## [1.0.0] - 2024-Q4

### Added
- **Initial Streamlit Release**
  - Stock data retrieval (yfinance)
  - Technical analysis indicators (pandas-ta)
  - Sentiment analysis (transformers)
  - Backtesting engine
  - Market alerts
  - News aggregation (feedparser)
  - Paper trading simulation (Alpaca)

### Known Limitations
- Single-user (no authentication)
- SQLite database (no cloud backup)
- Streamlit UI limitations
- No API key encryption
- Manual data refresh (no scheduling)

---

## [0.1.0] - 2024-Q3

### Added
- Early beta release
- Core market data aggregation
- Technical analysis indicators
- Basic charting with Plotly

---

## Migration Guide

### v1.0 → v2.0

**Database Migration:**
```bash
# Backup SQLite database
cp sqlite.db sqlite.db.backup

# Run database setup
flask db init
flask db migrate -m "Initial migration"
flask db upgrade

# Migrate existing data (if needed)
python scripts/migrate_sqlite_to_postgres.py
```

**Configuration:**
```bash
# Copy environment template
cp .env.example .env

# Update .env with PostgreSQL credentials
# SUPABASE_URL=https://your-project.supabase.co
# SUPABASE_KEY=your-anon-key
```

**Startup:**
```bash
flask run
# Application available at http://localhost:5000
```

### v2.0 → v2.1

No breaking changes. Simply update dependencies:
```bash
pip install -e ".[dev]" --upgrade
```

---

## Planned Features (Roadmap)

### v2.2 (Q2 2025)
- [ ] WebSocket real-time updates
- [ ] Advanced charting indicators
- [ ] Strategy backtesting engine
- [ ] Social features (share portfolios, leaderboards)

### v3.0 (Q4 2025)
- [ ] Mobile app (React Native)
- [ ] Options chain analysis
- [ ] Tax planning tools
- [ ] Institutional data (Morningstar, S&P)
- [ ] API endpoints for third-party integrations

### v4.0 (2026)
- [ ] Robo-advisor features
- [ ] Machine learning for price prediction
- [ ] Blockchain/crypto integration
- [ ] Multi-currency support

---

## How to Report Issues

- **Bug**: [GitHub Issues](https://github.com/harshshroff/Silicon-Oracle/issues)
- **Security**: Email harsh.shroff@vitg.us (see [SECURITY.md](SECURITY.md))
- **Feature Request**: [GitHub Discussions](https://github.com/harshshroff/Silicon-Oracle/discussions)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

---

**Questions?** Check [DOCS.md](DOCS.md) or open a discussion!
