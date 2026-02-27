#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

ENV="${1:-}"
ACTION="${2:-}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${PROJECT_ROOT}/logs/deploy_${TIMESTAMP}.log"

usage() {
    echo "Usage: $0 [dev|staging|prod] [deploy|canary|promote|rollback]"
    echo ""
    echo "Commands:"
    echo "  deploy   - Deploy new version (green environment)"
    echo "  canary   - Start canary deployment (10% traffic)"
    echo "  promote  - Promote green to 100% traffic"
    echo "  rollback - Rollback to blue environment"
    exit 1
}

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

error() {
    log "ERROR: $*" >&2
    exit 1
}

validate_env() {
    case "$ENV" in
        dev|staging|prod) ;;
        *) error "Invalid environment: $ENV. Use dev, staging, or prod" ;;
    esac
}

validate_action() {
    case "$ACTION" in
        deploy|canary|promote|rollback) ;;
        *) usage ;;
    esac
}

load_config() {
    local config_file="${PROJECT_ROOT}/config/${ENV}.env"
    if [[ -f "$config_file" ]]; then
        log "Loading configuration from $config_file"
        set -a
        source "$config_file"
        set +a
    else
        error "Configuration file not found: $config_file"
    fi
}

check_prerequisites() {
    log "Checking prerequisites..."
    
    command -v gcloud >/dev/null 2>&1 || error "gcloud CLI not found"
    command -v terraform >/dev/null 2>&1 || error "terraform not found"
    
    gcloud config get-value project >/dev/null 2>&1 || error "gcloud not authenticated"
    
    if [[ -n "${GCLOUD_PROJECT:-}" ]]; then
        gcloud config set project "$GCLOUD_PROJECT" --quiet
    fi
    
    log "Prerequisites check passed"
}

deploy_green() {
    log "Deploying GREEN environment to $ENV..."
    
    cd "${PROJECT_ROOT}/terraform"
    
    terraform workspace select "$ENV" 2>/dev/null || terraform workspace new "$ENV"
    
    export TF_VAR_environment="$ENV"
    export TF_VAR_deployment_color="green"
    export TF_VAR_deployment_timestamp="$TIMESTAMP"
    
    terraform init
    terraform plan -out="tfplan"
    terraform apply "tfplan"
    
    GREEN_URL=$(terraform output -raw green_service_url 2>/dev/null || echo "")
    
    if [[ -z "$GREEN_URL" ]]; then
        error "Failed to get GREEN service URL"
    fi
    
    log "GREEN environment deployed: $GREEN_URL"
    
    log "Running health checks on GREEN..."
    if ! "${SCRIPT_DIR}/health_check.sh" "$GREEN_URL"; then
        error "Health checks failed on GREEN environment"
    fi
    
    log "GREEN deployment successful"
    echo "$GREEN_URL" > "${PROJECT_ROOT}/.green_url"
}

start_canary() {
    log "Starting canary deployment (10% traffic)..."
    
    if [[ ! -f "${PROJECT_ROOT}/.green_url" ]]; then
        error "No GREEN deployment found. Run deploy first."
    fi
    
    cd "${PROJECT_ROOT}/terraform"
    
    export TF_VAR_environment="$ENV"
    export TF_VAR_traffic_split='{"green": 10, "blue": 90}'
    
    terraform init
    terraform apply -auto-approve
    
    log "Canary deployment active (10% traffic to GREEN)"
    
    log "Starting monitoring for 5 minutes..."
    "${SCRIPT_DIR}/monitor.sh" "$ENV" 300 || {
        log "Canary monitoring detected issues, rolling back..."
        rollback
        exit 1
    }
    
    log "Canary deployment successful"
}

promote() {
    log "Promoting GREEN to 100% traffic..."
    
    cd "${PROJECT_ROOT}/terraform"
    
    export TF_VAR_environment="$ENV"
    export TF_VAR_traffic_split='{"green": 100, "blue": 0}'
    
    terraform init
    terraform apply -auto-approve
    
    log "Promotion complete. GREEN is now 100%"
    
    log "Waiting 60 seconds before destroying BLUE..."
    sleep 60
    
    export TF_VAR_deployment_color="green"
    export TF_VAR_traffic_split='{"green": 100}'
    terraform apply -auto-approve
    
    rm -f "${PROJECT_ROOT}/.green_url"
    log "BLUE environment cleaned up"
}

rollback() {
    log "Initiating ROLLBACK to BLUE..."
    
    cd "${PROJECT_ROOT}/terraform"
    
    export TF_VAR_environment="$ENV"
    export TF_VAR_traffic_split='{"blue": 100}'
    
    terraform init
    terraform apply -auto-approve
    
    log "Rollback complete. BLUE is now 100%"
    
    if [[ -f "${PROJECT_ROOT}/.green_url" ]]; then
        log "Cleaning up failed GREEN deployment..."
        export TF_VAR_deployment_color="blue"
        terraform apply -auto-approve
        rm -f "${PROJECT_ROOT}/.green_url"
    fi
    
    log "Rollback successful"
}

main() {
    mkdir -p "${PROJECT_ROOT}/logs"
    
    if [[ $# -lt 2 ]]; then
        usage
    fi
    
    validate_env
    validate_action
    load_config
    check_prerequisites
    
    log "Starting deployment action: $ACTION in environment: $ENV"
    
    case "$ACTION" in
        deploy)  deploy_green ;;
        canary)  start_canary ;;
        promote) promote ;;
        rollback) rollback ;;
    esac
    
    log "Deployment action completed: $ACTION"
}

main "$@"
