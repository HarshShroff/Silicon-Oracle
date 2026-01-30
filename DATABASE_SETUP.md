# 🗄️ Database Setup Guide

## ⚠️ Critical: Why You Need PostgreSQL for Production

### The Problem with SQLite on Render

**SQLite is EPHEMERAL on Render's free tier:**
- ❌ Data deleted on every deploy
- ❌ Data deleted on app restart
- ❌ Data deleted on sleep/wake cycle
- ❌ Users lose accounts, API keys, watchlists, alerts

**Result:** Your users will be **very angry** 😠

### The Solution: Supabase PostgreSQL

**Supabase gives you PERSISTENT storage:**
- ✅ Data survives deploys
- ✅ Data survives restarts
- ✅ Data survives sleep/wake
- ✅ Free tier: 500MB storage
- ✅ Users happy 😊

---

## 🚀 Quick Setup (5 Minutes)

### Step 1: Create Supabase Account

1. Go to https://supabase.com
2. Click "Start your project"
3. Sign in with GitHub (easiest)

### Step 2: Create New Project

1. Click "New Project"
2. Fill in:
   - **Name:** silicon-oracle (or anything)
   - **Database Password:** (generate strong password - save it!)
   - **Region:** Choose closest to your users
3. Click "Create new project"
4. Wait 2-3 minutes for database to provision ☕

### Step 3: Get Connection String

1. Go to **Settings** (gear icon, bottom left)
2. Click **Database**
3. Scroll to **Connection string**
4. Select **URI** tab
5. Copy the connection string:
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres
   ```
6. **Replace** `[YOUR-PASSWORD]` with your actual database password

### Step 4: Add to Render

1. Go to your Render dashboard
2. Click your **silicon-oracle** service
3. Go to **Environment** tab
4. Click **Add Environment Variable**
5. Add:
   - **Key:** `DATABASE_URL`
   - **Value:** `postgresql://postgres:your-password@db.xxxxx.supabase.co:5432/postgres`
6. Click **Save Changes**
7. Your app will auto-redeploy with PostgreSQL! 🎉

---

## 🔍 Verify It's Working

### Check Render Logs

After redeploy completes, check logs:
```
Using database: postgresql://postgres:***@db.xxxxx.supabase.co:5432/postgres
✓ Database connected successfully
```

### Test User Signup

1. Visit your app
2. Sign up for an account
3. Add API keys in Settings
4. **Trigger a redeploy** (push a commit)
5. Log in again - **your account should still exist!** ✅

---

## 📊 Database Architecture

Your Flask app automatically handles both:

```python
# flask_app/config.py (already configured!)

# Priority order:
if DATABASE_URL exists:
    use PostgreSQL (Supabase)  # ← Production
elif SUPABASE_DB_URL exists:
    use PostgreSQL (Supabase)  # ← Alternative
else:
    use SQLite (local file)    # ← Local dev only
```

### Tables Created Automatically

On first run, your app creates:
- `users` - User accounts
- `api_keys` - Encrypted API keys (per-user)
- `portfolios` - Trading portfolios
- `orders` - Order history
- `alerts` - Price alerts
- `watchlists` - Custom watchlists
- `sentinel_scans` - Scanner results

---

## 🛠️ Advanced Configuration

### Using Supabase Auth (Optional)

Your app has its own auth, but you can also use Supabase's:

1. In Supabase: **Authentication** → **Providers**
2. Enable **Email** (enabled by default)
3. Optional: Enable **Google**, **GitHub**, etc.
4. Update your Flask app to use Supabase auth SDK

### Connection Pooling

For high traffic, use **Supabase Connection Pooler**:

1. Settings → Database → Connection pooling
2. Enable **Transaction** mode
3. Use the **pooler** connection string:
   ```
   postgresql://postgres.xxxxx:your-password@aws-0-us-east-1.pooler.supabase.com:6543/postgres
   ```

### Database Backups

Supabase automatically backs up your database daily. To restore:

1. Go to **Database** → **Backups**
2. Select backup date
3. Click **Restore**

---

## 💰 Cost Breakdown

### Free Tier (Forever)
- **Database:** 500MB storage
- **Bandwidth:** 5GB/month
- **API requests:** Unlimited
- **Backups:** Daily (7 days retention)
- **Perfect for:** Personal use, small teams

### Pro Tier ($25/month)
- **Database:** 8GB storage
- **Bandwidth:** 50GB/month
- **Backups:** Daily (30 days retention)
- **Priority support**
- **Perfect for:** Production apps, growing user base

---

## 🔒 Security Best Practices

### 1. Use Environment Variables
Never commit your connection string to git:
```bash
# .gitignore already has:
.env
.streamlit/secrets.toml
```

### 2. Use SSL Connections
Supabase uses SSL by default. Your connection string includes `sslmode=require`.

### 3. Rotate Database Password
Change your database password every 90 days:
1. Supabase → Settings → Database
2. Click **Reset database password**
3. Update `DATABASE_URL` in Render

### 4. Enable Row Level Security (RLS)
Supabase supports RLS for advanced security:
```sql
-- Enable RLS on users table
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own data
CREATE POLICY "Users can view own data" ON users
  FOR SELECT USING (auth.uid() = id);
```

---

## 🆘 Troubleshooting

### "Connection Refused"
- **Cause:** Wrong connection string or password
- **Fix:** Double-check `DATABASE_URL` in Render environment

### "Max Connections Reached"
- **Cause:** Too many concurrent connections (free tier limit: 50)
- **Fix:** Use connection pooler or upgrade to Pro

### "Database Does Not Exist"
- **Cause:** Wrong database name in connection string
- **Fix:** Ensure it ends with `/postgres`

### "SSL Required"
- **Cause:** Connection string missing SSL parameter
- **Fix:** Add `?sslmode=require` to end of connection string

---

## 📚 Additional Resources

- **Supabase Docs:** https://supabase.com/docs
- **Flask-SQLAlchemy:** https://flask-sqlalchemy.palletsprojects.com/
- **PostgreSQL:** https://www.postgresql.org/docs/

---

## ✅ Quick Checklist

Before going to production:

- [ ] Supabase account created
- [ ] Database provisioned (wait for green check)
- [ ] Connection string copied
- [ ] `DATABASE_URL` added to Render environment
- [ ] App redeployed successfully
- [ ] Tested signup → redeploy → login (data persists!)
- [ ] Database password saved securely (e.g., password manager)

---

**Your data is now safe!** 🛡️

No more losing user accounts on every deploy. Happy trading! 📈
