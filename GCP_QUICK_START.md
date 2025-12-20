# GCP Deployment - Quick Start Guide

## 🚀 Quick Deployment (5 Minutes)

### Prerequisites Check

```bash
# 1. Install gcloud CLI (if not installed)
# macOS: brew install google-cloud-sdk
# Visit: https://cloud.google.com/sdk/docs/install

# 2. Login to GCP
gcloud auth login

# 3. Set your project
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="us-central1"
gcloud config set project $GCP_PROJECT_ID
```

### Step 1: Create Secrets (2 minutes)

```bash
# Create secrets in Secret Manager
echo -n "your-google-api-key" | gcloud secrets create google-api-key --data-file=-
echo -n "your-youtube-api-key" | gcloud secrets create youtube-api-key --data-file=-
echo -n "your-github-token" | gcloud secrets create github-token --data-file=-
echo -n "your-tavily-api-key" | gcloud secrets create tavily-api-key --data-file=-

# Grant permissions
PROJECT_NUMBER=$(gcloud projects describe $GCP_PROJECT_ID --format="value(projectNumber)")
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud secrets add-iam-policy-binding google-api-key \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding youtube-api-key \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding github-token \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding tavily-api-key \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor"
```

### Step 2: Enable APIs (1 minute)

```bash
gcloud services enable run.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable artifactregistry.googleapis.com
```

### Step 3: Deploy (2 minutes)

```bash
# Use the deployment script
./scripts/deploy_gcp.sh

# Or manually:
# 1. Build and push image
docker build -t us-central1-docker.pkg.dev/$GCP_PROJECT_ID/research-copilot/research-copilot:latest .
docker push us-central1-docker.pkg.dev/$GCP_PROJECT_ID/research-copilot/research-copilot:latest

# 2. Deploy
gcloud run deploy research-copilot \
    --image us-central1-docker.pkg.dev/$GCP_PROJECT_ID/research-copilot/research-copilot:latest \
    --region us-central1 \
    --allow-unauthenticated \
    --memory 4Gi \
    --cpu 2 \
    --set-env-vars "GOOGLE_CLOUD_PROJECT=$GCP_PROJECT_ID" \
    --set-secrets "GOOGLE_API_KEY=google-api-key:latest,YOUTUBE_API_KEY=youtube-api-key:latest"
```

### Step 4: Get URL

```bash
gcloud run services describe research-copilot \
    --region us-central1 \
    --format 'value(status.url)'
```

**Done!** 🎉 Open the URL in your browser.

---

## 📋 Configuration Summary

### How It Works

1. **Local Development**: Uses `.env` file or environment variables
2. **GCP Production**: Automatically uses Secret Manager
3. **Priority**: Environment variables > Secret Manager > None

### Files Created

- `config/gcp_settings.py` - GCP-optimized config with Secret Manager
- `config/__init__.py` - Module initialization
- `GCP_DEPLOYMENT_TUTORIAL.md` - Detailed step-by-step guide
- `scripts/deploy_gcp.sh` - Automated deployment script

### Environment Variables (Local)

Create `.env` file:

```bash
# .env
GOOGLE_API_KEY=your-key
YOUTUBE_API_KEY=your-key
GITHUB_TOKEN=your-token
TAVILY_API_KEY=your-key
```

### Secrets in GCP

Secrets are automatically loaded from Secret Manager when running on GCP.

---

## 🔧 Common Commands

```bash
# View logs
gcloud run services logs read research-copilot --region us-central1

# Update service
gcloud run services update research-copilot --region us-central1

# Delete service
gcloud run services delete research-copilot --region us-central1

# Update secret
echo -n "new-value" | gcloud secrets versions add google-api-key --data-file=-
```

---

## 📚 Full Tutorial

For detailed instructions, see [GCP_DEPLOYMENT_TUTORIAL.md](./GCP_DEPLOYMENT_TUTORIAL.md)
