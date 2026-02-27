## Context

This is a new AI-powered code review system targeting enterprise developers. The system must integrate with multiple Git providers (GitHub, GitLab, Bitbucket), process pull requests through an AI pipeline, and provide observable, high-quality feedback. Based on exploration, we've established key architectural decisions around LangGraph for orchestration, self-hosted LangFuse for observability, and blue-green deployment for reliability.

## Goals / Non-Goals

**Goals:**
- Provide automated, high-quality code reviews across GitHub/GitLab/Bitbucket
- Reduce human review time while maintaining or improving code quality
- Learn repository-specific patterns from AGENTS.md and developer feedback
- Ensure zero-downtime deployments with instant rollback capability
- Track all LLM costs and performance metrics for optimization
- Support private repositories securely with encryption and audit logging

**Non-Goals:**
- Code auto-fix generation (future phase)
- Real-time collaborative editing
- IDE integrations or plugins
- Multi-tenancy support (single-tenant per deployment)
- Automated merge/blocking (future phase)

## Decisions

### Orchestration: LangGraph over ADK

**Decision:** Use LangGraph for the review workflow orchestration.

**Rationale:**
- LangGraph provides explicit state management with checkpointing, critical for long-running PR reviews that may span multiple minutes
- Complex conditional logic needed for multi-agent coordination (security → style → logic → pattern) requires state machine visibility
- LangGraph has larger community and production track record than GCP ADK
- Cloud Functions auto-scaling fits LangGraph's event-driven model

**Alternative considered:** GCP ADK - rejected due to vendor lock-in and smaller ecosystem despite native GCP integration.

### Observability: Self-Hosted LangFuse over Cloud Monitoring

**Decision:** Deploy LangFuse self-hosted on Cloud Run with Cloud SQL.

**Rationale:**
- Purpose-built for LLM observability with native tracing, prompt logging, and cost tracking
- Provides developer feedback correlation via scores attached to traces
- Self-hosted avoids data residency concerns with private repository code
- Integrates with BigQuery for custom analytics and retention policies

**Alternative considered:** Cloud Monitoring only - rejected due to lack of LLM-specific metrics (prompt/completion tracking, token costs).

### State Management: Firestore with Custom Checkpointer

**Decision:** Use Firestore for LangGraph checkpoint persistence.

**Rationale:**
- GCP-native, serverless, no additional infrastructure to manage
- Supports complex state serialization needed for LangGraph
- Single source of truth for both checkpoint state and application data
- Automatic backup and point-in-time recovery

**Alternative considered:** Redis - rejected due to added operational complexity and no significant performance benefit for review workloads.

### Database: Cloud SQL Postgres for LangFuse

**Decision:** Use Cloud SQL Postgres (db-f1-micro initially) for LangFuse.

**Rationale:**
- LangFuse requires relational database for its data model
- Managed service with automated backups and maintenance
- Start small, scale up based on trace volume

**Trade-off:** Slightly higher cost than Cloud Spanner or Firestore, but required by LangFuse.

### Message Queue: Pub/Sub over RabbitMQ/Redis

**Decision:** Use Cloud Pub/Sub for event streaming.

**Rationale:**
- Fully managed, highly available, no ops burden
- Integrates natively with Cloud Run (eventarc triggers)
- Supports dead letter queues for failed reviews
- Exactly-once delivery guarantees

### Deployment: Blue-Green with Cloud Run Traffic Splitting

**Decision:** Implement blue-green deployment using native Cloud Run traffic management.

**Rationale:**
- Instant rollback capability via traffic percentage changes
- Canary testing at 5%, 25%, 50% before full promotion
- No additional infrastructure (load balancers, ingress) needed
- Built-in health check integration

**Implementation:** Two Cloud Run services (blue/green) with primary service handling traffic routing via Terraform-managed traffic percentages.

### Model Strategy: Multi-Tier with Vertex AI Model Garden

**Decision:** Route to different models based on task complexity via Vertex AI.

**Rationale:**
- Cost optimization: Use cheaper models (Qwen, Gemini Pro) for simple tasks, expensive models (GPT-4, Claude Opus) for complex reasoning
- Single API endpoint (Vertex AI) for all models simplifies integration
- Access to model garden including open models (Qwen) and commercial (OpenAI, Anthropic)

