"""Test fixtures and configuration."""
import pytest
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, AsyncMock

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def sample_github_pr_payload():
    """Sample GitHub pull request webhook payload."""
    return {
        "action": "opened",
        "number": 42,
        "pull_request": {
            "number": 42,
            "title": "Add new feature",
            "body": "This PR adds a new feature",
            "state": "open",
            "merged": False,
            "head": {
                "ref": "feature/new-thing",
                "sha": "abc123def456",
                "repo": {
                    "full_name": "myorg/myrepo"
                }
            },
            "base": {
                "ref": "main",
                "sha": "def789abc012"
            },
            "user": {
                "login": "johndoe"
            },
            "html_url": "https://github.com/myorg/myrepo/pull/42"
        },
        "repository": {
            "name": "myrepo",
            "full_name": "myorg/myrepo",
            "owner": {
                "login": "myorg"
            }
        },
        "sender": {
            "login": "johndoe"
        }
    }


@pytest.fixture
def sample_gitlab_mr_payload():
    """Sample GitLab merge request webhook payload."""
    return {
        "object_kind": "merge_request",
        "event_type": "merge_request",
        "project": {
            "name": "myrepo",
            "namespace": "myorg",
            "web_url": "https://gitlab.com/myorg/myrepo"
        },
        "object_attributes": {
            "iid": 42,
            "title": "Add new feature",
            "description": "This MR adds a new feature",
            "state": "opened",
            "action": "open",
            "source_branch": "feature/new-thing",
            "target_branch": "main",
            "url": "https://gitlab.com/myorg/myrepo/-/merge_requests/42",
            "author_id": "johndoe",
            "last_commit": {
                "id": "abc123def456",
                "message": "Add new feature",
                "timestamp": datetime.now().isoformat()
            }
        }
    }


@pytest.fixture
def sample_bitbucket_pr_payload():
    """Sample Bitbucket pull request webhook payload."""
    return {
        "pullrequest": {
            "id": 42,
            "title": "Add new feature",
            "description": "This PR adds a new feature",
            "state": "OPEN",
            "source": {
                "branch": {
                    "name": "feature/new-thing"
                },
                "commit": {
                    "hash": "abc123def456"
                },
                "repository": {
                    "name": "myrepo",
                    "full_name": "myorg/myrepo"
                }
            },
            "destination": {
                "branch": {
                    "name": "main"
                },
                "repository": {
                    "name": "myrepo",
                    "full_name": "myorg/myrepo"
                }
            },
            "author": {
                "username": "johndoe",
                "display_name": "John Doe"
            },
            "links": {
                "html": {
                    "href": "https://bitbucket.org/myorg/myrepo/pull-requests/42"
                }
            }
        }
    }


@pytest.fixture
def sample_pr_event():
    """Sample normalized PREvent."""
    from models.events import PREvent, PRAction
    return PREvent(
        provider="github",
        repo_owner="myorg",
        repo_name="myrepo",
        pr_number=42,
        action=PRAction.OPENED,
        branch="feature/new-thing",
        target_branch="main",
        commit_sha="abc123def456",
        pr_title="Add new feature",
        pr_body="This PR adds a new feature",
        author="johndoe",
        url="https://github.com/myorg/myrepo/pull/42"
    )


@pytest.fixture
def sample_chunk():
    """Sample code chunk for testing agents."""
    from graph.state import ChunkInfo
    return ChunkInfo(
        file_path="src/main.py",
        start_line=1,
        end_line=10,
        content="def process(data):\n    password = 'secret123'\n    eval(data)\n    return data\n",
        language="python"
    )


@pytest.fixture
def sample_agents_md():
    """Sample AGENTS.md content."""
    return """
# AI Code Review Configuration

## Style Rules

### Python
- Max line length: 120
- Use type hints: yes
- Naming conventions:
  - functions: snake_case
  - classes: PascalCase
  - constants: UPPER_CASE

### JavaScript/TypeScript
- Max line length: 100
- Use semicolons: yes
- Prefer const over let/var

## Security Priorities

### High
- SQL injection vulnerabilities
- Hardcoded credentials
- XSS vulnerabilities

### Medium
- Insecure hash algorithms
- Disabled SSL verification

### Low
- Information disclosure in comments

## Ignore Patterns
- tests/**
- **/*.test.js
- **/node_modules/**
- **/.git/**

## Code Patterns

### Good Patterns
- Use dependency injection
- Validate all inputs
- Handle errors explicitly

### Anti-Patterns
- Magic numbers
- Deep nesting (>3 levels)
- Catch-all exceptions

## Review Settings
- Max suggestions per file: 10
- Total max suggestions: 50
- Severity threshold: suggestion
- Require tests for new features: yes
- Check documentation for public APIs: yes

## Custom Rules

### No Console in Production
Avoid console.log statements in production code.

### Prefer Async/Await
Use async/await instead of raw promises.
"""


