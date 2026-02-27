## ADDED Requirements

### Requirement: Webhook endpoint normalization
The system SHALL provide normalized webhook endpoints for all supported Git providers that abstract provider-specific differences into a common event format.

#### Scenario: GitHub webhook received
- **WHEN** GitHub sends a pull_request webhook to `/webhooks/github`
- **THEN** the system SHALL parse the payload and normalize it to a common PR event structure
- **AND** the system SHALL queue the event for processing

#### Scenario: GitLab webhook received
- **WHEN** GitLab sends a merge_request webhook to `/webhooks/gitlab`
- **THEN** the system SHALL parse the payload and normalize it to the same PR event structure as GitHub
- **AND** the system SHALL queue the event for processing

#### Scenario: Bitbucket webhook received
- **WHEN** Bitbucket sends a pullrequest webhook to `/webhooks/bitbucket`
- **THEN** the system SHALL parse the payload and normalize it to the same PR event structure
- **AND** the system SHALL queue the event for processing

### Requirement: HMAC signature verification
The system SHALL verify webhook signatures using HMAC to ensure payload authenticity for each provider.

#### Scenario: Valid GitHub signature
- **WHEN** a GitHub webhook is received with valid X-Hub-Signature-256 header
- **THEN** the system SHALL verify the signature against the stored secret
- **AND** the system SHALL process the webhook if valid

#### Scenario: Invalid signature
- **WHEN** a webhook is received with invalid or missing signature
- **THEN** the system SHALL reject the request with HTTP 401
- **AND** the system SHALL log the rejection

### Requirement: Provider credential management
The system SHALL securely store and retrieve provider credentials (tokens, app credentials) using Secret Manager.

#### Scenario: Private repository access
- **WHEN** processing a PR from a private repository
- **THEN** the system SHALL retrieve the appropriate access token from Secret Manager
- **AND** the system SHALL use the token to fetch code and post comments

#### Scenario: Provider token rotation
- **WHEN** a provider token is rotated
- **THEN** the system SHALL use the new token from Secret Manager without code changes
- **AND** the system SHALL continue processing PRs without interruption

### Requirement: Comment publication
The system SHALL publish review comments back to the original provider using provider-specific APIs.

#### Scenario: Post comment to GitHub
- **WHEN** the AI review generates a suggestion for a GitHub PR
- **THEN** the system SHALL post the comment using GitHub's PR review API
- **AND** the comment SHALL include line references and file paths

#### Scenario: Post comment to GitLab
- **WHEN** the AI review generates a suggestion for a GitLab MR
- **THEN** the system SHALL post the comment using GitLab's merge request discussions API
- **AND** the comment SHALL maintain the same format as GitHub comments

#### Scenario: Post comment to Bitbucket
- **WHEN** the AI review generates a suggestion for a Bitbucket PR
- **THEN** the system SHALL post the comment using Bitbucket's pull request comments API
- **AND** the comment SHALL maintain the same format as other providers
