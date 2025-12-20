# 🚀 GitHub Repository Setup Guide

This guide will walk you through creating and publishing your Research Copilot project to GitHub.

## 📋 Prerequisites

- Git installed on your computer
- A GitHub account (create one at https://github.com if you don't have one)
- Your project ready at `/Users/yuanwenbo/Desktop/project`

---

## Step-by-Step Guide

### Step 1: Initialize Git Repository Locally

Open your terminal and navigate to your project:

```bash
cd /Users/yuanwenbo/Desktop/project
```

Initialize a new Git repository:

```bash
git init
```

You should see: `Initialized empty Git repository in /Users/yuanwenbo/Desktop/project/.git/`

---

### Step 2: Configure Git (If First Time)

Set your Git username and email (if you haven't already):

```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

Verify your configuration:

```bash
git config --global --list
```

---

### Step 3: Review Files to Commit

Check what files will be tracked:

```bash
git status
```

**IMPORTANT**: Make sure your `.gitignore` file is working correctly. Files you should **NOT** commit:
- ❌ `config.py` (contains API keys!)
- ❌ `qdrant_db/` (database files)
- ❌ `parent_store/` (storage files)
- ❌ `__pycache__/` (Python cache)
- ❌ `.env` files

If you see these files in `git status`, add them to `.gitignore` before proceeding!

---

### Step 4: Create a Config Template (IMPORTANT!)

Before committing, create a template config file without your real API keys:

```bash
cat > config.example.py << 'EOF'
"""
Configuration Template for Research Copilot

Copy this file to config.py and fill in your API keys.
DO NOT commit config.py to version control!
"""

# OpenAI API (for embeddings and LLM)
OPENAI_API_KEY = "your-openai-api-key-here"

# Google Gemini API (recommended for main LLM)
GOOGLE_API_KEY = "your-google-api-key-here"

# Tavily API (for web search)
TAVILY_API_KEY = "your-tavily-api-key-here"

# GitHub Token (optional)
GITHUB_TOKEN = "your-github-token-here"

# Anthropic API (optional)
ANTHROPIC_API_KEY = "your-anthropic-api-key-here"

# Qdrant Configuration (embedded mode by default)
QDRANT_URL = None  # Use None for embedded mode
QDRANT_API_KEY = None

# Model Configuration
DEFAULT_LLM_PROVIDER = "gemini"  # Options: "openai", "anthropic", "gemini"
DEFAULT_MODEL = "gemini-2.5-flash"
EMBEDDING_MODEL = "text-embedding-3-small"

# RAG Configuration
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200
TOP_K_RETRIEVAL = 10
RERANK_TOP_K = 5
EOF
```

---

### Step 5: Add Files to Git

Add all files to staging:

```bash
git add .
```

Review what will be committed:

```bash
git status
```

**Double-check**: Make sure `config.py` is NOT listed (should show as ignored)

---

### Step 6: Create Initial Commit

Create your first commit:

```bash
git commit -m "Initial commit: Research Copilot - Multi-source AI research assistant"
```

---

### Step 7: Create GitHub Repository

1. **Go to GitHub**: Navigate to https://github.com/new

2. **Fill in repository details**:
   - **Repository name**: `research-copilot` (or your preferred name)
   - **Description**: "AI-powered research assistant with multi-source search (ArXiv, Web, GitHub, YouTube) and local RAG capabilities"
   - **Visibility**: 
     - Choose **Public** if you want to share it
     - Choose **Private** if you want to keep it private
   - **DO NOT** initialize with README, .gitignore, or license (we already have these)

3. **Click "Create repository"**

---

### Step 8: Connect Local Repository to GitHub

After creating the repository, GitHub will show you commands. Copy your repository URL and run:

```bash
# Add GitHub as remote origin (replace with YOUR username/repo)
git remote add origin https://github.com/YOUR_USERNAME/research-copilot.git

# Verify the remote was added
git remote -v
```

You should see:
```
origin  https://github.com/YOUR_USERNAME/research-copilot.git (fetch)
origin  https://github.com/YOUR_USERNAME/research-copilot.git (push)
```

---

### Step 9: Rename Main Branch (if needed)

GitHub uses `main` as the default branch name. Rename your branch if it's `master`:

```bash
git branch -M main
```

---

### Step 10: Push to GitHub

Push your code to GitHub:

```bash
git push -u origin main
```

If this is your first time pushing to GitHub, you'll be prompted to authenticate:
- Enter your GitHub username
- For password, use a **Personal Access Token** (not your GitHub password)

**To create a Personal Access Token**:
1. Go to: https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Give it a name (e.g., "Research Copilot")
4. Select scopes: `repo` (full control)
5. Click "Generate token"
6. **Copy the token immediately** (you won't see it again!)
7. Use this token as your password when pushing

---

### Step 11: Verify Upload

1. Go to your GitHub repository page: `https://github.com/YOUR_USERNAME/research-copilot`
2. You should see all your files
3. Verify the README.md is displayed on the main page

---

## 🔄 Daily Workflow (After Initial Setup)

### Making Changes

```bash
# 1. Check status
git status

# 2. Add changed files
git add .
# Or add specific files
git add research_copilot/agents/new_agent.py

# 3. Commit with a descriptive message
git commit -m "Add new agent for Wikipedia search"

# 4. Push to GitHub
git push
```

### Pulling Changes (if collaborating)

```bash
git pull origin main
```

---

## 🌿 Branching Strategy (Optional but Recommended)

Create branches for new features:

```bash
# Create and switch to a new branch
git checkout -b feature/new-agent

# Make your changes...
git add .
git commit -m "Implement new agent"

# Push branch to GitHub
git push -u origin feature/new-agent

# Go to GitHub to create a Pull Request
# After merging, switch back to main
git checkout main
git pull origin main
```

---

## 📝 Additional Files to Add (Optional)

### Create LICENSE file

Choose a license at https://choosealicense.com/ and add it:

```bash
# For MIT License example:
cat > LICENSE << 'EOF'
MIT License

Copyright (c) 2025 Your Name

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
EOF

git add LICENSE
git commit -m "Add MIT license"
git push
```

### Add CONTRIBUTING.md

```bash
cat > CONTRIBUTING.md << 'EOF'
# Contributing to Research Copilot

Thank you for your interest in contributing! Here are some guidelines:

## How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Code Style

- Follow PEP 8 for Python code
- Add docstrings to all functions and classes
- Write tests for new features

## Reporting Issues

Use GitHub Issues to report bugs or suggest features.
EOF

git add CONTRIBUTING.md
git commit -m "Add contributing guidelines"
git push
```

---

## 🔒 Security Checklist

Before pushing to GitHub, verify:

- ✅ No API keys in code
- ✅ `config.py` is in `.gitignore`
- ✅ `.env` files are in `.gitignore`
- ✅ No personal data in commits
- ✅ Database files are excluded
- ✅ `config.example.py` exists for others to use

---

## 🆘 Troubleshooting

### "Permission denied (publickey)"

Set up SSH keys:
```bash
ssh-keygen -t ed25519 -C "your.email@example.com"
# Add to GitHub: Settings → SSH and GPG keys → New SSH key
```

### "Repository not found"

Check the remote URL:
```bash
git remote -v
git remote set-url origin https://github.com/YOUR_USERNAME/research-copilot.git
```

### Accidentally committed sensitive data

```bash
# Remove file from Git history (but keep local copy)
git rm --cached config.py
git commit -m "Remove config.py from tracking"
git push

# If already pushed, you may need to purge history:
# See: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository
```

---

## 📚 Additional Resources

- [Git Documentation](https://git-scm.com/doc)
- [GitHub Guides](https://guides.github.com/)
- [Connecting to GitHub with SSH](https://docs.github.com/en/authentication/connecting-to-github-with-ssh)
- [GitHub Desktop](https://desktop.github.com/) (GUI alternative)

---

**Congratulations! Your Research Copilot project is now on GitHub! 🎉**
