# Silicon Oracle - Deployment Guide

Deploy Silicon Oracle to the cloud for free and access it from anywhere!

## 🚀 Quick Deploy to Render.com (Recommended - FREE)

### Prerequisites
1. GitHub account
2. Render.com account (sign up at https://render.com)

**Note:** API keys are added AFTER deployment by each user in their Settings page (BYOK system).

### Step 1: Push to GitHub

1. Initialize git repository:
```bash
cd "/Users/harshshroff/Desktop/Silicon Oracle"
git init
```

2. Create a new repository on GitHub (name it `silicon-oracle`)

3. Add and commit files:
```bash
git add .
git commit -m "Initial commit - Silicon Oracle"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/silicon-oracle.git
git push -u origin main
```

### Step 2: Deploy to Render

1. Go to https://dashboard.render.com
2. Click **"New +"** → **"Blueprint"**
3. Connect your GitHub account
4. Select the `silicon-oracle` repository
5. Render will auto-detect `render.yaml` and configure everything

### Step 3: Configure Environment Variables (Optional)

In Render Dashboard → Your Service → Environment:

**✅ Good news!** The `render.yaml` auto-configures everything. You only need environment variables if:

1. **Using Supabase for database** (optional - for persistent PostgreSQL instead of SQLite):
```
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_supabase_key
DATABASE_URL=postgresql://...
```

**⚠️ You do NOT need to add API keys here!**

Your app uses **BYOK (Bring Your Own Keys)** architecture:
- ✅ Each user adds their own API keys after signup (in Settings page)
- ✅ No shared rate limits between users
- ✅ Keys are encrypted per-user in the database
- ✅ More secure - users control their own API access
- ✅ Multi-tenant friendly

### Step 4: Deploy!

1. Click **"Apply"** or **"Manual Deploy"**
2. Wait 5-10 minutes for build to complete
3. Your app will be live at: `https://silicon-oracle.onrender.com`

### Step 5: First Login & Setup

1. Visit your deployed URL (e.g., `https://silicon-oracle-xxx.onrender.com`)
2. Click **"Sign Up"** to create your account
3. After login, go to **Settings** page
4. Add YOUR personal API keys (each user adds their own):
   - **Finnhub API Key** (required) - Get free at https://finnhub.io
   - **Alpaca Keys** (optional) - Get free at https://alpaca.markets
   - **Gemini API Key** (optional) - Get free at https://ai.google.dev
5. Save keys (they're encrypted and stored securely in your user profile)
6. Start trading! 🎉

**Why BYOK (Bring Your Own Keys)?**
- ✅ No shared rate limits - your keys, your quota
- ✅ You control your API usage and costs
- ✅ More secure - keys encrypted per-user
- ✅ Multi-user friendly - perfect for teams
- ✅ No app owner pays for everyone's API calls

---

## 🌐 Alternative: Deploy to Railway.app

Railway offers $5 free credit per month.

### Quick Railway Deploy

1. Install Railway CLI:
```bash
npm install -g @railway/cli
```

2. Login and deploy:
```bash
railway login
railway init
railway up
```

3. Add environment variables (only if using Supabase database):
```bash
railway variables set FLASK_ENV=production
# Only add these if using Supabase for database:
railway variables set SUPABASE_URL=your_url
railway variables set SUPABASE_ANON_KEY=your_key
# Note: API keys NOT needed - users add their own after signup!
```

4. Open your app:
```bash
railway open
```

---

## 🐳 Alternative: Deploy with Docker

### Build Docker Image

```bash
docker build -t silicon-oracle .
```

### Run Locally

```bash
docker run -p 5001:5001 \
  -e FLASK_ENV=production \
  -e SECRET_KEY=your-secret-key \
  silicon-oracle
# Note: API keys NOT needed in environment - users add after signup!
```

### Deploy to Fly.io (FREE)

1. Install Fly CLI:
```bash
curl -L https://fly.io/install.sh | sh
```

2. Launch app:
```bash
fly launch
fly secrets set SECRET_KEY=your-secret-key
fly secrets set FINNHUB_API_KEY=your-key
fly deploy
```

---

## 📊 Database Options

### Option 1: SQLite (Default - Simplest)
- No setup needed
- Data stored in container (resets on redeploy)
- Perfect for testing/personal use

### Option 2: Supabase PostgreSQL (Recommended for Production)
- Free tier: 500MB database
- Persistent data across deploys
- Setup:
  1. Create free account at https://supabase.com
  2. Create new project
  3. Get connection string from Settings → Database
  4. Add to environment variables:
```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=your_anon_key
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres
```

### Option 3: Render PostgreSQL
- Free tier: 90 days, then $7/month
- Uncomment database section in `render.yaml`

---

## ⚙️ Environment Variables Reference

**For Render/Railway/Fly deployment:**

| Variable | Required | Description | Where to Get | Notes |
|----------|----------|-------------|--------------|-------|
| `FLASK_ENV` | Yes | Set to `production` | N/A | Auto-set by render.yaml |
| `SECRET_KEY` | Yes | Random string for sessions | Auto-generated by Render | For Flask session security |
| `SUPABASE_URL` | No | Database URL | https://supabase.com | Only if using Supabase |
| `SUPABASE_ANON_KEY` | No | Database key | https://supabase.com | Only if using Supabase |
| `DATABASE_URL` | No | PostgreSQL connection | Supabase/Render | Only if using PostgreSQL |

**⚠️ API Keys (Finnhub, Alpaca, Gemini) are NOT set here!**

These are added by each user after signup in the Settings page:
- Each user brings their own API keys (BYOK)
- Keys are encrypted and stored per-user in database
- No shared rate limits
- More secure and scalable

---

## 🔧 Troubleshooting

### Build fails with "torch too large"
Torch is 2GB+ which can exceed free tier limits. Options:
1. Use CPU-only torch: `torch --index-url https://download.pytorch.org/whl/cpu`
2. Remove ML features temporarily
3. Upgrade to paid tier

### App crashes on startup
- Check logs in Render dashboard
- Verify SECRET_KEY and FLASK_ENV are set
- Test health endpoint: `curl https://your-app.com/health`
- Note: API keys are NOT needed in environment (added by users after signup)

### Database connection fails
- If using Supabase, verify URL and keys
- Check if DATABASE_URL is correctly formatted
- For SQLite, ensure write permissions

### API rate limits
- Each user manages their own API keys and rate limits
- Finnhub free tier: 60 calls/minute per user
- Users can upgrade their own API tiers as needed
- No shared rate limits = better multi-user experience

---

## 📱 Accessing Your App

Once deployed, you can access from:
- 🌐 Web browser (desktop/mobile)
- 📱 Add to home screen (PWA-ready)
- 🔗 Share URL with team members

**Your URL will be:**
- Render: `https://silicon-oracle-XXXX.onrender.com`
- Railway: `https://silicon-oracle-production.up.railway.app`
- Fly.io: `https://silicon-oracle.fly.dev`

---

## 🔒 Security Best Practices

1. ✅ Never commit `.streamlit/secrets.toml` (already in .gitignore)
2. ✅ Use environment variables for all secrets
3. ✅ Enable HTTPS (automatic on Render/Railway/Fly)
4. ✅ Use strong SECRET_KEY (auto-generated)
5. ✅ Regularly update dependencies: `pip list --outdated`

---

## 💰 Cost Comparison

| Platform | Free Tier | Build Time | Best For |
|----------|-----------|------------|----------|
| **Render** | 750 hrs/mo | 5-10 min | Full-stack apps |
| **Railway** | $5 credit/mo | 2-5 min | Quick deploys |
| **Fly.io** | 3 VMs free | 3-7 min | Docker apps |
| **PythonAnywhere** | Limited | N/A | Simple Python |

**Recommendation:** Start with **Render.com** - it's the easiest and most generous free tier.

---

## 🎯 Next Steps After Deployment

1. Create your account on deployed site
2. Add API keys in Settings
3. Set up watchlists
4. Configure alerts (optional)
5. Start paper trading!

---

## 📞 Need Help?

- Check Render logs: Dashboard → Service → Logs
- Test health endpoint: `https://your-app.com/health`
- Verify environment variables are set correctly

---

## 🔄 Updating Your Deployment

After making changes:
```bash
git add .
git commit -m "Update: description of changes"
git push origin main
```

Render will auto-deploy on every push to `main` branch!

---

**Happy Trading! 🚀📈**
