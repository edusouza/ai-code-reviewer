"""Default agent configuration when AGENTS.md is not present."""
from typing import Dict, List, Any


DEFAULT_STYLE_RULES = {
    "python": {
        "max_line_length": 88,
        "use_type_hints": True,
        "docstring_style": "google",
        "naming_conventions": {
            "functions": "snake_case",
            "classes": "PascalCase",
            "constants": "UPPER_SNAKE_CASE",
            "variables": "snake_case"
        },
        "preferred_patterns": [
            "Use list comprehensions over map/filter",
            "Use pathlib.Path instead of os.path",
            "Use f-strings for string formatting",
            "Use type hints for function signatures"
        ]
    },
    "javascript": {
        "max_line_length": 100,
        "use_semicolons": True,
        "prefer_const": True,
        "prefer_arrow_functions": True,
        "naming_conventions": {
            "functions": "camelCase",
            "classes": "PascalCase",
            "constants": "UPPER_SNAKE_CASE",
            "variables": "camelCase"
        }
    },
    "typescript": {
        "max_line_length": 100,
        "use_semicolons": True,
        "strict_types": True,
        "prefer_interface": True,
        "naming_conventions": {
            "functions": "camelCase",
            "classes": "PascalCase",
            "interfaces": "PascalCase",
            "types": "PascalCase",
            "constants": "UPPER_SNAKE_CASE",
            "variables": "camelCase"
        }
    }
}


DEFAULT_SECURITY_PRIORITIES = {
    "high": [
        "SQL injection vulnerabilities",
        "Command injection vulnerabilities",
        "Path traversal vulnerabilities",
        "Hardcoded secrets or credentials",
        "Insecure deserialization",
        "XXE (XML External Entity) vulnerabilities",
        "Authentication bypass vulnerabilities"
    ],
    "medium": [
        "Cross-site scripting (XSS) vulnerabilities",
        "CSRF vulnerabilities",
        "Insecure file uploads",
        "Weak cryptographic implementations",
        "Missing input validation"
    ],
    "low": [
        "Information disclosure in comments",
        "Verbose error messages",
        "Missing security headers"
    ]
}


DEFAULT_IGNORE_PATTERNS = [
    # Generated files
    "*.min.js",
    "*.min.css",
    "*.map",
    "bundle.js",
    "vendor/**",
    
    # Dependencies
    "node_modules/**",
    "vendor/**",
    ".venv/**",
    "venv/**",
    "__pycache__/**",
    ".git/**",
    
    # Lock files
    "package-lock.json",
    "yarn.lock",
    "poetry.lock",
    "Pipfile.lock",
    
    # Config files that shouldn't be reviewed
    ".editorconfig",
    ".gitignore",
    ".dockerignore",
    
    # Test data and fixtures
    "**/fixtures/**",
    "**/testdata/**",
    "**/*.test.{js,ts,jsx,tsx}",
    "**/*.spec.{js,ts,jsx,tsx}",
    "**/mocks/**",
    "**/__mocks__/**",
    
    # Documentation
    "*.md",
    "*.rst",
    "docs/**",
    "**/*.md",
    
    # Binary and image files
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.ico",
    "*.svg",
    "*.pdf",
    "*.zip",
    "*.tar",
    "*.gz",
    "*.bin"
]


DEFAULT_CODE_PATTERNS = {
    "python": {
        "good_patterns": [
            "Use context managers (with statements)",
            "Prefer composition over inheritance",
            "Use dataclasses for simple data structures",
            "Use enum for fixed sets of values",
            "Prefer async/await for I/O operations"
        ],
        "anti_patterns": [
            "Using mutable default arguments",
            "Catching bare 'except:' clauses",
            "Using 'is' for string/number comparison",
            "Reassigning built-in names (list, dict, etc.)",
            "Using global variables"
        ]
    },
    "javascript": {
        "good_patterns": [
            "Use async/await instead of callbacks",
            "Use destructuring for cleaner code",
            "Use optional chaining (?.) and nullish coalescing (??)",
            "Prefer template literals over string concatenation"
        ],
        "anti_patterns": [
            "Using var instead of let/const",
            "Implicit type coercion (== instead of ===)",
            "Modifying built-in prototypes",
            "Callback hell (deep nesting)",
            "Memory leaks from event listeners"
        ]
    }
}


def get_default_config() -> Dict[str, Any]:
    """
    Get the complete default configuration.
    
    Returns:
        Dictionary containing all default configuration settings
    """
    return {
        "style_rules": DEFAULT_STYLE_RULES,
        "security_priorities": DEFAULT_SECURITY_PRIORITIES,
        "ignore_patterns": DEFAULT_IGNORE_PATTERNS,
        "code_patterns": DEFAULT_CODE_PATTERNS,
        "review_settings": {
            "max_suggestions_per_file": 10,
            "max_suggestions_total": 50,
            "severity_threshold": "suggestion",
            "enable_all_agents": True,
            "require_tests_for_new_features": True,
            "check_documentation_for_public_apis": True
        }
    }


def get_language_config(language: str) -> Dict[str, Any]:
    """
    Get configuration for a specific language.
    
    Args:
        language: Programming language name
        
    Returns:
        Configuration dictionary for the language, or empty dict if not found
    """
    config = get_default_config()
    
    return {
        "style_rules": config["style_rules"].get(language, {}),
        "code_patterns": config["code_patterns"].get(language, {}),
        "security_priorities": config["security_priorities"],
        "ignore_patterns": config["ignore_patterns"],
        "review_settings": config["review_settings"]
    }
