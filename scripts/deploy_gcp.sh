#!/bin/bash
# GCP Deployment Script for Research Copilot
# Usage: ./scripts/deploy_gcp.sh

set -e

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-your-project-id}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="research-copilot"
IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${SERVICE_NAME}/${SERVICE_NAME}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Deploying Research Copilot to GCP...${NC}"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo ""

# Check if PROJECT_ID is set
if [ "$PROJECT_ID" == "your-project-id" ]; then
    echo -e "${RED}❌ Error: GCP_PROJECT_ID not set${NC}"
    echo "Set it with: export GCP_PROJECT_ID=your-project-id"
    exit 1
fi

# Set active project
echo "📋 Setting active project..."
gcloud config set project $PROJECT_ID

# Build Docker image
echo -e "${YELLOW}📦 Building Docker image...${NC}"
docker build -t ${IMAGE_NAME}:latest .

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Docker build failed${NC}"
    exit 1
fi

# Push to Artifact Registry
echo -e "${YELLOW}📤 Pushing to Artifact Registry...${NC}"
docker push ${IMAGE_NAME}:latest

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Docker push failed${NC}"
    echo "Make sure you've run: gcloud auth configure-docker ${REGION}-docker.pkg.dev"
    exit 1
fi

# Deploy to Cloud Run
echo -e "${YELLOW}☁️ Deploying to Cloud Run...${NC}"
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

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Deployment failed${NC}"
    exit 1
fi

# Get service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --region ${REGION} \
    --format 'value(status.url)' 2>/dev/null)

if [ -z "$SERVICE_URL" ]; then
    echo -e "${YELLOW}⚠️ Could not retrieve service URL${NC}"
else
    echo ""
    echo -e "${GREEN}✅ Deployment complete!${NC}"
    echo -e "${GREEN}🌐 Service URL: $SERVICE_URL${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Open the URL in your browser"
    echo "2. Test the Research tab"
    echo "3. Check logs: gcloud run services logs read ${SERVICE_NAME} --region=${REGION}"
fi
