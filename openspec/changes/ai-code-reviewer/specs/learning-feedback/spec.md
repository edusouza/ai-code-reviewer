## ADDED Requirements

### Requirement: Developer feedback collection
The system SHALL collect developer feedback on AI suggestions via emoji reactions and comment resolutions.

#### Scenario: Emoji reaction captured
- **WHEN** a developer reacts 👍 to a review comment
- **THEN** the system SHALL record the reaction
- **AND** the system SHALL classify the sentiment as positive
- **AND** the system SHALL link the feedback to the original trace

#### Scenario: Comment resolution
- **WHEN** a developer marks a suggestion as resolved/accepted
- **THEN** the system SHALL record the acceptance
- **AND** the system SHALL treat this as positive feedback

#### Scenario: Comment dismissal
- **WHEN** a developer dismisses a suggestion without resolution
- **THEN** the system SHALL record the dismissal
- **AND** the system SHALL treat this as negative feedback

### Requirement: Emoji sentiment classification
The system SHALL use LLM to classify emoji reactions into sentiment categories.

#### Scenario: Positive emoji classification
- **GIVEN** emojis: 👍, ✅, 🎉, 💯, 🚀, 👏
- **WHEN** the emoji evaluator processes the reaction
- **THEN** the system SHALL classify as POSITIVE
- **AND** the system SHALL submit score 1.0 to LangFuse

#### Scenario: Negative emoji classification
- **GIVEN** emojis: 👎, ❌, 😠, 💩, 🗑️
- **WHEN** the emoji evaluator processes the reaction
- **THEN** the system SHALL classify as NEGATIVE
- **AND** the system SHALL submit score 0.0 to LangFuse

#### Scenario: Neutral emoji classification
- **GIVEN** emojis: 🤔, ❓, 🤷, ⏳
- **WHEN** the emoji evaluator processes the reaction
- **THEN** the system SHALL classify as NEUTRAL
- **AND** the system SHALL submit score 0.5 to LangFuse

### Requirement: Per-repository pattern learning
The system SHALL learn repository-specific patterns using Vertex AI Vector Search with isolation per repository.

#### Scenario: Pattern extraction
- **WHEN** high-quality code is identified (high feedback scores)
- **THEN** the system SHALL extract code patterns using embeddings
- **AND** the system SHALL store patterns in vector store
- **AND** the patterns SHALL be namespaced by repository

#### Scenario: Pattern retrieval for review
- **GIVEN** a PR being reviewed
- **WHEN** the pattern_agent runs
- **THEN** the system SHALL retrieve similar patterns from the repository
- **AND** the system SHALL suggest consistency with learned patterns

#### Scenario: Repository isolation
- **GIVEN** patterns learned from repo-a
- **WHEN** reviewing code in repo-b
- **THEN** the system SHALL NOT use repo-a patterns
- **AND** repo-b SHALL only access its own learned patterns

### Requirement: Feedback data retention
The system SHALL retain feedback data with a 1-year retention policy.

#### Scenario: Data storage
- **WHEN** feedback is collected
- **THEN** the system SHALL store in Firestore with timestamp
- **AND** the system SHALL archive to BigQuery for analytics

#### Scenario: Data expiration
- **GIVEN** feedback data older than 1 year
- **WHEN** the retention job runs
- **THEN** the system SHALL delete expired feedback data
- **AND** the system SHALL maintain aggregated metrics

### Requirement: Model performance tracking
The system SHALL track model accuracy per agent type using feedback scores.

#### Scenario: Accuracy calculation
- **GIVEN** 100 suggestions from security_agent
- **GIVEN** 90 positive feedback scores, 10 negative
- **WHEN** calculating accuracy
- **THEN** the system SHALL report 90% accuracy for security_agent

#### Scenario: Accuracy reporting
- **WHEN** querying agent performance dashboard
- **THEN** the system SHALL display accuracy by agent type
- **AND** the system SHALL show trends over time
- **AND** the system SHALL identify declining accuracy
