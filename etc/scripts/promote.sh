#!/bin/bash
set -e

# Parse command line arguments
ROLE_NAME="civic-elevated"
MFA_TOKEN=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --role)
      ROLE_NAME="$2"
      shift 2
      ;;
    --mfa-token)
      MFA_TOKEN="$2"
      shift 2
      ;;
    *)
      echo "❌ Error: Unknown argument '$1'"
      echo "Usage: $0 --mfa-token <token> [--role <role-name>]"
      exit 1
      ;;
  esac
done

# Configuration
REGION="us-east-1"
ECR_PREFIX="civic-mcp"
SERVICE_NAME="postgres-mcp"
IMAGE_TAG="latest"

# ECR registries
DEV_ECR_REGISTRY="249634870252.dkr.ecr.us-east-1.amazonaws.com"
PROD_ECR_REGISTRY="883607224354.dkr.ecr.us-east-1.amazonaws.com"
PROD_ACCOUNT_ID="883607224354"

# Check if MFA token is provided
if [[ -z "$MFA_TOKEN" ]]; then
  echo "❌ Error: MFA token is required. Use --mfa-token parameter."
  echo "Usage: $0 --mfa-token <token> [--role <role-name>]"
  exit 1
fi

echo "🚀 Promoting $SERVICE_NAME from dev to prod"
echo "📋 Using role: $ROLE_NAME"
echo "🔑 MFA token: $MFA_TOKEN"

# Check if crane is installed
if ! command -v crane &> /dev/null; then
  echo "❌ Error: crane is not installed. Please install it with:"
  echo "   brew install crane"
  echo "   or visit: https://github.com/google/go-containerregistry/blob/main/cmd/crane/README.md"
  exit 1
fi

# Get dev ECR password
echo "🔑 Getting dev ECR credentials..."
DEV_PASSWORD=$(aws ecr get-login-password --region $REGION)

# Assume role for prod account
echo "🔐 Assuming role $ROLE_NAME in prod account..."

# Get MFA device serial number
MFA_SERIAL=$(aws sts get-caller-identity --query 'Arn' --output text | sed 's/:user\//:mfa\//g')
echo "🔑 Using MFA device: $MFA_SERIAL"

PROD_CREDS=$(aws sts assume-role \
  --role-arn "arn:aws:iam::${PROD_ACCOUNT_ID}:role/${ROLE_NAME}" \
  --role-session-name "ecr-promote-session" \
  --serial-number "$MFA_SERIAL" \
  --token-code "$MFA_TOKEN" \
  --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
  --output text)

if [[ -z "$PROD_CREDS" ]]; then
  echo "❌ Error: Failed to assume role $ROLE_NAME"
  exit 1
fi

# Extract the credentials
AWS_ACCESS_KEY_ID=$(echo "$PROD_CREDS" | cut -d' ' -f1)
AWS_SECRET_ACCESS_KEY=$(echo "$PROD_CREDS" | cut -d' ' -f2)
AWS_SESSION_TOKEN=$(echo "$PROD_CREDS" | cut -d' ' -f3)

# Get prod ECR password with assumed role
echo "🔑 Getting prod ECR credentials with assumed role..."
PROD_PASSWORD=$(AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
  AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
  AWS_SESSION_TOKEN=$AWS_SESSION_TOKEN \
  aws ecr get-login-password --region $REGION)

# Login to both registries with crane
echo "🔓 Logging into dev ECR with crane..."
echo "$DEV_PASSWORD" | crane auth login $DEV_ECR_REGISTRY -u AWS --password-stdin

echo "🔓 Logging into prod ECR with crane..."
echo "$PROD_PASSWORD" | crane auth login $PROD_ECR_REGISTRY -u AWS --password-stdin

# Create repository in prod if it doesn't exist
REPO_NAME="$ECR_PREFIX/$SERVICE_NAME"
echo "📦 Ensuring prod repository exists..."

if ! AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
     AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
     AWS_SESSION_TOKEN=$AWS_SESSION_TOKEN \
     aws ecr describe-repositories --repository-names "$REPO_NAME" --region $REGION &> /dev/null; then
  echo "📦 Creating repository $REPO_NAME in prod..."
  AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
  AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
  AWS_SESSION_TOKEN=$AWS_SESSION_TOKEN \
  aws ecr create-repository --repository-name "$REPO_NAME" --region $REGION
fi

# Promote the image
DEV_IMAGE="$DEV_ECR_REGISTRY/$REPO_NAME:$IMAGE_TAG"
PROD_IMAGE="$PROD_ECR_REGISTRY/$REPO_NAME:$IMAGE_TAG"

echo ""
echo "📤 Promoting $SERVICE_NAME..."
echo "   From: $DEV_IMAGE"
echo "   To:   $PROD_IMAGE"

if crane copy $DEV_IMAGE $PROD_IMAGE; then
  echo "✅ Successfully promoted $SERVICE_NAME"
else
  echo "❌ Failed to promote $SERVICE_NAME"
  exit 1
fi

echo ""
echo "🎉 Promotion complete!"
echo "Image: $PROD_IMAGE"
