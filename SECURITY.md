# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Silicon-Oracle, **please do not open a public GitHub issue**.

Instead, email **harsh.shroff@vitg.us** with:

- **Subject**: `[SECURITY] Brief description`
- **Description**: Detailed explanation of the vulnerability
- **Steps to Reproduce**: How to trigger the issue (if applicable)
- **Impact**: What could go wrong (API key exposure, data breach, etc.)
- **Suggested Fix**: If you have one

I will respond within **48 hours** and work with you on a fix.

## Security Best Practices for Users

### API Keys & Secrets

**CRITICAL**: Never commit API keys to version control.

**Setup:**
```bash
# Create local .env file (gitignored)
cp .env.example .env

# Add your secrets
GEMINI_API_KEY=your_key_here
ALPACA_API_KEY=your_key_here
FINNHUB_API_KEY=your_key_here
SUPABASE_URL=your_url_here
SUPABASE_KEY=your_key_here
```

**In production:**
- Use environment-specific secret managers (GitHub Secrets, AWS Secrets Manager, etc.)
- Never store secrets in code or config files
- Rotate API keys regularly
- Use minimal-privilege API keys (read-only where possible)

### Password Security

If using local user authentication:
- Passwords are hashed with werkzeug.security.generate_password_hash
- Never store plaintext passwords
- Use strong passwords (12+ chars, mixed case, numbers, symbols)
- Enable rate limiting on login endpoints (Flask-Limiter enabled)

### API Rate Limiting

Silicon-Oracle implements rate limiting to prevent abuse:
- **Login**: 5 attempts per 15 minutes per IP
- **API calls**: 100 requests per hour per user (configurable)
- **Market data**: Rate limits per external API (yfinance, Finnhub, Alpaca)

## Dependency Security

### Check for Vulnerabilities

```bash
# Install pip-audit
pip install pip-audit

# Scan dependencies
pip-audit
```

### Reporting Dependency Vulnerabilities

If you find a dependency with a known CVE:
1. Check [GitHub's Advisory Database](https://github.com/advisories)
2. Check the package's security advisories
3. Open an issue titled `[SECURITY] Update [PACKAGE] to fix CVE-XXXX`

**Example:**
```
Title: [SECURITY] Update numpy to fix CVE-2024-XXXXX

Description: numpy versions <1.24.0 have a buffer overflow in...
Current version: 1.24.0
Fixed version: 1.24.3
Impact: Potential RCE if processing untrusted array data
```

## Known Security Considerations

### Multi-User BYOK Model

Silicon-Oracle implements "Bring Your Own Key" (BYOK) architecture:

- **No central API key storage**: Users provide their own keys
- **Client-side encryption**: API keys encrypted before database storage (AES-256)
- **Per-user isolation**: Supabase Row Level Security (RLS) enforces user boundaries
- **Audit logging**: API key usage tracked (view-only, never logged in plaintext)

**Implications:**
- ✅ Platform cannot access user data
- ✅ User controls who has access to their portfolios
- ⚠️ User responsible for key security
- ⚠️ Lost keys = lost access (no recovery)

### External Data Sources

Market data comes from:
- **yfinance**: Unofficial Yahoo Finance (historical data)
- **Finnhub**: Paid API (news, fundamentals)
- **Alpaca**: Regulated broker (paper trading)
- **Google News**: RSS feed (news sentiment)

**Risks:**
- Data accuracy depends on source reliability
- API outages affect available data
- Rate limits may be hit during market hours
- News feed may contain spam/low-quality sources

### Sentiment Analysis

News sentiment uses transformers (BERT-based models):
- Model is fine-tuned on financial news
- Sentiment scores are probabilistic (not absolute truth)
- False positives/negatives can occur
- Should not be sole basis for trading decisions

## Version Support

| Version | Status | Security Updates | Release Date |
|---------|--------|------------------|--------------|
| 2.1.x   | ✅ Current | Yes | Mar 2025 |
| 2.0.x   | ✅ Supported | Limited | Jan 2025 |
| 1.x.x   | ⚠️ Legacy | No | 2024 |

**Please upgrade to the latest version for security patches.**

## Responsible Disclosure Timeline

When we receive a security report, we will:

1. **24 hours**: Acknowledge receipt and confirm we're investigating
2. **72 hours**: Provide estimated timeline for fix
3. **7 days** (typical): Release patch version with fix
4. **Release notes**: Credit reporter (if desired) in CHANGELOG.md

## Security Checklist for Deployment

Before deploying Silicon-Oracle to production:

- [ ] Set all required environment variables (no defaults)
- [ ] Use HTTPS only (redirect HTTP to HTTPS)
- [ ] Enable CSRF protection (`flask-wtf` default: enabled)
- [ ] Set strong `SECRET_KEY` (random 32+ char string)
- [ ] Configure CORS properly (not `*` for production)
- [ ] Use database passwords (PostgreSQL should not be public)
- [ ] Enable email rate limiting for notifications
- [ ] Set up monitoring and error alerting
- [ ] Use a production WSGI server (gunicorn, not Flask dev)
- [ ] Keep dependencies updated (run `pip-audit` regularly)
- [ ] Configure firewall rules (whitelist IPs, block unknown)
- [ ] Set up automated backups (database + configuration)
- [ ] Review logs regularly for suspicious activity

## Compliance

Silicon-Oracle is **not** compliance-ready for:
- FINRA (trading regulations)
- SEC (broker-dealer rules)
- GDPR (EU data protection)
- SOC 2 (cloud service audits)

**Disclaimer:** This is a portfolio/analysis tool. It is **not a licensed broker or investment advisor**. Always consult professionals before making financial decisions.

See [DISCLAIMER.md](DISCLAIMER.md) for full legal terms.

## Contact

**Security inquiries:** harsh.shroff@vitg.us
**Bug reports (non-security):** [GitHub Issues](https://github.com/harshshroff/Silicon-Oracle/issues)
**General questions:** [GitHub Discussions](https://github.com/harshshroff/Silicon-Oracle/discussions)

---

**Thank you for helping keep Silicon-Oracle secure.** 🛡️
