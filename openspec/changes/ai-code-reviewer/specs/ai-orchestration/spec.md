## ADDED Requirements

### Requirement: LangGraph state machine
The system SHALL use LangGraph to orchestrate the review workflow with explicit state management and checkpoint persistence.

#### Scenario: Review workflow execution
- **WHEN** a PR event is received from the queue
- **THEN** the system SHALL instantiate a LangGraph workflow
- **AND** the workflow SHALL execute nodes in sequence: ingest → analyze → judge → publish
- **AND** the system SHALL persist state after each node completion

#### Scenario: Workflow recovery after failure
- **WHEN** a review workflow fails mid-execution (e.g., during analysis)
- **THEN** the system SHALL recover from the last checkpoint
- **AND** the system SHALL resume execution from the failed node
- **AND** the system SHALL not re-process already completed nodes

### Requirement: Multi-agent parallel execution
The system SHALL support parallel execution of independent analysis agents.

#### Scenario: Parallel agent analysis
- **WHEN** the workflow reaches the analysis phase
- **THEN** the system SHALL execute style_agent, security_agent, logic_agent, and pattern_agent concurrently
- **AND** the system SHALL wait for all agents to complete before aggregation
- **AND** the system SHALL aggregate results from all agents into a unified suggestion list

### Requirement: State checkpoint persistence
The system SHALL persist LangGraph checkpoints to Firestore for durability and recovery.

#### Scenario: Checkpoint creation
- **WHEN** a workflow node completes successfully
- **THEN** the system SHALL save the current state to Firestore
- **AND** the checkpoint SHALL include node outputs, metadata, and timestamp

#### Scenario: Checkpoint retrieval
- **WHEN** resuming a workflow after interruption
- **THEN** the system SHALL retrieve the latest checkpoint from Firestore
- **AND** the system SHALL restore the workflow state exactly as it was

### Requirement: Error handling and retry
The system SHALL implement error handling with configurable retry logic at the workflow level.

#### Scenario: Transient error retry
- **WHEN** an LLM API call fails with a transient error (rate limit, timeout)
- **THEN** the system SHALL retry up to 3 times with exponential backoff
- **AND** the system SHALL proceed to the next node if retry succeeds

#### Scenario: Permanent error handling
- **WHEN** a workflow node fails with a permanent error (invalid input, auth failure)
- **THEN** the system SHALL not retry
- **AND** the system SHALL log the error
- **AND** the system SHALL publish a partial review if applicable
- **AND** the system SHALL move the message to the dead letter queue
