#!/bin/bash

set -euo pipefail

URL="${1:-}"
HEALTH_ENDPOINT="${2:-/health}"
READY_ENDPOINT="${3:-/ready}"
MAX_RETRIES="${4:-30}"
RETRY_DELAY="${5:-10}"
TIMEOUT="${6:-30}"

usage() {
    echo "Usage: $0 <url> [health_endpoint] [ready_endpoint] [max_retries] [retry_delay] [timeout]"
    echo ""
    echo "Example: $0 https://api.example.com"
    exit 1
}

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2
    exit 1
}

if [[ -z "$URL" ]]; then
    usage
fi

BASE_URL="${URL%/}"

check_endpoint() {
    local endpoint="$1"
    local full_url="${BASE_URL}${endpoint}"
    local attempt=0
    
    log "Checking endpoint: $full_url"
    
    while [[ $attempt -lt $MAX_RETRIES ]]; do
        attempt=$((attempt + 1))
        log "Attempt $attempt/$MAX_RETRIES: $full_url"
        
        local response
        local http_code
        
        response=$(curl -s -o /dev/null -w "%{http_code}|%{time_total}" \
            --max-time "$TIMEOUT" \
            --retry 0 \
            "$full_url" 2>/dev/null) || {
            log "  Connection failed (attempt $attempt)"
            sleep "$RETRY_DELAY"
            continue
        }
        
        http_code=$(echo "$response" | cut -d'|' -f1)
        response_time=$(echo "$response" | cut -d'|' -f2)
        
        if [[ "$http_code" == "200" ]]; then
            log "  SUCCESS: HTTP $http_code (response time: ${response_time}s)"
            return 0
        else
            log "  FAILED: HTTP $http_code (response time: ${response_time}s)"
        fi
        
        sleep "$RETRY_DELAY"
    done
    
    error "Health check failed after $MAX_RETRIES attempts"
}

check_health() {
    log "=== Health Check ==="
    check_endpoint "$HEALTH_ENDPOINT"
}

check_readiness() {
    log "=== Readiness Check ==="
    check_endpoint "$READY_ENDPOINT"
}

main() {
    log "Starting health checks for: $BASE_URL"
    log "Health endpoint: $HEALTH_ENDPOINT"
    log "Ready endpoint: $READY_ENDPOINT"
    log "Max retries: $MAX_RETRIES, Retry delay: ${RETRY_DELAY}s, Timeout: ${TIMEOUT}s"
    echo ""
    
    check_health
    echo ""
    check_readiness
    
    echo ""
    log "All health checks passed!"
    exit 0
}

main "$@"
