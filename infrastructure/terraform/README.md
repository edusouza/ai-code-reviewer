# Terraform Infrastructure for AI Code Reviewer

This directory contains Terraform configurations for deploying the AI Code Reviewer infrastructure on Google Cloud Platform.

## Architecture

- **Network**: VPC with private subnet, Cloud NAT, and VPC connector
- **IAM**: Service accounts with minimal permissions per module
- **Core**: Pub/Sub, Firestore, Cloud Run (API, Worker, Webhook) with blue-green deployment
- **LangFuse**: Cloud SQL (PostgreSQL) and LangFuse Cloud Run deployment
- **Observability**: BigQuery, Cloud Monitoring, and alerting

## Quick Start

### 1. Bootstrap

First, run the bootstrap configuration to set up the Terraform state bucket:

```bash
cd infrastructure/terraform/bootstrap
terraform init
terraform plan
terraform apply
```

### 2. Configure Backend

Update the backend bucket name in `environments/dev/backend.tf`:

```hcl
backend "gcs" {
  bucket = "YOUR_PROJECT_ID-terraform-state"  # Replace with your bucket name
  prefix = "terraform/state/dev"
}
```

### 3. Configure Variables

Copy and edit the tfvars file:

```bash
cd environments/dev
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your actual values:
- project_id
- Container image URLs
- API keys and secrets

### 4. Deploy

```bash
terraform init
terraform plan
terraform apply
```

## Module Structure

```
modules/
├── network/        # VPC, subnets, firewall, NAT
├── iam/            # Service accounts and IAM bindings
├── core/           # Firestore, Pub/Sub, Cloud Run services
├── langfuse/       # Cloud SQL, LangFuse deployment
└── observability/  # BigQuery, monitoring, alerts
```

## Environments

- **dev**: Development environment with minimal resources
- **staging**: Pre-production environment
- **prod**: Production environment with high availability

## Blue-Green Deployment

The core module supports blue-green deployment for the API service:
- Blue deployment (`api-blue`): Receives all traffic by default
- Green deployment (`api-green`): Used for testing new versions

To switch traffic:
1. Deploy to green: `terraform apply -var="blue_traffic_percentage=0"`
2. Test green deployment
3. Switch traffic: Update `blue_traffic_percentage` variable

## Security

- All secrets stored in Secret Manager
- Service accounts with least privilege
- VPC with private Google access
- Cloud SQL with private IP only

## Monitoring

Access the monitoring dashboard:
- Cloud Console > Monitoring > Dashboards
- Look for "AI Reviewer Dashboard"

## Troubleshooting

### Cloud Run services not accessible
Check IAM permissions and ensure public access is configured correctly.

### Pub/Sub messages not processing
Check:
- Worker subscription configuration
- Service account permissions
- Dead letter queue for failed messages

### Database connection issues
Verify:
- VPC connector configuration
- Cloud SQL connection name
- Service account has cloudsql.client role
