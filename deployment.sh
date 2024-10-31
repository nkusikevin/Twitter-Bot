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
MIN_INSTANCES=1 

# Deploy to Cloud Run
echo "Deploying to Cloud Run..."
echo "OPenAI_API_KEY: $OPENAI_API_KEY"
gcloud run deploy $SERVICE_NAME \
    --source . \
    --port 8080 \
    --project $PROJECT_ID \
    --allow-unauthenticated \
     --min-instances $MIN_INSTANCES \
    --region $REGION \
     --min-instances 1 \
    --cpu 1 \
    --memory 512Mi \
    --set-env-vars=OPENAI_API_KEY=$OPENAI_API_KEY,\
TWITTER_CONSUMER_KEY=$TWITTER_CONSUMER_KEY,\
TWITTER_CONSUMER_SECRET=$TWITTER_CONSUMER_SECRET,\
TWITTER_ACCESS_TOKEN=$TWITTER_ACCESS_TOKEN,\
TWITTER_ACCESS_TOKEN_SECRET=$TWITTER_ACCESS_TOKEN_SECRET,\
GUNICORN_CMD_ARGS="--bind :$PORT --workers=4  --timeout=120 --worker-class=gthread --threads=4 --access-logfile=- --error-logfile=- --log-level=info" \
    || error "Deployment failed"
# GOOGLE_ENTRYPOINT="gunicorn --bind :$PORT main:app" \

echo "Deployment completed successfully!"

# Get the URL of the deployed service
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --project $PROJECT_ID --platform managed --region $REGION --format 'value(status.url)')

#start the gunicorn server after deployment


# Set up Cloud Scheduler to keep the service warm
echo "Setting up Cloud Scheduler..."
gcloud scheduler jobs create http keep-twitter-bot-warm \
    --schedule="*/10 * * * *" \
    --uri="${SERVICE_URL}" \
    --http-method=GET \
    --attempt-deadline=30s \
    --project $PROJECT_ID \
    --location $REGION \
    || echo "Scheduler job already exists"

echo "Deployment completed successfully!"
echo "Your service is available at: $SERVICE_URL"