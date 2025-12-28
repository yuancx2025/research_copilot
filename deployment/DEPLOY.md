# Step-by-Step GCP Deployment Guide

This guide provides **copy-paste ready commands** to deploy Research Copilot to Google Cloud Platform using Cloud Build (no local Docker required).

## Prerequisites

1. **Google Cloud Account** with billing enabled
2. **gcloud CLI** installed and authenticated
3. **API Keys** ready:
   - Google Gemini API key ([Get here](https://makersuite.google.com/app/apikey))
   - Tavily API key ([Get here](https://tavily.com))
   - Optional: YouTube API key, GitHub token, Notion API key

## Step 1: Set Your Project Variables

```bash
# Replace with your actual project ID
export PROJECT_ID="research-copilot-481820" 
export REGION="us-central1"
export SERVICE_NAME="research-copilot"
export REPO_NAME="research-copilot"
export SA_NAME="research-copilot"
export SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# Verify your project is set
gcloud config set project ${PROJECT_ID}
```

## Step 2: Enable Required APIs

```bash
gcloud services enable \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  --project=${PROJECT_ID}
```

## Step 3: Create Service Account

```bash
# Create service account for Cloud Run
gcloud iam service-accounts create ${SA_NAME} \
  --display-name="Research Copilot Runtime Service Account" \
  --project=${PROJECT_ID} || echo "Service account already exists"

# Grant necessary permissions
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.admin" \
  --condition=None

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor" \
  --condition=None

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/logging.logWriter" \
  --condition=None

# Get your email (replace YOUR_EMAIL with your actual GCP email)
YOUR_EMAIL=$(gcloud config get-value account)

# Grant yourself permission to use the service account
gcloud iam service-accounts add-iam-policy-binding ${SA_EMAIL} \
  --member="user:${YOUR_EMAIL}" \
  --role="roles/iam.serviceAccountUser" \
  --project=${PROJECT_ID} || echo "Permission already granted"

# Grant Cloud Build permission to push to Artifact Registry
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format="value(projectNumber)")
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/artifactregistry.writer" \
  --condition=None || echo "Permission already granted"
```

## Step 4: Create Artifact Registry Repository

```bash
# Create Docker repository (if it doesn't exist)
gcloud artifacts repositories create ${REPO_NAME} \
  --repository-format=docker \
  --location=${REGION} \
  --description="Docker repository for Research Copilot" \
  --project=${PROJECT_ID} || echo "Repository already exists"
```

## Step 5: Create Secrets in Secret Manager

```bash
# Required: Google API Key
echo -n "YOUR_GOOGLE_API_KEY_HERE" | gcloud secrets create GOOGLE_API_KEY \
  --data-file=- \
  --replication-policy="automatic" \
  --project="${PROJECT_ID}" || \
  echo -n "YOUR_GOOGLE_API_KEY_HERE" | gcloud secrets versions add GOOGLE_API_KEY \
    --data-file=- \
    --project="${PROJECT_ID}"

# Required: Tavily API Key
echo -n "YOUR_TAVILY_API_KEY_HERE" | gcloud secrets create TAVILY_API_KEY \
  --data-file=- \
  --replication-policy="automatic" \
  --project="${PROJECT_ID}" || \
  echo -n "YOUR_TAVILY_API_KEY_HERE" | gcloud secrets versions add TAVILY_API_KEY \
    --data-file=- \
  --project="${PROJECT_ID}"

# Optional: YouTube API Key
echo -n "YOUR_YOUTUBE_API_KEY_HERE" | gcloud secrets create YOUTUBE_API_KEY \
  --data-file=- \
  --replication-policy="automatic" \
  --project="${PROJECT_ID}" || \
  echo -n "YOUR_YOUTUBE_API_KEY_HERE" | gcloud secrets versions add YOUTUBE_API_KEY \
    --data-file=- \
    --project="${PROJECT_ID}"

# Optional: GitHub Token
echo -n "YOUR_GITHUB_TOKEN_HERE" | gcloud secrets create GITHUB_TOKEN \
  --data-file=- \
  --replication-policy="automatic" \
  --project="${PROJECT_ID}" || \
  echo -n "YOUR_GITHUB_TOKEN_HERE" | gcloud secrets versions add GITHUB_TOKEN \
    --data-file=- \
    --project="${PROJECT_ID}"

# Optional: Notion API Key (required for Notion integration)
echo -n "YOUR_NOTION_API_KEY_HERE" | gcloud secrets create NOTION_API_KEY \
  --data-file=- \
  --replication-policy="automatic" \
  --project="${PROJECT_ID}" || \
  echo -n "YOUR_NOTION_API_KEY_HERE" | gcloud secrets versions add NOTION_API_KEY \
    --data-file=- \
    --project="${PROJECT_ID}"

# Grant service account access to all secrets
for SECRET_NAME in GOOGLE_API_KEY TAVILY_API_KEY YOUTUBE_API_KEY GITHUB_TOKEN NOTION_API_KEY; do
  gcloud secrets add-iam-policy-binding "${SECRET_NAME}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor" \
    --project="${PROJECT_ID}" 2>/dev/null || echo "Permission already granted for ${SECRET_NAME}"
done
```

**Note for Notion Integration:**
- You'll also need to set `NOTION_PARENT_PAGE_ID` as an environment variable (see Step 8)
- To get your Notion Parent Page ID:
  1. Open your Notion page
  2. Click "Share" → "Copy link"
  3. The page ID is the last part of the URL (32 hex characters, may have dashes)
  4. Example: `https://www.notion.so/My-Page-abc123def456...` → Page ID is `abc123def456...`

## Step 6: Create Cloud Storage Bucket

```bash
# Create bucket for persistent storage
gsutil mb -p ${PROJECT_ID} -c STANDARD -l ${REGION} gs://${PROJECT_ID}-research-copilot-data || \
  echo "Bucket already exists"

# Grant service account access to the bucket
gsutil iam ch serviceAccount:${SA_EMAIL}:roles/storage.objectAdmin \
  gs://${PROJECT_ID}-research-copilot-data || echo "Permissions already set"
```

## Step 7: Get Hugging Face Token (Recommended)

To avoid rate limiting when downloading the embedding model, get a Hugging Face token:

```bash
# 1. Go to https://huggingface.co/settings/tokens
# 2. Create a new token (read access is sufficient)
# 3. Copy the token (starts with "hf_")

# Set it as an environment variable
export HF_TOKEN="hf_your_token_here"
```

**Note**: The token is optional but highly recommended. Without it, model downloads may hit rate limits (429 errors). The code includes retry logic, but authenticated downloads are much more reliable.

## Step 8: Build Docker Image Using Cloud Build

```bash
# Build and push image using Cloud Build (no local Docker needed!)
# Include HF_TOKEN if you have one (recommended)
if [ -n "$HF_TOKEN" ]; then
  gcloud builds submit \
    --config=cloudbuild.yaml \
    --project=${PROJECT_ID} \
    --substitutions=_REGION=${REGION},_REPO_NAME=${REPO_NAME},_SERVICE_NAME=${SERVICE_NAME},_HF_TOKEN=${HF_TOKEN} \
    .
else
  echo "⚠ Warning: Building without HF_TOKEN - model downloads may hit rate limits"
  gcloud builds submit \
    --config=cloudbuild.yaml \
    --project=${PROJECT_ID} \
    --substitutions=_REGION=${REGION},_REPO_NAME=${REPO_NAME},_SERVICE_NAME=${SERVICE_NAME} \
    .
fi

# This will:
# 1. Upload your code to Cloud Build
# 2. Build the Docker image on Google's infrastructure
# 3. Pre-download the embedding model (if HF_TOKEN provided)
# 4. Push the image to Artifact Registry (tags: BUILD_ID and latest)
# 5. Take about 10-15 minutes (includes model downloads)

# Note: If you have a previous image, don't worry! Cloud Run will use the "latest" tag,
# so your new build will automatically replace it. Old images remain in Artifact Registry
# but won't be used unless you explicitly reference them.
```

## Step 9: Deploy to Cloud Run

```bash
# Set image name
export IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:latest"

# Set your Notion Parent Page ID (replace with your actual page ID)
# To get it: Open Notion page → Share → Copy link → Extract the UUID from the URL
export NOTION_PARENT_PAGE_ID="your-notion-page-id-here"  # 32 hex chars, with or without dashes

# Deploy to Cloud Run
gcloud run deploy ${SERVICE_NAME} \
  --image ${IMAGE_NAME} \
  --region ${REGION} \
  --service-account ${SA_EMAIL} \
  --memory 4Gi \
  --cpu 2 \
  --timeout 3600 \
  --max-instances 10 \
  --min-instances 0 \
  --set-env-vars="GCS_BUCKET_NAME=${PROJECT_ID}-research-copilot-data,QDRANT_DB_PATH=/tmp/qdrant_db,PARENT_STORE_PATH=/tmp/parent_store,MARKDOWN_DIR=/tmp/markdown_docs,GRADIO_SERVER_NAME=0.0.0.0,GRADIO_SERVER_PORT=7860,LLM_PROVIDER=google,LLM_MODEL=gemini-2.5-flash,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},USE_GITHUB_MCP=false,USE_WEB_SEARCH_MCP=false,USE_NOTION_MCP=false,NOTION_PARENT_PAGE_ID=${NOTION_PARENT_PAGE_ID}" \
  --port 7860 \
  --allow-unauthenticated \
  --project=${PROJECT_ID}

# The deployment will output a URL like:
# https://research-copilot-xxxxx-uc.a.run.app
```

**Important for Notion Integration:**
- Make sure your Notion integration has access to the parent page:
  1. Open your Notion page
  2. Click "Share" (top right)
  3. Click "Add people, emails, groups, or integrations"
  4. Search for your integration name and add it
  5. Make sure the integration has "Can edit" or "Full access" permissions

## Step 10: Verify Deployment

```bash
# Get the service URL
gcloud run services describe ${SERVICE_NAME} \
  --region=${REGION} \
  --project=${PROJECT_ID} \
  --format="value(status.url)"

# View logs
gcloud run services logs read ${SERVICE_NAME} \
  --region=${REGION} \
  --project=${PROJECT_ID} \
  --limit=50
```

## Quick Reference: All Commands in One Script

Save this as `deploy.sh` and run it:

```bash
#!/bin/bash
set -e

# Configuration
export PROJECT_ID="your-project-id"  # CHANGE THIS
export REGION="us-central1"
export SERVICE_NAME="research-copilot"
export REPO_NAME="research-copilot"
export SA_NAME="research-copilot"
export SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "🚀 Starting deployment..."

# Step 1: Set project
gcloud config set project ${PROJECT_ID}

# Step 2: Enable APIs
echo "📦 Enabling APIs..."
gcloud services enable \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  --project=${PROJECT_ID}

# Step 3: Create service account
echo "👤 Creating service account..."
gcloud iam service-accounts create ${SA_NAME} \
  --display-name="Research Copilot Runtime Service Account" \
  --project=${PROJECT_ID} 2>/dev/null || echo "Service account already exists"

# Grant permissions
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.admin" --condition=None 2>/dev/null || true

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor" --condition=None 2>/dev/null || true

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/logging.logWriter" --condition=None 2>/dev/null || true

YOUR_EMAIL=$(gcloud config get-value account)
gcloud iam service-accounts add-iam-policy-binding ${SA_EMAIL} \
  --member="user:${YOUR_EMAIL}" \
  --role="roles/iam.serviceAccountUser" \
  --project=${PROJECT_ID} 2>/dev/null || true

PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format="value(projectNumber)")
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/artifactregistry.writer" --condition=None 2>/dev/null || true

# Step 4: Create Artifact Registry
echo "📦 Creating Artifact Registry..."
gcloud artifacts repositories create ${REPO_NAME} \
  --repository-format=docker \
  --location=${REGION} \
  --description="Docker repository for Research Copilot" \
  --project=${PROJECT_ID} 2>/dev/null || echo "Repository already exists"

# Step 5: Create secrets (you'll need to add your API keys)
echo "🔐 Creating secrets..."
echo "⚠️  Please add your API keys to Secret Manager manually or update this script"

# Step 6: Create Cloud Storage bucket
echo "🗄️  Creating Cloud Storage bucket..."
gsutil mb -p ${PROJECT_ID} -c STANDARD -l ${REGION} \
  gs://${PROJECT_ID}-research-copilot-data 2>/dev/null || echo "Bucket already exists"

gsutil iam ch serviceAccount:${SA_EMAIL}:roles/storage.objectAdmin \
  gs://${PROJECT_ID}-research-copilot-data 2>/dev/null || true

# Step 7: Get Hugging Face Token (optional but recommended)
echo "🔑 Setting up Hugging Face token..."
export HF_TOKEN="${HF_TOKEN:-}"  # Set this if you have a token from https://huggingface.co/settings/tokens
if [ -z "$HF_TOKEN" ]; then
  echo "⚠ Warning: HF_TOKEN not set - model downloads may hit rate limits"
fi

# Step 8: Build image
echo "🔨 Building Docker image (this takes 10-15 minutes)..."
if [ -n "$HF_TOKEN" ]; then
  gcloud builds submit \
    --config=cloudbuild.yaml \
    --project=${PROJECT_ID} \
    --substitutions=_REGION=${REGION},_REPO_NAME=${REPO_NAME},_SERVICE_NAME=${SERVICE_NAME},_HF_TOKEN=${HF_TOKEN} \
    .
else
  gcloud builds submit \
    --config=cloudbuild.yaml \
    --project=${PROJECT_ID} \
    --substitutions=_REGION=${REGION},_REPO_NAME=${REPO_NAME},_SERVICE_NAME=${SERVICE_NAME} \
    .
fi

# Step 9: Deploy to Cloud Run
echo "🚀 Deploying to Cloud Run..."
export IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:latest"

# Set Notion Parent Page ID (optional - only if using Notion integration)
export NOTION_PARENT_PAGE_ID="${NOTION_PARENT_PAGE_ID:-}"  # Set this if using Notion

gcloud run deploy ${SERVICE_NAME} \
  --image ${IMAGE_NAME} \
  --region ${REGION} \
  --service-account ${SA_EMAIL} \
  --memory 4Gi \
  --cpu 2 \
  --timeout 3600 \
  --max-instances 10 \
  --min-instances 0 \
  --set-env-vars="GCS_BUCKET_NAME=${PROJECT_ID}-research-copilot-data,QDRANT_DB_PATH=/tmp/qdrant_db,PARENT_STORE_PATH=/tmp/parent_store,MARKDOWN_DIR=/tmp/markdown_docs,GRADIO_SERVER_NAME=0.0.0.0,GRADIO_SERVER_PORT=7860,LLM_PROVIDER=google,LLM_MODEL=gemini-2.5-flash,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},USE_GITHUB_MCP=false,USE_WEB_SEARCH_MCP=false,USE_NOTION_MCP=false,NOTION_PARENT_PAGE_ID=${NOTION_PARENT_PAGE_ID}" \
  --port 7860 \
  --allow-unauthenticated \
  --project=${PROJECT_ID}

echo "✅ Deployment complete!"
echo "🌐 Service URL:"
gcloud run services describe ${SERVICE_NAME} \
  --region=${REGION} \
  --project=${PROJECT_ID} \
  --format="value(status.url)"
```

## Important Notes

1. **MCP is Disabled**: The deployment sets `USE_GITHUB_MCP=false`, `USE_WEB_SEARCH_MCP=false`, and `USE_NOTION_MCP=false` because MCP servers require local processes that don't work well in Cloud Run. The application will use direct API calls instead.

2. **Hugging Face Token (Recommended)**: 
   - Get a free token from https://huggingface.co/settings/tokens (read access is sufficient)
   - Set `HF_TOKEN` environment variable before building (Step 7)
   - This prevents rate limiting (429 errors) when downloading the embedding model
   - Without it, the code includes retry logic, but authenticated downloads are more reliable

3. **Secrets**: Make sure to replace `YOUR_GOOGLE_API_KEY_HERE`, `YOUR_TAVILY_API_KEY_HERE`, etc. with your actual API keys in Step 5.

4. **Notion Integration**: 
   - Requires `NOTION_API_KEY` secret (created in Step 5)
   - Requires `NOTION_PARENT_PAGE_ID` environment variable (set in Step 9)
   - Make sure your Notion integration has access to the parent page (see Step 9 instructions)

5. **Previous Images**: If you've built images before, **you don't need to delete them**. Cloud Run uses the `latest` tag, so your new build automatically becomes the active version. Old images remain in Artifact Registry but won't be used unless you explicitly reference a specific tag. You can optionally clean them up later to save storage costs.

6. **First Build**: The first build takes 10-15 minutes because it downloads embedding models. Subsequent builds are faster.

7. **Costs**: Expect ~$5-15/month for moderate usage (see README.md for details).

8. **Storage**: Data persists in Cloud Storage, so your Qdrant database and documents survive container restarts.

## Troubleshooting

### Build Fails
```bash
# Check build logs
gcloud builds list --project=${PROJECT_ID} --limit=1
gcloud builds log $(gcloud builds list --project=${PROJECT_ID} --limit=1 --format="value(id)") --project=${PROJECT_ID}
```

### Service Won't Start
```bash
# Check service logs
gcloud run services logs read ${SERVICE_NAME} --region=${REGION} --project=${PROJECT_ID}
```

### Secrets Not Found
```bash
# Verify secrets exist
gcloud secrets list --project=${PROJECT_ID}

# Check service account has access
gcloud secrets get-iam-policy GOOGLE_API_KEY --project=${PROJECT_ID}
```

## Updating After Code Changes

```bash
# Set HF_TOKEN if you have one (recommended)
export HF_TOKEN="${HF_TOKEN:-}"  # Set this if you have a token

# Rebuild with HF_TOKEN if available
if [ -n "$HF_TOKEN" ]; then
  gcloud builds submit \
    --config=cloudbuild.yaml \
    --project=${PROJECT_ID} \
    --substitutions=_REGION=${REGION},_REPO_NAME=${REPO_NAME},_SERVICE_NAME=${SERVICE_NAME},_HF_TOKEN=${HF_TOKEN} \
    .
else
  gcloud builds submit \
    --config=cloudbuild.yaml \
    --project=${PROJECT_ID} \
    --substitutions=_REGION=${REGION},_REPO_NAME=${REPO_NAME},_SERVICE_NAME=${SERVICE_NAME} \
    .
fi

# Redeploy (include all environment variables)
export NOTION_PARENT_PAGE_ID="${NOTION_PARENT_PAGE_ID:-}"  # Set if using Notion

gcloud run deploy ${SERVICE_NAME} \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:latest \
  --region ${REGION} \
  --set-env-vars="GCS_BUCKET_NAME=${PROJECT_ID}-research-copilot-data,QDRANT_DB_PATH=/tmp/qdrant_db,PARENT_STORE_PATH=/tmp/parent_store,MARKDOWN_DIR=/tmp/markdown_docs,GRADIO_SERVER_NAME=0.0.0.0,GRADIO_SERVER_PORT=7860,LLM_PROVIDER=google,LLM_MODEL=gemini-2.5-flash,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},USE_GITHUB_MCP=false,USE_WEB_SEARCH_MCP=false,USE_NOTION_MCP=false,NOTION_PARENT_PAGE_ID=${NOTION_PARENT_PAGE_ID}" \
  --project=${PROJECT_ID}
```

## Cleanup

To delete everything:

```bash
# Delete Cloud Run service
gcloud run services delete ${SERVICE_NAME} --region=${REGION} --project=${PROJECT_ID}

# Delete Cloud Storage bucket (WARNING: Deletes all data!)
gsutil rm -r gs://${PROJECT_ID}-research-copilot-data

# Delete secrets
for SECRET in GOOGLE_API_KEY TAVILY_API_KEY YOUTUBE_API_KEY GITHUB_TOKEN NOTION_API_KEY; do
  gcloud secrets delete ${SECRET} --project=${PROJECT_ID} 2>/dev/null || true
done

# Delete service account
gcloud iam service-accounts delete ${SA_EMAIL} --project=${PROJECT_ID}

# Delete Artifact Registry repository
gcloud artifacts repositories delete ${REPO_NAME} --location=${REGION} --project=${PROJECT_ID}
```
