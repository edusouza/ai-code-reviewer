# Troubleshooting Guide

Common issues and solutions for the AI Code Reviewer.

## Table of Contents

- [Installation Issues](#installation-issues)
- [Webhook Issues](#webhook-issues)
- [Authentication Issues](#authentication-issues)
- [Review Not Appearing](#review-not-appearing)
- [Performance Issues](#performance-issues)
- [Cost Issues](#cost-issues)
- [Log Locations](#log-locations)

---

## Installation Issues

### Docker Build Fails

**Symptom:** `docker build` fails with package installation errors

**Solutions:**
```bash
# Clean build with no cache
docker build --no-cache -t ai-code-reviewer .

# Check Python version
docker --version  # Should be 20.10+

# Verify requirements.txt exists
ls -la requirements.txt
```

### Import Errors

**Symptom:** `ModuleNotFoundError: No module named 'src'`

**Solution:**
```bash
# Ensure PYTHONPATH is set
export PYTHONPATH=/app/src:$PYTHONPATH

# Or run from src directory
cd src && python main.py
```

---

## Webhook Issues

### Webhook Not Receiving Events

**Symptom:** PRs created but no review triggered

**Check:**
1. Verify webhook URL is correct
   ```bash
   curl -X POST https://YOUR_URL/webhooks/github \
     -H "Content-Type: application/json" \
     -d '{"test": true}'
   ```

2. Check webhook secret
   ```bash
   # Verify secret matches in both .env and provider settings
   echo $GITHUB_WEBHOOK_SECRET
   ```

3. Review webhook delivery in provider:
   - **GitHub**: Settings → Webhooks → Recent Deliveries
   - **GitLab**: Settings → Webhooks → Test
   - **Bitbucket**: Repository Settings → Webhooks → View requests

### 401 Unauthorized Errors

**Symptom:** Webhook requests return 401

**Solutions:**
- Regenerate webhook secret:
  ```bash
  openssl rand -base64 32
  ```
- Update secret in both `.env` and provider webhook settings
- Redeploy service with new secret

### 404 Not Found

**Symptom:** Webhook requests return 404

**Solutions:**
- Verify URL path: `/webhooks/github`, `/webhooks/gitlab`, or `/webhooks/bitbucket`
- Check service is running: `curl /health`
- Verify route is registered in FastAPI

---

## Authentication Issues

### GitHub App Authentication Failed

**Symptom:** `401 Bad credentials` or `JWT token expired`

**Solutions:**
1. Regenerate private key:
   - GitHub App Settings → General → Private keys → Generate
   
2. Verify private key format:
   ```bash
   # Should start with -----BEGIN RSA PRIVATE KEY-----
   head -1 private-key.pem
   ```

3. Check App ID is correct (numbers only, no quotes)

4. Ensure private key has proper newlines:
   ```bash
   # In .env, use actual newlines or \n
   GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\nMII..."
   ```

### GitLab Token Issues

**Symptom:** `401 Unauthorized` or `403 Forbidden`

**Solutions:**
1. Create new personal access token:
   - GitLab → User Settings → Access Tokens
   - Scopes: `api`, `read_repository`, `write_repository`

2. Verify token:
   ```bash
   curl -H "Authorization: Bearer $GITLAB_TOKEN" \
     https://gitlab.com/api/v4/user
   ```

3. Check token hasn't expired

### Bitbucket Authentication Failed

**Symptom:** `401 Authentication failed`

**Solutions:**
1. Create new app password:
   - Bitbucket Settings → App passwords
   - Permissions: Repositories (Read), Pull requests (Write)

2. Verify username matches exactly

3. Test with curl:
   ```bash
   curl -u "username:app_password" \
     https://api.bitbucket.org/2.0/user
   ```

---

## Review Not Appearing

### No Comments on PR

**Checklist:**
1. **Webhook delivered?**
   - Check provider's webhook delivery log
   - Look for 200 OK responses

2. **Worker running?**
   ```bash
   # Check Pub/Sub subscription
   gcloud pubsub subscriptions pull code-reviews-sub --auto-ack
   ```

3. **Logs show processing?**
   ```bash
   gcloud logging read "resource.type=cloud_run_revision" --limit=20
   ```

4. **PR has changed files?**
   - Empty PRs won't trigger reviews
   - Check ignored file patterns

### Reviews Are Empty

**Symptom:** "No suggestions found" message

**Causes:**
- All changes in ignored files (check AGENTS.md ignore patterns)
- PR only has deletions
- Changes are too small (less than min threshold)
- LLM returned empty suggestions

**Solutions:**
```bash
# Check review job logs
gcloud logging read "jsonPayload.event_id=\"EVENT_ID\"" --format="table(textPayload)"
```

### Duplicate Suggestions

**Symptom:** Same suggestion appears multiple times

**Solutions:**
- Enable deduplication in AGENTS.md:
  ```markdown
  ## Review Preferences
  - Enable deduplication: true
  ```

- Increase similarity threshold:
  ```python
  # In src/suggestions/deduplicator.py
  SIMILARITY_THRESHOLD = 0.85  # Increase from 0.80
  ```

---

## Performance Issues

### Slow Review Generation

**Symptoms:** Reviews take > 5 minutes

**Solutions:**
1. **Check LLM latency:**
   ```bash
   # Monitor Vertex AI quotas
   gcloud ai quotas list --region=us-central1
   ```

2. **Reduce file count:**
   - Add ignore patterns to AGENTS.md
   - Split large PRs into smaller ones

3. **Use smaller model:**
   ```markdown
   ## LLM Preferences
   - Preferred model: gemini-pro-flash  # Faster, cheaper
   ```

4. **Increase Cloud Run concurrency:**
   ```bash
   gcloud run services update ai-code-reviewer \
     --concurrency=100
   ```

### Timeouts

**Symptom:** `504 Gateway Timeout`

**Solutions:**
- Increase Cloud Run timeout:
  ```bash
  gcloud run services update ai-code-reviewer \
    --timeout=600
  ```

- Enable Pub/Sub retry with backoff:
  ```bash
  gcloud pubsub subscriptions update code-reviews-sub \
    --min-retry-delay=10s \
    --max-retry-delay=600s
  ```

### High Memory Usage

**Symptom:** Container restarts, OOM errors

**Solutions:**
1. Increase memory:
   ```bash
   gcloud run services update ai-code-reviewer --memory=2Gi
   ```

2. Reduce batch size in LLM client

3. Process files in smaller chunks

---

## Cost Issues

### Unexpected High Costs

**Symptoms:** Vertex AI bills higher than expected

**Investigation:**
```bash
# Check cost breakdown
gcloud billing accounts list
gcloud billing projects describe PROJECT_ID

# Review token usage
gcloud logging read "jsonPayload.tokens_used > 1000" --limit=50
```

**Solutions:**
1. **Enable cost tracking:**
   ```bash
   ENABLE_COST_TRACKING=true
   MAX_TOKENS_PER_REVIEW=5000
   ```

2. **Set budget alerts:**
   - GCP Console → Billing → Budgets & alerts
   - Set threshold at 80%, 100%

3. **Use cost optimizer:**
   ```python
   # Routes simple PRs to cheaper models
   ENABLE_COST_OPTIMIZATION=true
   ```

### Token Overages

**Symptoms:** Frequent "Token limit exceeded" warnings

**Solutions:**
- Reduce `MAX_TOKENS_PER_REVIEW` in settings
- Add more ignore patterns
- Split large PRs into smaller ones
- Use more aggressive file filtering

---

## Log Locations

### Cloud Run Logs

```bash
# View recent logs
gcloud logging read "resource.type=cloud_run_revision" --limit=50

# Follow logs in real-time
gcloud logging tail "resource.type=cloud_run_revision"

# Filter by severity
gcloud logging read "resource.type=cloud_run_revision AND severity>=ERROR"

# Filter by service
gcloud logging read "resource.labels.service_name=ai-code-reviewer"
```

### Pub/Sub Logs

```bash
# View message processing logs
gcloud logging read "protoPayload.serviceName=pubsub.googleapis.com"

# Check subscription metrics
gcloud pubsub subscriptions describe code-reviews-sub
```

### Firestore Logs

```bash
# Check database operations
gcloud logging read "protoPayload.serviceName=firestore.googleapis.com"
```

### Local Development Logs

```bash
# Docker Compose logs
docker-compose logs -f app

# Or with timestamps
docker-compose logs -f --timestamps app
```

---

## Debugging Tips

### Enable Debug Mode

```bash
# In .env or environment
DEBUG=true
```

This enables:
- Detailed logging
- Stack traces in error responses
- Additional health check info

### Test Webhooks Locally

```bash
# Use ngrok for local testing
ngrok http 8080

# Then configure webhook URL to ngrok URL
# https://abc123.ngrok.io/webhooks/github
```

### Trace Request Flow

1. Find event ID in webhook payload
2. Search logs:
   ```bash
   gcloud logging read "jsonPayload.event_id=\"pr-123\"" --format="table(timestamp,jsonPayload.message)"
   ```

3. Follow through:
   - Webhook received
   - Event published to Pub/Sub
   - Worker picked up job
   - LLM requests made
   - Comments posted

### Check Service Health

```bash
# Full health check
curl https://YOUR_URL/health

# Check specific components
curl https://YOUR_URL/health/firestore
curl https://YOUR_URL/health/pubsub
```

---

## Getting Help

### Before Asking for Help

1. Check this troubleshooting guide
2. Search [existing issues](https://github.com/yourusername/ai-code-reviewer/issues)
3. Review [discussions](https://github.com/yourusername/ai-code-reviewer/discussions)
4. Gather relevant logs
5. Note your configuration (redact secrets)

### Where to Get Help

- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/yourusername/ai-code-reviewer/issues)
- 💬 **Questions**: [GitHub Discussions](https://github.com/yourusername/ai-code-reviewer/discussions)
- 📧 **Security Issues**: security@example.com
- 📖 **Documentation**: [Full docs](../README.md)

### Information to Include

When reporting issues:
- Error messages (full stack trace)
- Logs (sanitized)
- Configuration (without secrets)
- Steps to reproduce
- Environment details (GCP region, versions)

---

## Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `401 Bad credentials` | Invalid auth token | Check GitHub/GitLab/Bitbucket credentials |
| `404 Not Found` | Wrong webhook URL | Verify URL path |
| `429 Too Many Requests` | Rate limited | Check quotas, add retry logic |
| `504 Gateway Timeout` | Request too slow | Increase timeout, optimize processing |
| `Permission denied` | IAM issues | Check service account permissions |
| `Database not found` | Firestore not created | Run `gcloud firestore databases create` |
