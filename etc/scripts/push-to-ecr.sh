#!/bin/bash
set -e

# Usage: ./push-to-ecr.sh [env]
#   env: dev (default) or prod

# Configuration
ENV=${1:-dev}
REGION="us-east-1"
ECR_PREFIX="civic-mcp"
SERVICE_NAME="postgres-mcp"
IMAGE_TAG="latest"
ARCHITECTURES="linux/amd64,linux/arm64"

# Set ECR registry based on environment
if [[ "$ENV" == "prod" ]]; then
  ECR_REGISTRY="883607224354.dkr.ecr.us-east-1.amazonaws.com"
else
  ECR_REGISTRY="249634870252.dkr.ecr.us-east-1.amazonaws.com"
fi

echo "🚀 Using environment: $ENV with registry: $ECR_REGISTRY"

# Change to the repo root directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../.."
ROOT_DIR=$(pwd)
echo "📂 Working from repo root: $ROOT_DIR"

# Login to ECR
echo "🔑 Logging in to Amazon ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_REGISTRY

# Setup buildx builder for multi-architecture builds
echo "🔧 Setting up Docker buildx..."
docker buildx ls | grep -q mybuilder || docker buildx create --name mybuilder --use
docker buildx inspect --bootstrap

# Check if repository exists
REPO_NAME="$ECR_PREFIX/$SERVICE_NAME"
echo "🔍 Checking if repository $REPO_NAME exists..."

if ! aws ecr describe-repositories --repository-names "$REPO_NAME" --region $REGION &> /dev/null; then
  echo "📦 Creating repository $REPO_NAME..."
  aws ecr create-repository --repository-name "$REPO_NAME" --region $REGION
else
  echo "✅ Repository $REPO_NAME already exists"
fi

# Build and push the image
FULL_IMAGE_NAME="$ECR_REGISTRY/$REPO_NAME:$IMAGE_TAG"

echo "🔨 Building $SERVICE_NAME for multiple architectures ($ARCHITECTURES)..."
echo "📄 Using Dockerfile: ./Dockerfile with context: ."

# Build and push directly with buildx (--no-cache ensures fresh builds with latest security patches)
docker buildx build \
  --no-cache \
  --platform $ARCHITECTURES \
  --tag $FULL_IMAGE_NAME \
  --push \
  -f ./Dockerfile \
  .

echo "✅ Successfully built and pushed $FULL_IMAGE_NAME"
echo ""
echo "🎉 Image pushed to ECR!"
echo "Environment: $ENV"
echo "Registry: $ECR_REGISTRY"
echo "Image: $FULL_IMAGE_NAME"