@pytest.fixture
def sample_suggestions():
    """Sample suggestions for testing."""
    return [
        {
            "file_path": "src/main.py",
            "line_number": 10,
            "message": "Potential SQL injection vulnerability",
            "severity": "error",
            "suggestion": "Use parameterized queries",
            "agent_type": "security",
            "confidence": 0.95,
            "category": "security"
        },
        {
            "file_path": "src/main.py",
            "line_number": 15,
            "message": "Line exceeds 120 characters",
            "severity": "suggestion",
            "suggestion": None,
            "agent_type": "style",
            "confidence": 0.9,
            "category": "style"
        },
        {
            "file_path": "src/utils.py",
            "line_number": 5,
            "message": "Potential null pointer",
            "severity": "warning",
            "suggestion": "Add null check before accessing",
            "agent_type": "logic",
            "confidence": 0.8,
            "category": "logic"
        }
    ]


@pytest.fixture
def mock_llm_client():
    """Mock LLM client."""
    client = Mock()
    client.generate = AsyncMock(return_value='[]')
    client.generate_json = AsyncMock(return_value={
        "style_rules": {},
        "security_priorities": {"high": [], "medium": [], "low": []},
        "ignore_patterns": [],
        "code_patterns": {},
        "review_settings": {}
    })
    return client


@pytest.fixture
def mock_httpx_client():
    """Mock httpx client for provider tests."""
    with pytest.mock.patch("httpx.AsyncClient") as mock:
        client_instance = Mock()
        client_instance.get = AsyncMock()
        client_instance.post = AsyncMock()
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=None)
        mock.return_value = client_instance
        yield mock


@pytest.fixture
def github_headers():
    """Sample GitHub webhook headers."""
    return {
        "X-GitHub-Event": "pull_request",
        "X-GitHub-Delivery": "test-delivery-id",
        "Content-Type": "application/json"
    }


@pytest.fixture
def gitlab_headers():
    """Sample GitLab webhook headers."""
    return {
        "X-Gitlab-Event": "Merge Request Hook",
        "X-Gitlab-Token": "test-token"
    }


@pytest.fixture
def bitbucket_headers():
    """Sample Bitbucket webhook headers."""
    return {
        "X-Event-Key": "pullrequest:created",
        "Content-Type": "application/json"
    }


@pytest.fixture
def sample_code_diff():
    """Sample code diff for testing."""
    return '''diff --git a/src/main.py b/src/main.py
index 1234567..abcdefg 100644
--- a/src/main.py
+++ b/src/main.py
@@ -1,5 +1,10 @@
 def process(data):
+    password = 'secret123'
+    eval(data)
     return data
 
+def query_db(user_input):
+    cursor.execute("SELECT * FROM users WHERE id = " + user_input)
+
 class User:
     def __init__(self, name):
         self.name = name
@@ -10,5 +15,8 @@ class User:
     def get_name(self):
         return self.name
 
+    def insecure_method(self):
+        os.system("rm -rf /")
+
 if __name__ == "__main__":
     main()

diff --git a/src/utils.js b/src/utils.js
index 9876543..fedcba9 100644
--- a/src/utils.js
+++ b/src/utils.js
@@ -1,5 +1,10 @@
 function process(data) {
+    if (data == null) {
+        return null;
+    }
     return data.toString();
 }
 
+const password = "hardcoded_secret";
+
 module.exports = { process };
'''


@pytest.fixture
def sample_review_config():
    """Sample review configuration."""
    from graph.state import ReviewConfig
    return ReviewConfig(
        max_suggestions=50,
        severity_threshold="suggestion",
        enable_agents={"security": True, "style": True, "logic": True},
        custom_rules={}
    )


@pytest.fixture
def sample_review_state(sample_pr_event, sample_review_config):
    """Sample review state for workflow tests."""
    from graph.state import ReviewState, ReviewMetadata
    from datetime import datetime
    
    return ReviewState(
        pr_event=sample_pr_event,
        config=sample_review_config,
        pr_diff="",
        agnets_md=None,
        chunks=[],
        current_chunk_index=0,
        suggestions=[],
        raw_agent_outputs={},
        validated_suggestions=[],
        rejected_suggestions=[],
        comments=[],
        summary="",
        passed=True,
        metadata=ReviewMetadata(
            review_id="test-review-123",
            started_at=datetime.now(),
            completed_at=None,
            current_step="init",
            agent_results={},
            error_count=0
        ),
        error=None,
        should_stop=False
    )
