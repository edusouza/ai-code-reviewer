# Deployment Guide

This guide walks you through deploying the AI Code Reviewer to Google Cloud Platform.

## Prerequisites

### 1. Google Cloud Project Setup

```bash
# Create a new project (or use existing)
gcloud projects create ai-code-reviewer-prod --name="AI Code Reviewer"
gcloud config set project ai-code-reviewer-prod

# Enable required APIs
gcloud services enable run.googleapis.com
gcloud services enable firestore.googleapis.com
gcloud services enable pubsub.googleapis.com
gcloud services enable aiplatform.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable monitoring.googleapis.com
gcloud services enable logging.googleapis.com
```

### 2. Service Account Setup

```bash
# Create service account
gcloud iam service-accounts create ai-reviewer \
    --display-name="AI Code Reviewer"

# Grant necessary permissions
gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:ai-reviewer@PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/datastore.user"

gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:ai-reviewer@PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/pubsub.publisher"

gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:ai-reviewer@PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"
```

### 3. Firestore Database

```bash
# Create Firestore database (Native mode)
gcloud firestore databases create --location=nam5
```

## Step-by-Step Deployment

### Step 1: Clone and Configure

```bash
git clone https://github.com/yourusername/ai-code-reviewer.git
cd ai-code-reviewer

# Copy environment template
cp .env.example .env
```

Edit `.env` with your production values:
- `PROJECT_ID`: Your GCP project ID
- Provider credentials (GitHub/GitLab/Bitbucket)

### Step 2: Infrastructure with Terraform

```bash
cd infrastructure/terraform

# Initialize Terraform
terraform init

# Create workspace for environment
terraform workspace new prod
terraform workspace select prod

# Review the plan
terraform plan

# Apply infrastructure
terraform apply
```

This creates:
- Cloud Run service
- Pub/Sub topic and subscriptions
- Service accounts and IAM bindings
- Firestore database (if not exists)

### Step 3: Build and Deploy

#### Option A: Using Cloud Build (Recommended)

```bash
# Submit build
gcloud builds submit --tag gcr.io/PROJECT_ID/ai-code-reviewer:latest

# Deploy to Cloud Run
gcloud run deploy ai-code-reviewer \
    --image gcr.io/PROJECT_ID/ai-code-reviewer:latest \
    --platform managed \
    --region us-central1 \
    --service-account ai-reviewer@PROJECT_ID.iam.gserviceaccount.com \
    --set-env-vars "PROJECT_ID=PROJECT_ID" \
    --set-env-vars "GITHUB_WEBHOOK_SECRET=YOUR_SECRET" \
    --set-env-vars "GITHUB_APP_ID=YOUR_APP_ID" \
    --set-env-vars "GITHUB_PRIVATE_KEY=$(cat private-key.pem)" \
    --allow-unauthenticated
```

#### Option B: Using Make Commands

```bash
# Initialize
make init

# Deploy (blue-green)
make deploy ENV=prod

# Start canary (10% traffic)
make canary ENV=prod

# Monitor
make monitor ENV=prod

# Promote to 100%
make promote ENV=prod
```

### Step 4: Get Service URL

```bash
gcloud run services describe ai-code-reviewer \
    --region us-central1 \
    --format 'value(status.url)'
```

Save this URL - you'll need it for webhook configuration.

## Git Provider Setup

### GitHub App

1. Go to **Settings → Developer settings → GitHub Apps → New GitHub App**

2. Configure:
   - **GitHub App Name**: `AI Code Reviewer`
   - **Homepage URL**: Your repository URL
   - **Webhook URL**: `https://YOUR_SERVICE_URL/webhooks/github`
   - **Webhook Secret**: Generate a secure secret
   
3. Permissions:
   - **Pull requests**: Read & Write
   - **Contents**: Read
   - **Issues**: Read & Write (for feedback)
   - **Metadata**: Read

4. Subscribe to events:
   - Pull request
   - Pull request review
   - Pull request review comment

5. Generate and download private key

6. Install the app on your repositories

7. Update your `.env` with:
   ```bash
   GITHUB_WEBHOOK_SECRET=your-webhook-secret
   GITHUB_APP_ID=123456
   GITHUB_PRIVATE_KEY=-----BEGIN RSA PRIVATE KEY-----
   ...
   -----END RSA PRIVATE KEY-----
   ```

