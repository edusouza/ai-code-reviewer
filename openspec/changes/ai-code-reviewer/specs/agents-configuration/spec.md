## ADDED Requirements

### Requirement: AGENTS.md parsing
The system SHALL parse AGENTS.md files from repository roots to customize review behavior.

#### Scenario: AGENTS.md exists
- **WHEN** processing a PR from a repository containing AGENTS.md
- **THEN** the system SHALL fetch the AGENTS.md file
- **AND** the system SHALL parse the file into structured configuration
- **AND** the system SHALL apply custom rules during analysis

#### Scenario: AGENTS.md missing
- **WHEN** processing a PR from a repository without AGENTS.md
- **THEN** the system SHALL use default review rules
- **AND** the system SHALL perform broader, more general analysis
- **AND** the system SHALL not fail or block processing

### Requirement: Configuration structure
The system SHALL support AGENTS.md sections for style guidelines, patterns, security priorities, and custom rules.

#### Scenario: Style guidelines configuration
- **GIVEN** an AGENTS.md with "Style Guidelines" section
- **WHEN** the style_agent runs
- **THEN** the agent SHALL enforce the specified style rules
- **AND** the agent SHALL use the specified max line length, import order, etc.

#### Scenario: Pattern enforcement configuration
- **GIVEN** an AGENTS.md with "Patterns to Enforce" section
- **WHEN** the pattern_agent runs
- **THEN** the agent SHALL verify code follows specified patterns
- **AND** the agent SHALL flag deviations as violations

#### Scenario: Pattern avoidance configuration
- **GIVEN** an AGENTS.md with "Patterns to Avoid" section
- **WHEN** any agent runs
- **THEN** the agents SHALL flag occurrences of forbidden patterns
- **AND** the agents SHALL suggest alternatives

#### Scenario: Security priority configuration
- **GIVEN** an AGENTS.md with "Security Priorities" section
- **WHEN** the security_agent runs
- **THEN** the agent SHALL prioritize specified security checks
- **AND** the agent SHALL assign severities according to configuration

### Requirement: Ignore patterns
The system SHALL respect file ignore patterns specified in AGENTS.md.

#### Scenario: Ignored files excluded
- **GIVEN** an AGENTS.md with "Ignore Files" section listing `**/migrations/**`
- **WHEN** processing a PR with files in the migrations directory
- **THEN** the system SHALL skip analysis of ignored files
- **AND** the system SHALL not generate suggestions for those files

### Requirement: Review preferences
The system SHALL respect review preferences for thoroughness, suggestion limits, and focus areas.

#### Scenario: Thoroughness preference
- **GIVEN** an AGENTS.md specifying "thorough" review mode
- **WHEN** processing a PR
- **THEN** the system SHALL use more comprehensive analysis
- **AND** the system SHALL increase token budgets for the review

#### Scenario: Suggestion limits
- **GIVEN** an AGENTS.md specifying max suggestions per category
- **WHEN** filtering suggestions
- **THEN** the system SHALL apply the specified limits
- **AND** the system SHALL prioritize suggestions accordingly
