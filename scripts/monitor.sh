#!/bin/bash

set -euo pipefail

ENV="${1:-}"
MONITOR_DURATION="${2:-300}"
LOG_FILE="${3:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

ERROR_THRESHOLD="${ERROR_THRESHOLD:-5.0}"
LATENCY_THRESHOLD="${LATENCY_THRESHOLD:-1000}"
P90_LATENCY_THRESHOLD="${P90_LATENCY_THRESHOLD:-2000}"

usage() {
    echo "Usage: $0 <environment> [duration_seconds] [log_file]"
    echo ""
    echo "Example: $0 prod 300"
    exit 1
}

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg"
    if [[ -n "$LOG_FILE" ]]; then
        echo "$msg" >> "$LOG_FILE"
    fi
}

error() {
    log "ERROR: $*" >&2
    exit 1
}

if [[ -z "$ENV" ]]; then
    usage
fi

load_config() {
    local config_file="${PROJECT_ROOT}/config/${ENV}.env"
    if [[ -f "$config_file" ]]; then
        set -a
        source "$config_file"
        set +a
    fi
}

get_metrics() {
    local metric="$1"
    local minutes="${2:-5}"
    
    if command -v gcloud >/dev/null 2>&1 && [[ -n "${GCLOUD_PROJECT:-}" ]]; then
        gcloud monitoring metrics list --filter="metric.type='${metric}'" --limit=1 2>/dev/null | \
            grep -q "metric.type" && {
            gcloud monitoring metrics list --filter="metric.type='${metric}'" --limit=1 2>/dev/null | \
                head -1
            return 0
        }
    fi
    
    echo "N/A"
}

check_error_rate() {
    log "Checking error rate..."
    
    local error_rate="0.0"
    
    if [[ -n "${SERVICE_NAME:-}" ]]; then
        error_rate=$(gcloud monitoring metrics list \
            --filter="metric.labels.response_code_class!='2xx'" \
            --format="value(points.value.doubleValue)" 2>/dev/null | \
            head -1 || echo "0.0")
    fi
    
    if [[ "$error_rate" == "N/A" ]] || [[ "$error_rate" == "0.0" ]]; then
        log "  Error rate: 0% (OK)"
        return 0
    fi
    
    local error_percent=$(echo "$error_rate * 100" | bc -l 2>/dev/null || echo "0")
    
    if (( $(echo "$error_percent > $ERROR_THRESHOLD" | bc -l 2>/dev/null || echo "0") )); then
        log "  ERROR: Error rate ${error_percent}% exceeds threshold ${ERROR_THRESHOLD}%"
        return 1
    fi
    
    log "  Error rate: ${error_percent}% (OK)"
    return 0
}

check_latency() {
    log "Checking latency..."
    
    local p50_latency="0"
    local p90_latency="0"
    local p99_latency="0"
    
    if [[ -n "${SERVICE_NAME:-}" ]]; then
        local metrics=$(gcloud monitoring metrics list \
            --filter="metric.type='run.googleapis.com/request_latencies'" \
            --format="table[no-heading](points.value.distributionValue)" 2>/dev/null | \
            head -3 || echo "")
        
        if [[ -n "$metrics" ]]; then
            p50_latency=$(echo "$metrics" | sed -n '1p' | grep -o '[0-9]*' | head -1 || echo "0")
            p90_latency=$(echo "$metrics" | sed -n '2p' | grep -o '[0-9]*' | head -1 || echo "0")
            p99_latency=$(echo "$metrics" | sed -n '3p' | grep -o '[0-9]*' | head -1 || echo "0")
        fi
    fi
    
    local latency_ok=true
    
    if (( $(echo "$p50_latency > $LATENCY_THRESHOLD" | bc -l 2>/dev/null || echo "0") )); then
        log "  WARNING: P50 latency ${p50_latency}ms exceeds threshold ${LATENCY_THRESHOLD}ms"
        latency_ok=false
    else
        log "  P50 latency: ${p50_latency}ms (OK)"
    fi
    
    if (( $(echo "$p90_latency > $P90_LATENCY_THRESHOLD" | bc -l 2>/dev/null || echo "0") )); then
        log "  WARNING: P90 latency ${p90_latency}ms exceeds threshold ${P90_LATENCY_THRESHOLD}ms"
        latency_ok=false
    else
        log "  P90 latency: ${p90_latency}ms (OK)"
    fi
    
    log "  P99 latency: ${p99_latency}ms"
    
    if [[ "$latency_ok" == "true" ]]; then
        return 0
    else
        return 1
    fi
}

check_custom_metrics() {
    log "Checking custom application metrics..."
    
    local custom_ok=true
    
    if [[ -f "${PROJECT_ROOT}/scripts/custom_checks.sh" ]]; then
        bash "${PROJECT_ROOT}/scripts/custom_checks.sh" "$ENV" || custom_ok=false
    fi
    
    if [[ "$custom_ok" == "true" ]]; then
        log "  Custom metrics: OK"
        return 0
    else
        log "  Custom metrics: FAILED"
        return 1
    fi
}

monitor_loop() {
    local end_time=$(($(date +%s) + MONITOR_DURATION))
    local check_interval=30
    local consecutive_failures=0
    local max_consecutive_failures=3
    
    log "Starting monitoring for ${MONITOR_DURATION} seconds..."
    log "Error threshold: ${ERROR_THRESHOLD}%"
    log "Latency threshold: ${LATENCY_THRESHOLD}ms (P50)"
    log "P90 Latency threshold: ${P90_LATENCY_THRESHOLD}ms"
    echo ""
    
    while [[ $(date +%s) -lt $end_time ]]; do
        local cycle_start=$(date +%s)
        local all_ok=true
        
        log "--- Check at $(date '+%H:%M:%S') ---"
        
        check_error_rate || all_ok=false
        check_latency || all_ok=false
        check_custom_metrics || all_ok=false
        
        if [[ "$all_ok" == "true" ]]; then
            consecutive_failures=0
            log "Status: ALL OK"
        else
            consecutive_failures=$((consecutive_failures + 1))
            log "Status: ISSUES DETECTED (failure $consecutive_failures/$max_consecutive_failures)"
            
            if [[ $consecutive_failures -ge $max_consecutive_failures ]]; then
                log "ALERT: Too many consecutive failures, triggering rollback recommendation"
                return 1
            fi
        fi
        
        echo ""
        
        local elapsed=$(($(date +%s) - cycle_start))
        local sleep_time=$((check_interval - elapsed))
        if [[ $sleep_time -gt 0 ]]; then
            sleep $sleep_time
        fi
    done
    
    log "Monitoring complete"
    return 0
}

auto_rollback() {
    log "Auto-rollback requested due to monitoring failures"
    
    if [[ "${AUTO_ROLLBACK:-false}" == "true" ]]; then
        log "Executing automatic rollback..."
        bash "${SCRIPT_DIR}/deploy.sh" "$ENV" rollback
    else
        log "Auto-rollback is disabled. Manual intervention required."
        return 1
    fi
}

main() {
    load_config
    
    if ! monitor_loop; then
        auto_rollback
        exit 1
    fi
    
    exit 0
}

main "$@"
