# 🚀 Silicon Oracle - Quick Start Guide

Deploy your AI-powered trading platform to the cloud in 15 minutes!

## What You'll Get

✅ **Free hosting** on Render.com (750 hours/month)
✅ **Access from anywhere** - web, mobile, any device
✅ **Multi-user support** - invite your team
✅ **Secure BYOK system** - each user brings their own API keys
✅ **Real-time stock analysis** with AI
✅ **Paper trading** with Alpaca
✅ **Price alerts** and watchlists

---

## 3-Step Deployment

### Step 1: Push to GitHub (2 minutes)

```bash
cd "/Users/harshshroff/Desktop/Silicon Oracle"
./deploy_to_render.sh
```

Follow the prompts, then push to GitHub:
```bash
git push -u origin main
```

### Step 2: Deploy on Render (3 minutes)

1. Go to https://dashboard.render.com
2. Click **"New +"** → **"Blueprint"**
3. Connect your GitHub repo
4. Click **"Apply"**
5. Wait ~5-10 minutes for build

**That's it!** No environment variables needed - it's all auto-configured.

### Step 3: First Login (2 minutes)

1. Visit your deployed URL (e.g., `https://silicon-oracle-xxx.onrender.com`)
2. Click **"Sign Up"**
3. Go to **Settings** → Add your personal API keys:
   - Get Finnhub key: https://finnhub.io (required)
   - Get Alpaca keys: https://alpaca.markets (optional)
   - Get Gemini key: https://ai.google.dev (optional)
4. Start trading! 🎉

---

## Why BYOK (Bring Your Own Keys)?

Your app doesn't need API keys in the deployment environment because:

✅ **Each user adds their own keys** after signing up
✅ **No shared rate limits** - your keys, your quota
✅ **More secure** - keys encrypted per-user in database
✅ **Multi-user friendly** - perfect for teams
✅ **Cost-effective** - app owner doesn't pay for everyone's API usage

This is different from typical apps where the app owner provides shared API keys!

---

## What Gets Deployed

```
Your App (Render.com)
├── Flask Web Server (Gunicorn)
├── SQLite Database (or PostgreSQL if you configure Supabase)
├── Background Scheduler (news, alerts, scans)
└── Static Assets (CSS, JS, images)
```

**Zero configuration needed** - `render.yaml` handles everything!

---

## After Deployment

Your URL: `https://silicon-oracle-[random].onrender.com`

### Share with your team:
1. Send them the URL
2. They sign up for their own account
3. They add their own API keys in Settings
4. Everyone has their own portfolio, watchlists, and alerts!

### Free tier limitations:
- Sleeps after 15 min inactivity (wakes in ~30s on first request)
- 750 hours/month (enough for personal/small team use)
- Upgrade to paid ($7/mo) for always-on service

---

## Troubleshooting

**Build is too large?**
- The ML dependencies (torch, transformers) are ~2GB
- Free tier might struggle - consider removing ML features temporarily
- Or upgrade to paid tier

**App won't start?**
- Check logs in Render dashboard
- Verify `render.yaml` was detected
- Test health endpoint: `curl https://your-app.com/health`

**Can't log in?**
- Make sure you signed up first!
- Check database is created (SQLite auto-creates)

---

## Next Steps

📖 **Full Guide:** See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions

🐳 **Docker:** See [Dockerfile](Dockerfile) for containerized deployment

🔒 **Security:** See [DEPLOYMENT_SUMMARY.md](DEPLOYMENT_SUMMARY.md) for security features

---

## Need Help?

1. Check Render logs: Dashboard → Your Service → Logs
2. Test health: `https://your-app.com/health`
3. Read full guide: [DEPLOYMENT.md](DEPLOYMENT.md)

---

**Happy Trading! 📈**

Total time: ~15-20 minutes from start to finish 🚀