**Routing Logic:**
- Simple tasks (emoji evaluation, formatting): Qwen/Gemini Pro
- Medium complexity (pattern matching, style checks): Kimi k2, Claude Sonnet
- Complex reasoning (architecture review, security analysis): GPT-4, Claude Opus

### Pattern Learning: Per-Repository Isolation

**Decision:** Store learned patterns per repository, no cross-repository sharing.

**Rationale:**
- Security: Prevents code patterns from private repos leaking to other contexts
- Predictability: Each repo learns its own conventions without interference
- Simplicity: No need for complex multi-tenant isolation in vector store

**Implementation:** Namespace vector store collections by `repo_owner/repo_name`.

### Configuration: AGENTS.md over Web UI

**Decision:** Use AGENTS.md file in repository root for configuration.

**Rationale:**
- Version-controlled alongside code (review rules evolve with codebase)
- No additional UI to build and maintain
- Familiar pattern (like .cursorrules, CLAUDE.md)
- Easy to template and share across repos

**Format:** Markdown with structured sections (Style Guidelines, Patterns, Security Priorities, etc.) parsed by LLM into structured config.

## Risks / Trade-offs

**[Risk] LLM costs could spiral with large PRs**
→ Mitigation: Implement aggressive chunking for PRs >500 lines, configurable token budgets per PR, cost alerts at $5/hour and $40/day

**[Risk] AI hallucinations could provide bad suggestions**
→ Mitigation: LLM-as-judge validation layer with low temperature (0.1), severity-based filtering, developer feedback loop with emoji evaluation

**[Risk] Vendor lock-in to GCP**
→ Mitigation: Abstract cloud-specific services behind interfaces (Terraform modules, Python adapters), keep core logic cloud-agnostic

**[Risk] Cold start latency on Cloud Run**
→ Mitigation: Set minInstances=1 for production, use startup probes, implement queue-based processing (not synchronous)

**[Risk] Firestore costs at scale**
→ Mitigation: 1-year retention policy, periodic archival to Coldline, indexing strategy optimized for query patterns

**[Trade-off] Per-repository learning vs. shared knowledge**
→ Chose isolation for security/simplicity. Downside: Each repo starts from scratch. Mitigation: Provide default AGENTS.md templates with common patterns.

**[Trade-off] Self-hosted LangFuse vs. managed service**
→ Chose self-hosted for data control. Downside: Operational overhead (~$12/month infra). Mitigation: Terraform automation, Cloud SQL automated backups.

## Migration Plan

Since this is a new system, deployment is straightforward:

1. **Infrastructure Provisioning**
   - Run `terraform apply` to create all GCP resources
   - Verify Cloud Run services, Pub/Sub topics, Firestore DB, Cloud SQL instance

2. **LangFuse Setup**
   - Access LangFuse dashboard at deployed URL
   - Create initial organization and project
   - Generate API keys, store in Secret Manager

3. **Git Provider Configuration**
   - Create GitHub App (or GitLab/Bitbucket equivalents)
   - Configure webhooks pointing to deployed service
   - Store credentials in Secret Manager

4. **Testing**
   - Create test repository with AGENTS.md
   - Open test PR, verify webhook received
   - Check LangFuse traces for successful review flow
   - Verify BigQuery data pipeline

5. **Production Cutover**
   - Deploy to prod environment
   - Start with blue-green: deploy green at 0%, health check
   - Canary at 5% for 24 hours
   - Gradual promotion to 100%

## Open Questions

1. **LangFuse hosting**: Self-hosted on Cloud Run vs. LangFuse Cloud managed service - confirm decision based on data residency requirements

2. **Queue depth monitoring**: Need to define specific alert thresholds for queue backup (currently: >50 messages for 5 minutes)

3. **BigQuery retention**: Confirm 1-year retention aligns with compliance requirements

4. **AGENTS.md parsing**: Validate approach - use LLM to parse markdown vs. structured YAML frontmatter

5. **Model fallback strategy**: What happens when Vertex AI rate limits or a model is unavailable? Define fallback chain.

6. **Feedback retention**: How long to keep developer feedback data? Currently aligned with 1-year trace retention.
