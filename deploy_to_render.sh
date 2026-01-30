#!/bin/bash
# Silicon Oracle - Quick Deploy Script for Render.com

echo "================================================"
echo "   Silicon Oracle - Deployment Setup"
echo "================================================"
echo ""

# Check if git is initialized
if [ ! -d .git ]; then
    echo "📦 Initializing git repository..."
    git init
    git branch -M main
    echo "✅ Git initialized"
else
    echo "✅ Git already initialized"
fi

# Check if remote is set
if ! git remote | grep -q origin; then
    echo ""
    echo "❓ Enter your GitHub repository URL (e.g., https://github.com/username/silicon-oracle.git):"
    read -r repo_url

    if [ -n "$repo_url" ]; then
        git remote add origin "$repo_url"
        echo "✅ Remote added: $repo_url"
    else
        echo "⚠️  No remote URL provided. You can add it later with:"
        echo "   git remote add origin <your-repo-url>"
    fi
else
    echo "✅ Remote already configured"
fi

# Stage and commit files
echo ""
echo "📝 Staging files for commit..."
git add .

echo ""
echo "💾 Creating commit..."
git commit -m "Initial deployment setup for Silicon Oracle" || echo "⚠️  Nothing to commit or already committed"

echo ""
echo "================================================"
echo "   Next Steps:"
echo "================================================"
echo ""
echo "1. Create a new repository on GitHub:"
echo "   https://github.com/new"
echo ""
echo "2. If you haven't set the remote yet, run:"
echo "   git remote add origin <your-repo-url>"
echo ""
echo "3. Push to GitHub:"
echo "   git push -u origin main"
echo ""
echo "4. Deploy on Render:"
echo "   - Go to https://dashboard.render.com"
echo "   - Click 'New +' → 'Blueprint'"
echo "   - Connect your GitHub repo"
echo "   - Add environment variables (see DEPLOYMENT.md)"
echo ""
echo "5. Get your API keys:"
echo "   - Finnhub: https://finnhub.io (required)"
echo "   - Alpaca: https://alpaca.markets (optional)"
echo "   - Gemini: https://ai.google.dev (optional)"
echo ""
echo "📖 Full guide: See DEPLOYMENT.md"
echo ""
echo "================================================"
