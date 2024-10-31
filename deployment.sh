#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Function to display error messages
error() {
    echo "ERROR: $1" >&2
    exit 1
}

# Check required environment variables
required_vars=(
    "OPENAI_API_KEY"
    "TWITTER_CONSUMER_KEY"
    "TWITTER_CONSUMER_SECRET"
    "TWITTER_ACCESS_TOKEN"
    "TWITTER_ACCESS_TOKEN_SECRET"
)

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        error "$var is not set. Please set it in your environment."
    fi
done

# Set default values
PROJECT_ID="twitter-bot-440221"
REGION="us-central1"
SERVICE_NAME="twitter-bot"

# Deploy to Cloud Run
echo "Deploying to Cloud Run..."
echo "OPenAI_API_KEY: $OPENAI_API_KEY"
gcloud run deploy $SERVICE_NAME \
    --source . \
    --port 8080 \
    --project $PROJECT_ID \
    --allow-unauthenticated \
    --region $REGION \
    --set-env-vars=OPENAI_API_KEY=$OPENAI_API_KEY,\
TWITTER_CONSUMER_KEY=$TWITTER_CONSUMER_KEY,\
TWITTER_CONSUMER_SECRET=$TWITTER_CONSUMER_SECRET,\
TWITTER_ACCESS_TOKEN=$TWITTER_ACCESS_TOKEN,\
TWITTER_ACCESS_TOKEN_SECRET=$TWITTER_ACCESS_TOKEN_SECRET,\
GOOGLE_ENTRYPOINT="gunicorn --bind :$PORT main:app" \
    || error "Deployment failed"

echo "Deployment completed successfully!"

# Get the URL of the deployed service
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)')

#run the app after deployment
gcloud run services exec $SERVICE_NAME --region $REGION -- curl $SERVICE_URL

echo "Your service is available at: $SERVICE_URL"