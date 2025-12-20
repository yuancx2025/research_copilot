# GCP Deployment Tutorial - Step-by-Step Guide

This tutorial will guide you through deploying Research Copilot to Google Cloud Platform (GCP) using Cloud Run with Secret Manager for secure API key management.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Step 1: Set Up GCP Project](#step-1-set-up-gcp-project)
3. [Step 2: Enable Required APIs](#step-2-enable-required-apis)
4. [Step 3: Create Secrets in Secret Manager](#step-3-create-secrets-in-secret-manager)
5. [Step 4: Configure Service Account Permissions](#step-4-configure-service-account-permissions)
6. [Step 5: Build and Push Docker Image](#step-5-build-and-push-docker-image)
7. [Step 6: Deploy to Cloud Run](#step-6-deploy-to-cloud-run)
8. [Step 7: Verify Deployment](#step-7-verify-deployment)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before starting, ensure you have:

- ✅ A Google Cloud Platform account
- ✅ `gcloud` CLI installed ([Install Guide](https://cloud.google.com/sdk/docs/install))
- ✅ Docker installed and running locally
- ✅ Your API keys ready:
  - Google Gemini API key
  - YouTube Data API v3 key (optional)
  - GitHub Personal Access Token (optional)
  - Tavily API key (optional)

---

## Step 1: Set Up GCP Project

### 1.1 Create a New Project (or use existing)

```bash
# Set your project ID (choose a unique name)
export PROJECT_ID="research-copilot-$(date +%s)"
export REGION="us-central1"  # Choose your preferred region

# Create the project
gcloud projects create $PROJECT_ID --name="Research Copilot"

# Set as active project
gcloud config set project $PROJECT_ID

# Get project number (needed later)
export PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
echo "Project Number: $PROJECT_NUMBER"
```

**Or use an existing project:**

```bash
export PROJECT_ID="your-existing-project-id"
gcloud config set project $PROJECT_ID
export PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
```

### 1.2 Enable Billing

```bash
# Link billing account (replace BILLING_ACCOUNT_ID with your billing account)
gcloud billing projects link $PROJECT_ID --billing-account=BILLING_ACCOUNT_ID
```

---

## Step 2: Enable Required APIs

Enable the APIs needed for deployment:

```bash
# Enable Cloud Run API
gcloud services enable run.googleapis.com

# Enable Container Registry API (for Docker images)
gcloud services enable containerregistry.googleapis.com

# Enable Secret Manager API
gcloud services enable secretmanager.googleapis.com

# Enable Artifact Registry API (newer, recommended)
gcloud services enable artifactregistry.googleapis.com

# Verify APIs are enabled
gcloud services list --enabled
```

---

## Step 3: Create Secrets in Secret Manager

Store your API keys securely in Secret Manager:

### 3.1 Create Secrets

```bash
# Google Gemini API Key (REQUIRED)
echo -n "your-google-api-key-here" | gcloud secrets create google-api-key \
    --data-file=- \
    --replication-policy="automatic" \
    --project=$PROJECT_ID

# YouTube API Key (OPTIONAL)
echo -n "your-youtube-api-key-here" | gcloud secrets create youtube-api-key \
    --data-file=- \
    --replication-policy="automatic" \
    --project=$PROJECT_ID

# GitHub Token (OPTIONAL)
echo -n "your-github-token-here" | gcloud secrets create github-token \
    --data-file=- \
    --replication-policy="automatic" \
    --project=$PROJECT_ID

# Tavily API Key (OPTIONAL)
echo -n "your-tavily-api-key-here" | gcloud secrets create tavily-api-key \
    --data-file=- \
    --replication-policy="automatic" \
    --project=$PROJECT_ID
```

**Note:** Replace the placeholder values with your actual API keys.

### 3.2 Verify Secrets Created

```bash
# List all secrets
gcloud secrets list --project=$PROJECT_ID

# Verify a specific secret (without revealing value)
gcloud secrets versions access latest --secret="google-api-key" --project=$PROJECT_ID
```

---

## Step 4: Configure Service Account Permissions

Cloud Run needs permission to access Secret Manager:

### 4.1 Get Cloud Run Service Account

```bash
# Cloud Run uses a default service account
export SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
echo "Service Account: $SERVICE_ACCOUNT"
```

### 4.2 Grant Secret Access Permissions

```bash
# Grant access to Google API key secret
gcloud secrets add-iam-policy-binding google-api-key \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor" \
    --project=$PROJECT_ID

# Grant access to YouTube API key secret (if created)
gcloud secrets add-iam-policy-binding youtube-api-key \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor" \
    --project=$PROJECT_ID

# Grant access to GitHub token secret (if created)
gcloud secrets add-iam-policy-binding github-token \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor" \
    --project=$PROJECT_ID

# Grant access to Tavily API key secret (if created)
gcloud secrets add-iam-policy-binding tavily-api-key \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor" \
    --project=$PROJECT_ID
```

### 4.3 Verify Permissions

```bash
# Check IAM policy for a secret
gcloud secrets get-iam-policy google-api-key --project=$PROJECT_ID
```

---

## Step 5: Build and Push Docker Image

### 5.1 Configure Docker for GCP

```bash
# Configure Docker to use gcloud as credential helper
gcloud auth configure-docker

# Or for Artifact Registry (newer)
gcloud auth configure-docker ${REGION}-docker.pkg.dev
```

### 5.2 Build Docker Image

```bash
# Navigate to project root
cd /path/to/your/project

# Build the Docker image
docker build -t gcr.io/${PROJECT_ID}/research-copilot:latest .

# Or use Artifact Registry (recommended)
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/research-copilot/research-copilot:latest .
```

### 5.3 Push to Container Registry

**Option A: Container Registry (legacy)**

```bash
docker push gcr.io/${PROJECT_ID}/research-copilot:latest
```

**Option B: Artifact Registry (recommended)**

```bash
# Create Artifact Registry repository (one-time setup)
gcloud artifacts repositories create research-copilot \
    --repository-format=docker \
    --location=${REGION} \
    --description="Research Copilot Docker images"

# Push image
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/research-copilot/research-copilot:latest
```

---

## Step 6: Deploy to Cloud Run

### 6.1 Deploy with Secret Manager Integration

**Using gcloud CLI:**

```bash
# Deploy to Cloud Run with secrets
gcloud run deploy research-copilot \
    --image=${REGION}-docker.pkg.dev/${PROJECT_ID}/research-copilot/research-copilot:latest \
    --platform=managed \
    --region=${REGION} \
    --project=${PROJECT_ID} \
    --allow-unauthenticated \
    --memory=4Gi \
    --cpu=2 \
    --timeout=300 \
    --max-instances=10 \
    --min-instances=1 \
    --port=7860 \
    --set-env-vars="LLM_PROVIDER=google,LLM_MODEL=gemini-2.5-flash,ENABLE_RERANKING=true,GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
    --set-secrets="GOOGLE_API_KEY=google-api-key:latest,YOUTUBE_API_KEY=youtube-api-key:latest,GITHUB_TOKEN=github-token:latest,TAVILY_API_KEY=tavily-api-key:latest"
```

**Or create a service.yaml file for easier management:**

```yaml
# gcp/cloud-run-service.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: research-copilot
  annotations:
    run.googleapis.com/ingress: all
    run.googleapis.com/execution-environment: gen2
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "1"
        autoscaling.knative.dev/maxScale: "10"
        run.googleapis.com/cpu-throttling: "false"
        run.googleapis.com/memory: "4Gi"
        run.googleapis.com/cpu: "2"
    spec:
      containerConcurrency: 80
      timeoutSeconds: 300
      containers:
      - image: ${REGION}-docker.pkg.dev/${PROJECT_ID}/research-copilot/research-copilot:latest
        ports:
        - name: http1
          containerPort: 7860
        env:
        # Non-sensitive config
        - name: LLM_PROVIDER
          value: "google"
        - name: LLM_MODEL
          value: "gemini-2.5-flash"
        - name: ENABLE_RERANKING
          value: "true"
        - name: GOOGLE_CLOUD_PROJECT
          value: ${PROJECT_ID}
        
        # Secrets from Secret Manager
        - name: GOOGLE_API_KEY
          valueFrom:
            secretKeyRef:
              key: latest
              name: google-api-key
        - name: YOUTUBE_API_KEY
          valueFrom:
            secretKeyRef:
              key: latest
              name: youtube-api-key
        - name: GITHUB_TOKEN
          valueFrom:
            secretKeyRef:
              key: latest
              name: github-token
        - name: TAVILY_API_KEY
          valueFrom:
            secretKeyRef:
              key: latest
              name: tavily-api-key
        
        resources:
          limits:
            cpu: "2"
            memory: "4Gi"
          requests:
            cpu: "1"
            memory: "2Gi"
```

Then deploy:

```bash
gcloud run services replace gcp/cloud-run-service.yaml \
    --region=${REGION} \
    --project=${PROJECT_ID}
```

### 6.2 Get Service URL

```bash
# Get the service URL
export SERVICE_URL=$(gcloud run services describe research-copilot \
    --region=${REGION} \
    --format='value(status.url)')

echo "Service URL: $SERVICE_URL"
```

---

## Step 7: Verify Deployment

### 7.1 Check Service Status

```bash
# Check service status
gcloud run services describe research-copilot \
    --region=${REGION} \
    --format="table(status.conditions[0].status,status.url)"

# View logs
gcloud run services logs read research-copilot \
    --region=${REGION} \
    --limit=50
```

### 7.2 Test the Service

1. **Open the service URL** in your browser:
   ```bash
   echo "Open: $SERVICE_URL"
   ```

2. **Test Research Tab:**
   - Navigate to Research tab
   - Try query: "What are the latest transformer architectures?"
   - Verify citations appear in the right panel

3. **Test File Upload:**
   - Upload a PDF or Markdown file
   - Verify it gets indexed
   - Ask a question about the uploaded document

### 7.3 Monitor Logs

```bash
# Stream logs in real-time
gcloud run services logs tail research-copilot \
    --region=${REGION}

# Filter for errors
gcloud run services logs read research-copilot \
    --region=${REGION} \
    --filter="severity>=ERROR"
```

---

## Step 8: Update Secrets (When Needed)

If you need to update an API key:

```bash
# Create a new version of the secret
echo -n "new-api-key-value" | gcloud secrets versions add google-api-key \
    --data-file=- \
    --project=$PROJECT_ID

# The latest version is automatically used (no redeployment needed)
```

---

## Troubleshooting

### Issue: "Permission denied" when accessing secrets

**Solution:**
```bash
# Verify service account has access
gcloud secrets get-iam-policy google-api-key --project=$PROJECT_ID

# Re-grant access if needed
gcloud secrets add-iam-policy-binding google-api-key \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor" \
    --project=$PROJECT_ID
```

### Issue: "Secret not found"

**Solution:**
```bash
# List all secrets
gcloud secrets list --project=$PROJECT_ID

# Verify secret exists
gcloud secrets describe google-api-key --project=$PROJECT_ID
```

### Issue: Service fails to start

**Solution:**
```bash
# Check logs for errors
gcloud run services logs read research-copilot \
    --region=${REGION} \
    --limit=100

# Common issues:
# 1. Missing GOOGLE_CLOUD_PROJECT env var
# 2. Secret Manager API not enabled
# 3. Service account lacks permissions
```

### Issue: "API quota exceeded"

**Solution:**
- Check your Google Cloud Console for quota limits
- Consider using Ollama for local development
- Monitor API usage in Cloud Console

### Issue: Docker build fails

**Solution:**
```bash
# Test Docker build locally first
docker build -t research-copilot:test .

# Run locally to verify
docker run -p 7860:7860 \
    -e GOOGLE_API_KEY="your-key" \
    research-copilot:test
```

---

## Quick Deployment Script

Save this as `scripts/deploy_gcp.sh`:

```bash
#!/bin/bash
set -e

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-your-project-id}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="research-copilot"
IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${SERVICE_NAME}/${SERVICE_NAME}"

echo "🚀 Deploying Research Copilot to GCP..."
echo "Project: $PROJECT_ID"
echo "Region: $REGION"

# Build Docker image
echo "📦 Building Docker image..."
docker build -t ${IMAGE_NAME}:latest .

# Push to Artifact Registry
echo "📤 Pushing to Artifact Registry..."
docker push ${IMAGE_NAME}:latest

# Deploy to Cloud Run
echo "☁️ Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME}:latest \
    --platform managed \
    --region ${REGION} \
    --project ${PROJECT_ID} \
    --allow-unauthenticated \
    --memory 4Gi \
    --cpu 2 \
    --timeout 300 \
    --max-instances 10 \
    --min-instances 1 \
    --port 7860 \
    --set-env-vars "LLM_PROVIDER=google,LLM_MODEL=gemini-2.5-flash,ENABLE_RERANKING=true,GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
    --set-secrets "GOOGLE_API_KEY=google-api-key:latest,YOUTUBE_API_KEY=youtube-api-key:latest,GITHUB_TOKEN=github-token:latest,TAVILY_API_KEY=tavily-api-key:latest"

# Get service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --region ${REGION} \
    --format 'value(status.url)')

echo "✅ Deployment complete!"
echo "🌐 Service URL: $SERVICE_URL"
```

Make it executable:
```bash
chmod +x scripts/deploy_gcp.sh
```

Usage:
```bash
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="us-central1"
./scripts/deploy_gcp.sh
```

---

## Cost Estimation

**Cloud Run Pricing (as of 2024):**
- **CPU**: $0.00002400 per vCPU-second
- **Memory**: $0.00000250 per GiB-second
- **Requests**: First 2 million requests/month free, then $0.40 per million

**Estimated Monthly Cost:**
- Light usage (1000 requests/day): ~$5-10/month
- Medium usage (10,000 requests/day): ~$30-50/month
- Heavy usage (100,000 requests/day): ~$200-300/month

**Secret Manager:**
- First 6 secrets: Free
- Additional secrets: $0.06 per secret per month

---

## Next Steps

1. **Set up custom domain** (optional):
   ```bash
   gcloud run domain-mappings create \
       --service research-copilot \
       --domain your-domain.com \
       --region ${REGION}
   ```

2. **Enable Cloud Monitoring** for better observability

3. **Set up CI/CD** with Cloud Build for automated deployments

4. **Configure autoscaling** based on your traffic patterns

---

## Security Best Practices

1. ✅ **Never commit API keys** to version control
2. ✅ **Use Secret Manager** for all sensitive data
3. ✅ **Limit service account permissions** (principle of least privilege)
4. ✅ **Enable Cloud Audit Logs** to track secret access
5. ✅ **Rotate secrets regularly** (every 90 days recommended)
6. ✅ **Use IAM conditions** to restrict secret access by service

---

## Support

If you encounter issues:
1. Check Cloud Run logs: `gcloud run services logs read research-copilot --region=${REGION}`
2. Verify Secret Manager permissions
3. Check API quotas in Cloud Console
4. Review [Cloud Run documentation](https://cloud.google.com/run/docs)

---

**Congratulations!** Your Research Copilot is now deployed on GCP! 🎉
