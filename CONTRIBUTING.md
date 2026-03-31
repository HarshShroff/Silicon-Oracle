# Contributing to Silicon-Oracle

Thank you for your interest in contributing! Here's how to help make Silicon-Oracle better.

## Getting Started

### Prerequisites
- Python 3.11+
- Git
- Node.js 18+ (for Tailwind CSS development)

### Local Setup

1. **Fork this repository**
   ```bash
   https://github.com/harshshroff/Silicon-Oracle/fork
   ```

2. **Clone and set up**
   ```bash
   git clone https://github.com/YOUR_USERNAME/Silicon-Oracle.git
   cd Silicon-Oracle
   
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   
   pip install -e ".[dev]"
   ```

3. **Set up environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys (Gemini, Alpaca, Finnhub, etc.)
   ```

4. **Verify setup**
   ```bash
   pytest tests/ -v
   black --check flask_app/
   ruff check flask_app/
   ```

## Development Workflow

### Code Standards

- **Python**: 3.11+ only
- **Formatting**: `black` (100 char line)
- **Linting**: `ruff check flask_app/`
- **Security**: `bandit -r flask_app/`
- **Tests**: Run before committing

### Before Committing

```bash
# Format code
black flask_app/ tests/

# Fix linting issues
ruff check flask_app/ tests/ --fix

# Security check
bandit -r flask_app/

# Run tests
pytest tests/ -v
```

### Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: Add sentiment analysis to stock scanner
fix: Resolve APScheduler email job timeout
docs: Expand database schema documentation
test: Add unit tests for portfolio calculations
perf: Optimize Supabase queries with indexes
```

### Pull Request Process

1. **Create feature branch** from `main`:
   ```bash
   git checkout -b feature/sentiment-analysis
   ```

2. **Make changes** and commit frequently:
   ```bash
   git commit -m "feat: Add sentiment scoring"
   ```

3. **Keep up with main**:
   ```bash
   git fetch origin
   git rebase origin/main
   ```

4. **Push and open PR**:
   ```bash
   git push origin feature/sentiment-analysis
   ```
   - Title: Brief, clear description
   - Description: Why this change? What problem does it solve?
   - Link related issues: "Closes #123"
   - Request review from @harshshroff

5. **Address feedback** with new commits (don't amend)

6. **Squash if needed** before merge

## Testing Guidelines

- Write tests for new features
- Update tests if you change behavior
- Test all API integrations locally:
  ```bash
  # Set API keys in .env
  pytest tests/test_apis.py -v
  ```

### Running Specific Tests
```bash
# Test only market data
pytest tests/test_market_data.py -v

# Test with coverage report
pytest tests/ -v --cov=flask_app --cov-report=html
```

## Documentation

### Python Code Docstrings
Add docstrings to all public functions:
```python
def calculate_oracle_score(ticker: str, lookback_days: int = 365) -> dict:
    """Calculate Silicon-Oracle composite score for a stock.
    
    Combines technical, sentiment, and fundamental analysis into single metric.
    
    Args:
        ticker: Stock symbol (e.g., 'AAPL')
        lookback_days: Historical data window (default: 365)
        
    Returns:
        dict: Score breakdown with components:
            - oracle_score: Final composite (0-100)
            - technical_score: TA metrics (0-100)
            - sentiment_score: News sentiment (0-100)
            - fundamental_score: P/E, dividend, etc. (0-100)
            
    Raises:
        ValueError: If ticker not found
        APIError: If market data unavailable
    """
```

### Markdown Documentation
- Update `DOCS.md` for feature documentation
- Update `README.md` for major feature additions
- Add entries to `CHANGELOG.md` under "Unreleased"

### HTML/CSS/Frontend
- Comment complex layout logic in templates
- Keep Tailwind classes grouped by responsibility
- Test responsive design (mobile, tablet, desktop)

## Areas for Contribution

### High Priority
- [ ] Unit tests for flask_app/services/
- [ ] Database migration guide (Flask-Migrate setup)
- [ ] WebSocket real-time updates for portfolio
- [ ] Advanced charting (multi-indicator overlays)
- [ ] Dark mode UI variant

### Medium Priority
- [ ] Additional sentiment data sources (Twitter API v2)
- [ ] Portfolio comparison benchmarking
- [ ] Backtesting engine for strategies
- [ ] Mobile app (React Native)
- [ ] API documentation (OpenAPI/Swagger)

### Community
- [ ] Bug reports (GitHub Issues)
- [ ] Feature requests with use cases
- [ ] Documentation improvements
- [ ] Performance optimization suggestions

## Security Reporting

**Do not open a public GitHub issue for security vulnerabilities.**

Email: harsh.shroff@vitg.us with:
- Title and description
- Steps to reproduce
- Potential impact
- Suggested fix (if you have one)

See [SECURITY.md](SECURITY.md) for details.

## Questions?

- 📧 Email: harsh.shroff@vitg.us
- 💬 Open a [GitHub Discussion](https://github.com/harshshroff/Silicon-Oracle/discussions)
- 📖 Check [DOCS.md](DOCS.md) for architecture details
- 🐛 Browse [existing issues](https://github.com/harshshroff/Silicon-Oracle/issues)

---

**Thank you for contributing! Your effort helps make Silicon-Oracle better for everyone.** 🙏
