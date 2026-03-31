# Monitoring & Observability Guide

Production Silicon-Oracle deployment requires visibility into application health, performance, and errors.

## Quick Start

### Error Tracking (Sentry)

```bash
# Install
pip install sentry-sdk

# Configure in flask_app/__init__.py
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

sentry_sdk.init(
    dsn="https://key@sentry.io/project-id",
    integrations=[FlaskIntegration()],
    traces_sample_rate=0.1,  # 10% of requests
    environment="production"
)
```

### Application Logging

```python
import logging

logger = logging.getLogger(__name__)

# In route handlers
logger.info(f"User {user_id} executed scan: {scan_id}")
logger.error(f"API error: {error_message}", exc_info=True)
```

### Health Check Endpoint

```python
# Add to flask_app/routes/main.py
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring."""
    try:
        # Check database connection
        db.session.execute(text("SELECT 1"))
        
        # Check external API connectivity
        # (optional: quick ping to Finnhub/Alpaca)
        
        return {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '2.1.0'
        }, 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {'status': 'unhealthy', 'error': str(e)}, 503
```

## Production Deployment Checklist

### Application Monitoring

- [ ] **Error Tracking**: Set up Sentry
- [ ] **Health Endpoint**: `/health` returns 200 when healthy
- [ ] **Structured Logging**: JSON logs with request IDs
- [ ] **Performance Monitoring**: Track slow queries/API calls
- [ ] **Alerting**: Notify on errors, high latency

### Database Monitoring

- [ ] **Connection Pooling**: Configure SQLAlchemy `pool_size`
- [ ] **Query Performance**: Enable slow query log
- [ ] **Backups**: Automated daily backups (Supabase automatic)
- [ ] **Monitoring**: CPU, memory, disk usage

### Background Job Monitoring (APScheduler)

```python
# Add logging to scheduled jobs
from apscheduler.schedulers.background import BackgroundScheduler

def send_daily_summary():
    """Daily market summary email."""
    try:
        logger.info("Starting daily summary job")
        # ... job logic ...
        logger.info("Daily summary completed")
    except Exception as e:
        logger.error(f"Daily summary failed: {e}", exc_info=True)
        # Alert (Sentry, email, etc.)
        raise

scheduler = BackgroundScheduler()
scheduler.add_job(send_daily_summary, 'cron', hour=8, minute=0)
scheduler.start()
```

### External API Monitoring

```python
import time
from functools import wraps

def monitor_api_call(func):
    """Decorator to log API calls and track latency."""
    def wrapper(*args, **kwargs):
        start = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start
            logger.info(f"{func.__name__} completed in {duration:.2f}s")
            return result
        except Exception as e:
            duration = time.time() - start
            logger.error(f"{func.__name__} failed after {duration:.2f}s: {e}")
            raise
    return wrapper

@monitor_api_call
def fetch_stock_data(ticker):
    """Fetch data from yfinance."""
    return yf.download(ticker)
```

## Key Metrics to Monitor

### Application Level

| Metric | Target | Alert If |
|--------|--------|----------|
| **Error Rate** | < 1% | > 5% |
| **Response Time (p95)** | < 500ms | > 2s |
| **Response Time (p99)** | < 1000ms | > 5s |
| **Uptime** | > 99.9% | < 99% |
| **API Rate Limit** | < 80% of quota | > 90% |

### Database Level

| Metric | Target | Alert If |
|--------|--------|----------|
| **Query Time (p95)** | < 100ms | > 500ms |
| **Connection Pool Usage** | < 70% | > 90% |
| **Disk Usage** | < 70% | > 85% |
| **Backup Age** | < 24 hours | > 48 hours |

### Email Job Level

| Metric | Target | Alert If |
|--------|--------|----------|
| **Job Success Rate** | > 99% | < 95% |
| **Email Delivery Rate** | > 98% | < 90% |
| **Job Duration** | < 30s | > 5 minutes |

## Recommended Monitoring Stacks

### Minimal (Free/Low Cost)

```
Application: Sentry (free tier: 5K errors/month)
Logs: Render/Railway built-in logs
Database: Supabase dashboard
Status: Uptime Robot (free tier: 50 monitors)
```

**Cost**: ~$0 - $30/month

### Production (Recommended)

```
Application: Sentry + DataDog
Logs: ELK Stack (self-hosted) or LogRocket
Database: Supabase metrics + DataDog
Tracing: Grafana Tempo or DataDog APM
Status: PagerDuty + Grafana
```

