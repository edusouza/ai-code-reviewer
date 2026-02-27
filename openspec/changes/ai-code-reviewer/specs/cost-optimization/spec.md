## ADDED Requirements

### Requirement: Cost tracking per review
The system SHALL track LLM costs for each pull request review.

#### Scenario: Cost calculation per model
- **WHEN** an LLM call completes
- **THEN** the system SHALL calculate cost based on input/output tokens
- **AND** the system SHALL use model-specific pricing
- **AND** the system SHALL accumulate cost per review

#### Scenario: Cost breakdown by agent
- **GIVEN** a review using multiple agents
- **WHEN** the review completes
- **THEN** the system SHALL provide cost breakdown by agent type
- **AND** the system SHALL provide cost breakdown by model used

#### Scenario: Total review cost
- **WHEN** a PR review completes
- **THEN** the system SHALL record total cost in Firestore
- **AND** the system SHALL expose cost in LangFuse trace
- **AND** the cost SHALL be viewable in analytics dashboard

### Requirement: Budget enforcement
The system SHALL enforce configurable cost budgets to prevent runaway spending.

#### Scenario: Per-PR cost limit
- **GIVEN** a PR cost limit of $2.00
- **WHEN** review cost approaches the limit
- **THEN** the system SHALL reduce analysis scope
- **AND** the system SHALL skip non-critical agents

#### Scenario: Daily budget alert
- **GIVEN** a daily budget of $40
- **WHEN** daily spend exceeds $40
- **THEN** the system SHALL trigger a cost alert
- **AND** the system SHALL queue new reviews for next day

#### Scenario: Hourly rate limit
- **GIVEN** an hourly cost threshold of $5
- **WHEN** hourly spend exceeds $5
- **THEN** the system SHALL send Slack notification
- **AND** the system SHALL reduce concurrency

### Requirement: Large PR handling
The system SHALL implement chunking and filtering for large pull requests.

#### Scenario: PR size detection
- **GIVEN** a PR with 1000 lines changed
- **WHEN** determining review strategy
- **THEN** the system SHALL detect this as a large PR
- **AND** the system SHALL enable aggressive filtering

#### Scenario: File prioritization
- **GIVEN** a large PR with 50 files
- **WHEN** selecting files for review
- **THEN** the system SHALL prioritize:
  - Files with >10 lines changed
  - Security-sensitive files (auth, crypto)
  - New files over modified files
  - Files matching AGENTS.md patterns

#### Scenario: Chunk processing
- **GIVEN** a file with 500 lines changed
- **WHEN** processing the file
- **THEN** the system SHALL split into chunks
- **AND** the system SHALL process chunks sequentially
- **AND** the system SHALL limit total chunks per PR

### Requirement: Model tier routing
The system SHALL route tasks to appropriate model tiers based on complexity.

#### Scenario: Simple task to fast model
- **GIVEN** an emoji evaluation task
- **WHEN** selecting model
- **THEN** the system SHALL route to fast tier (Qwen, Gemini Pro)
- **AND** the system SHALL optimize for low latency and cost

#### Scenario: Complex task to powerful model
- **GIVEN** an architectural review task
- **WHEN** selecting model
- **THEN** the system SHALL route to powerful tier (GPT-4, Claude Opus)
- **AND** the system SHALL optimize for accuracy

#### Scenario: Balanced task to mid-tier model
- **GIVEN** a pattern matching task
- **WHEN** selecting model
- **THEN** the system SHALL route to balanced tier (Kimi k2, Claude Sonnet)
- **AND** the system SHALL balance cost and accuracy

### Requirement: Token quota management
The system SHALL manage token quotas to control costs.

#### Scenario: Token budget per review
- **GIVEN** a token budget of 50k tokens per PR
- **WHEN** approaching the limit
- **THEN** the system SHALL reduce context window
- **AND** the system SHALL limit number of agents

#### Scenario: Rate limiting
- **GIVEN** a token rate limit of 100k tokens/minute
- **WHEN** rate limit is reached
- **THEN** the system SHALL queue requests
- **AND** the system SHALL retry after backoff

### Requirement: Cost optimization reporting
The system SHALL provide cost optimization reports and recommendations.

#### Scenario: Cost report generation
- **WHEN** generating weekly report
- **THEN** the system SHALL show:
  - Total spend by model
  - Average cost per PR
  - Most expensive PRs
  - Cost trends over time

#### Scenario: Optimization recommendations
- **GIVEN** cost analytics data
- **WHEN** analyzing for optimizations
- **THEN** the system SHALL suggest:
  - Model substitutions for cost savings
  - Configuration adjustments
  - Usage pattern improvements
