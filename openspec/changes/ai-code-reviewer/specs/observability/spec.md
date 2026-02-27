## ADDED Requirements

### Requirement: LangFuse tracing
The system SHALL integrate with LangFuse to trace all LLM calls, workflow execution, and agent activities.

#### Scenario: LLM call tracing
- **WHEN** any agent makes an LLM API call
- **THEN** the system SHALL log the trace to LangFuse
- **AND** the trace SHALL include prompt, completion, tokens used, cost, latency, and model name

#### Scenario: Workflow trace creation
- **WHEN** a review workflow starts
- **THEN** the system SHALL create a LangFuse trace with PR metadata
- **AND** the trace SHALL span all workflow nodes until completion

#### Scenario: Agent span creation
- **WHEN** an agent executes
- **THEN** the system SHALL create a child span under the workflow trace
- **AND** the span SHALL include agent type, duration, suggestions generated

### Requirement: Metrics collection
The system SHALL collect custom metrics for cost tracking, accuracy, and performance monitoring.

#### Scenario: Cost tracking per review
- **WHEN** a review completes
- **THEN** the system SHALL calculate total cost from all LLM calls
- **AND** the system SHALL record cost by model and agent type
- **AND** the system SHALL send cost metrics to Cloud Monitoring

#### Scenario: Latency metrics
- **WHEN** each workflow node completes
- **THEN** the system SHALL record execution duration
- **AND** the system SHALL track p50, p95, p99 latencies

#### Scenario: Token usage metrics
- **WHEN** each LLM call completes
- **THEN** the system SHALL record input and output token counts
- **AND** the system SHALL aggregate tokens by model and agent

### Requirement: BigQuery analytics pipeline
The system SHALL export LangFuse data to BigQuery for long-term analytics and custom reporting.

#### Scenario: Daily ETL execution
- **WHEN** the daily Cloud Scheduler job triggers
- **THEN** the system SHALL extract yesterday's traces from LangFuse
- **AND** the system SHALL transform and load data into BigQuery
- **AND** the system SHALL maintain 1-year retention in BigQuery

#### Scenario: Analytics availability
- **GIVEN** data in BigQuery
- **WHEN** querying for agent performance metrics
- **THEN** the system SHALL return aggregated accuracy, cost, and latency data
- **AND** the data SHALL be available for Looker Studio dashboards

### Requirement: Alerting policies
The system SHALL implement Cloud Monitoring alerts for cost, accuracy, and operational issues.

#### Scenario: High cost alert
- **WHEN** hourly cost exceeds $5
- **THEN** Cloud Monitoring SHALL trigger an alert
- **AND** the alert SHALL notify Slack #alerts channel

#### Scenario: Accuracy drop alert
- **WHEN** 24-hour average accuracy drops below 80% for any agent
- **THEN** Cloud Monitoring SHALL trigger a warning alert
- **AND** the alert SHALL notify the engineering team

#### Scenario: Review failure alert
- **WHEN** more than 3 reviews fail in 10 minutes
- **THEN** Cloud Monitoring SHALL trigger a critical alert
- **AND** the alert SHALL page on-call via PagerDuty

#### Scenario: Queue backup alert
- **WHEN** Pub/Sub queue depth exceeds 50 messages for 5 minutes
- **THEN** Cloud Monitoring SHALL trigger a warning alert
- **AND** the alert SHALL notify Slack #alerts channel

### Requirement: Feedback score tracking
The system SHALL track developer feedback scores in LangFuse for continuous improvement.

#### Scenario: Developer reaction scoring
- **WHEN** a developer reacts to a comment with 👍, 👎, or 🤔
- **THEN** the system SHALL classify the emoji sentiment
- **AND** the system SHALL submit a score to LangFuse attached to the original trace

#### Scenario: LLM judge correlation
- **GIVEN** LangFuse scores from developer feedback
- **WHEN** analyzing agent accuracy
- **THEN** the system SHALL correlate judge validation scores with developer acceptance
- **AND** the system SHALL identify discrepancies for model tuning