### GitLab Integration

1. Go to your project **Settings → Webhooks**

2. Add webhook:
   - **URL**: `https://YOUR_SERVICE_URL/webhooks/gitlab`
   - **Secret Token**: Generate a secure token
   - **Trigger**: Merge request events, Comment events

3. Create a personal access token:
   - **Scope**: `api`, `read_repository`

4. Update your `.env`:
   ```bash
   GITLAB_WEBHOOK_SECRET=your-webhook-secret
   GITLAB_TOKEN=glpat-your-token
   ```

### Bitbucket Integration

1. Go to **Repository settings → Webhooks → Add webhook**

2. Configure:
   - **Title**: AI Code Reviewer
   - **URL**: `https://YOUR_SERVICE_URL/webhooks/bitbucket`
   - **Triggers**: Pull request created, Pull request updated

3. Generate app password:
   - **Settings → App passwords → Create app password**
   - **Permissions**: Pull requests: Read & Write, Repositories: Read

4. Update your `.env`:
   ```bash
   BITBUCKET_WEBHOOK_SECRET=your-webhook-secret
   BITBUCKET_USERNAME=your-username
   BITBUCKET_APP_PASSWORD=your-app-password
   ```

## Environment Configuration

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `PROJECT_ID` | GCP project ID | `my-project-123` |
| `GITHUB_WEBHOOK_SECRET` | GitHub webhook secret | `whsec_...` |
| `GITHUB_APP_ID` | GitHub App ID | `123456` |
| `GITHUB_PRIVATE_KEY` | GitHub App private key | `-----BEGIN...` |
| `GITLAB_WEBHOOK_SECRET` | GitLab webhook secret | `glpat_...` |
| `GITLAB_TOKEN` | GitLab access token | `glpat_...` |
| `FIRESTORE_DATABASE` | Firestore database name | `(default)` |
| `PUBSUB_TOPIC` | Pub/Sub topic name | `code-reviews` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DEBUG` | Enable debug mode | `false` |
| `PORT` | Server port | `8080` |
| `MAX_TOKENS_PER_REVIEW` | Max tokens per review | `10000` |
| `ENABLE_COST_TRACKING` | Enable cost tracking | `true` |
| `ENABLE_LEARNING` | Enable learning | `true` |

## Verification Steps

### 1. Health Check

```bash
curl https://YOUR_SERVICE_URL/health

# Expected response:
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-01-15T10:30:00Z",
  "checks": {
    "firestore": "connected",
    "pubsub": "connected"
  }
}
```

### 2. Test Webhook

Create a test pull request in a connected repository. You should see:
- PR comment from AI Code Reviewer
- Suggestions with severity badges
- Reaction buttons for feedback

### 3. Check Logs

```bash
# View Cloud Run logs
gcloud logging read "resource.type=cloud_run_revision" \
    --limit=50 \
    --format="table(timestamp,textPayload)"

# Or use Cloud Console
# https://console.cloud.google.com/logs
```

### 4. Verify Pub/Sub

```bash
# List subscriptions
gcloud pubsub subscriptions list

# Check message backlog
gcloud pubsub subscriptions describe code-reviews-sub
```

## Troubleshooting

See [troubleshooting.md](troubleshooting.md) for common issues and solutions.

## Security Considerations

1. **Webhook Secrets**: Always use strong, unique secrets for each provider
2. **Private Keys**: Store GitHub private keys securely (Secret Manager recommended)
3. **Service Account**: Use minimal required permissions
4. **Network**: Consider VPC connector for private resources
5. **CORS**: Configure appropriate CORS settings in production

## Production Checklist

- [ ] All environment variables set correctly
- [ ] Webhook URLs configured in git providers
- [ ] Service account has proper permissions
- [ ] Firestore database created
- [ ] Pub/Sub topic and subscriptions created
- [ ] Health check endpoint responding
- [ ] Test PR created and reviewed successfully
- [ ] Monitoring and alerts configured
- [ ] Cost budget set up
- [ ] Documentation updated

## Next Steps

1. Configure [AGENTS.md](agents.md) for your repositories
2. Set up [monitoring and alerts](#)
3. Review [cost optimization tips](#)
4. Join the [community discussions](https://github.com/yourusername/ai-code-reviewer/discussions)