**Cost**: $200 - $1000+/month

### Enterprise

```
Full observability with Datadog:
- APM (Application Performance Monitoring)
- Distributed Tracing
- Log Management
- Infrastructure Monitoring
- Alert Orchestration
```

**Cost**: $1000+ /month

## Setting Up Sentry

### 1. Create Sentry Account

```bash
# Visit https://sentry.io and sign up (free plan available)
# Create project: Python + Flask
# Get DSN: https://key@sentry.io/project-id
```

### 2. Configure Flask

```python
# flask_app/__init__.py
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
from sentry_sdk.integrations.sqlalchemy import SqlAlchemyIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

sentry_sdk.init(
    dsn=os.getenv('SENTRY_DSN'),
    integrations=[
        FlaskIntegration(),
        SqlAlchemyIntegration(),
        LoggingIntegration(
            level=logging.INFO,        # Capture info and above
            event_level=logging.ERROR  # Send errors to Sentry
        )
    ],
    traces_sample_rate=0.1,        # 10% transaction sampling
    environment=os.getenv('FLASK_ENV', 'development'),
    before_send=lambda event, hint: event  # Custom filtering
)
```

### 3. Environment Variable

```bash
# .env
SENTRY_DSN=https://key@sentry.io/project-id
```

### 4. Test Sentry

```python
# In Flask shell
from flask import Flask
app = Flask(__name__)

import sentry_sdk
sentry_sdk.init(dsn="YOUR_DSN")

# Trigger test error
1 / 0  # This will be sent to Sentry
```

## Logging Best Practices

### Use Structured Logging

```python
import json
import logging

class JsonFormatter(logging.Formatter):
    """JSON formatter for better log aggregation."""
    def format(self, record):
        log_data = {
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        return json.dumps(log_data)

# Apply to Flask
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
app.logger.addHandler(handler)
```

### Include Request Context

```python
from flask import request, g
import uuid

@app.before_request
def add_request_id():
    """Add request ID for tracing."""
    g.request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
    logger.info(f"Request started: {request.method} {request.path}")

@app.after_request
def log_response(response):
    logger.info(f"Request finished: {response.status_code}")
    return response
```

## Common Issues & Debugging

### APScheduler Email Jobs Failing Silently

```python
# Enable APScheduler logging
logging.getLogger('apscheduler').setLevel(logging.DEBUG)

# Add error handler to job
def send_email_with_retry(user_id):
    try:
        # ... send email ...
    except Exception as e:
        logger.error(f"Email send failed for user {user_id}: {e}", exc_info=True)
        # Re-raise or send alert
        raise
```

### Database Connection Pool Exhaustion

```python
# Configure connection pooling
from sqlalchemy.pool import QueuePool

app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'poolclass': QueuePool,
    'pool_size': 10,
    'pool_recycle': 3600,     # Recycle connections every hour
    'pool_pre_ping': True,    # Test connections before using
    'max_overflow': 20,       # Allow up to 20 overflow connections
}
```

### Slow API Requests

```python
# Monitor external API calls
@monitor_api_call
def get_stock_data(ticker):
    """Track Finnhub API latency."""
    start = time.time()
    response = requests.get(
        f"https://finnhub.io/api/v1/quote",
        params={'symbol': ticker, 'token': FINNHUB_KEY}
    )
    duration = time.time() - start
    
    if duration > 2.0:
        logger.warning(f"Slow Finnhub API call: {ticker} took {duration:.2f}s")
    
    return response.json()
```

## Alerting Strategy

### Critical Alerts (Page On-Call)

- Application error rate > 10%
- Database connection failure
- Email delivery job failure
- API rate limit exceeded
- Disk usage > 90%

### Warning Alerts (Email/Slack)

- Response time p95 > 1s
- Error rate > 1%
- Database query slow (> 500ms)
- Low disk space (> 70%)

### Info Alerts (Dashboard Only)

- Daily summary of errors
- Performance trends
- Background job completion

## Resources

- **Sentry Docs**: https://docs.sentry.io/product/
- **Flask Logging**: https://flask.palletsprojects.com/logging/
- **SQLAlchemy Monitoring**: https://docs.sqlalchemy.org/dialects/postgresql/
- **APScheduler Docs**: https://apscheduler.readthedocs.io/

---

**Questions?** Open a [GitHub Discussion](https://github.com/harshshroff/Silicon-Oracle/discussions)
