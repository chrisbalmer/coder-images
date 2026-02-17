#!/bin/bash
# Release current state from Gitea to GitHub

set -e

echo "🚀 Releasing to GitHub..."
echo ""

# Check for required remotes
if ! git remote | grep -q "^gitea$"; then
    echo "⚠️  No 'gitea' remote found. Add it with:"
    echo "   git remote add gitea https://gitea.example.com/username/coder-images.git"
    echo ""
fi

if ! git remote | grep -q "^github$"; then
    echo "❌ No 'github' remote found. Add it with:"
    echo "   git remote add github https://github.com/username/coder-images.git"
    exit 1
fi

# Ensure we're on main
BRANCH=$(git branch --show-current)
if [ "$BRANCH" != "main" ]; then
    echo "❌ Must be on main branch (currently on: $BRANCH)"
    exit 1
fi

# Ensure clean state
if ! git diff-index --quiet HEAD --; then
    echo "❌ Uncommitted changes detected. Commit or stash them first."
    git status --short
    exit 1
fi

# Pull latest from Gitea (if remote exists)
if git remote | grep -q "^gitea$"; then
    echo "📥 Pulling latest from Gitea..."
    git pull gitea main
    echo ""
fi

# Show what will be pushed
echo "📋 Commits to be pushed to GitHub:"
AHEAD=$(git rev-list --count github/main..HEAD 2>/dev/null || echo "unknown")
if [ "$AHEAD" = "unknown" ] || [ "$AHEAD" -eq 0 ]; then
    echo "   (Up to date or unable to compare)"
else
    echo "   $AHEAD commits ahead"
    git log --oneline github/main..HEAD | head -5
    if [ "$AHEAD" -gt 5 ]; then
        echo "   ... and $((AHEAD - 5)) more"
    fi
fi
echo ""

# Confirm push
read -p "Push to GitHub? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Aborted"
    exit 0
fi

# Push to GitHub
echo "📤 Pushing to GitHub..."
git push github main
echo "✅ Pushed main branch to GitHub"
echo ""

# Ask about tags
read -p "Create a release tag? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Show recent tags
    echo ""
    echo "Recent tags:"
    git tag -l | tail -5
    echo ""

    # Get version
    read -p "Enter version (e.g., 1.2.0): " VERSION

    # Validate version format
    if [[ ! $VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo "⚠️  Warning: Version doesn't follow semantic versioning (x.y.z)"
        read -p "Continue anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "❌ Aborted"
            exit 0
        fi
    fi

    # Check if tag already exists
    if git tag -l | grep -q "^v${VERSION}$"; then
        echo "❌ Tag v${VERSION} already exists"
        exit 1
    fi

    # Create and push tag
    git tag "v${VERSION}"
    git push github "v${VERSION}"

    echo ""
    echo "✅ Released as v${VERSION}"
    echo ""
    echo "🎉 GitHub Actions will now build and publish images:"
    echo "   → ghcr.io/$(git config --get remote.github.url | sed 's/.*github.com[:/]\(.*\)\.git/\1/' | cut -d'/' -f1)/coder-images-*:${VERSION}"
    echo ""
    echo "Monitor progress at:"
    REPO=$(git config --get remote.github.url | sed 's/.*github.com[:/]\(.*\)\.git/\1/')
    echo "   https://github.com/${REPO}/actions"
else
    echo "✅ Pushed to GitHub without tag"
fi

echo ""
echo "🏁 Done!"
