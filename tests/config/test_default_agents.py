"""Tests for config/default_agents.py - default agent configurations."""

from config.default_agents import (
    DEFAULT_CODE_PATTERNS,
    DEFAULT_IGNORE_PATTERNS,
    DEFAULT_SECURITY_PRIORITIES,
    DEFAULT_STYLE_RULES,
    get_default_config,
    get_language_config,
)


class TestDefaultStyleRules:
    """Tests for DEFAULT_STYLE_RULES."""

    def test_has_python_rules(self):
        assert "python" in DEFAULT_STYLE_RULES

    def test_has_javascript_rules(self):
        assert "javascript" in DEFAULT_STYLE_RULES

    def test_has_typescript_rules(self):
        assert "typescript" in DEFAULT_STYLE_RULES

    def test_python_max_line_length(self):
        assert DEFAULT_STYLE_RULES["python"]["max_line_length"] == 88

    def test_python_use_type_hints(self):
        assert DEFAULT_STYLE_RULES["python"]["use_type_hints"] is True

    def test_python_docstring_style(self):
        assert DEFAULT_STYLE_RULES["python"]["docstring_style"] == "google"

    def test_python_naming_conventions(self):
        naming = DEFAULT_STYLE_RULES["python"]["naming_conventions"]
        assert naming["functions"] == "snake_case"
        assert naming["classes"] == "PascalCase"
        assert naming["constants"] == "UPPER_SNAKE_CASE"
        assert naming["variables"] == "snake_case"

    def test_python_preferred_patterns(self):
        patterns = DEFAULT_STYLE_RULES["python"]["preferred_patterns"]
        assert isinstance(patterns, list)
        assert len(patterns) > 0
        assert any("f-string" in p.lower() for p in patterns)

    def test_javascript_max_line_length(self):
        assert DEFAULT_STYLE_RULES["javascript"]["max_line_length"] == 100

    def test_javascript_use_semicolons(self):
        assert DEFAULT_STYLE_RULES["javascript"]["use_semicolons"] is True

    def test_javascript_prefer_const(self):
        assert DEFAULT_STYLE_RULES["javascript"]["prefer_const"] is True

    def test_javascript_prefer_arrow_functions(self):
        assert DEFAULT_STYLE_RULES["javascript"]["prefer_arrow_functions"] is True

    def test_javascript_naming_conventions(self):
        naming = DEFAULT_STYLE_RULES["javascript"]["naming_conventions"]
        assert naming["functions"] == "camelCase"
        assert naming["classes"] == "PascalCase"
        assert naming["constants"] == "UPPER_SNAKE_CASE"
        assert naming["variables"] == "camelCase"

    def test_typescript_max_line_length(self):
        assert DEFAULT_STYLE_RULES["typescript"]["max_line_length"] == 100

    def test_typescript_strict_types(self):
        assert DEFAULT_STYLE_RULES["typescript"]["strict_types"] is True

    def test_typescript_prefer_interface(self):
        assert DEFAULT_STYLE_RULES["typescript"]["prefer_interface"] is True

    def test_typescript_naming_conventions_has_interfaces(self):
        naming = DEFAULT_STYLE_RULES["typescript"]["naming_conventions"]
        assert "interfaces" in naming
        assert naming["interfaces"] == "PascalCase"

    def test_typescript_naming_conventions_has_types(self):
        naming = DEFAULT_STYLE_RULES["typescript"]["naming_conventions"]
        assert "types" in naming
        assert naming["types"] == "PascalCase"


class TestDefaultSecurityPriorities:
    """Tests for DEFAULT_SECURITY_PRIORITIES."""

    def test_has_high_priority(self):
        assert "high" in DEFAULT_SECURITY_PRIORITIES

    def test_has_medium_priority(self):
        assert "medium" in DEFAULT_SECURITY_PRIORITIES

    def test_has_low_priority(self):
        assert "low" in DEFAULT_SECURITY_PRIORITIES

    def test_high_priority_includes_sql_injection(self):
        assert any("SQL injection" in p for p in DEFAULT_SECURITY_PRIORITIES["high"])

    def test_high_priority_includes_hardcoded_secrets(self):
        assert any("Hardcoded secrets" in p for p in DEFAULT_SECURITY_PRIORITIES["high"])

    def test_high_priority_includes_command_injection(self):
        assert any("Command injection" in p for p in DEFAULT_SECURITY_PRIORITIES["high"])

    def test_high_priority_includes_path_traversal(self):
        assert any("Path traversal" in p for p in DEFAULT_SECURITY_PRIORITIES["high"])

    def test_medium_includes_xss(self):
        assert any(
            "XSS" in p or "Cross-site scripting" in p for p in DEFAULT_SECURITY_PRIORITIES["medium"]
        )

    def test_medium_includes_csrf(self):
        assert any("CSRF" in p for p in DEFAULT_SECURITY_PRIORITIES["medium"])

    def test_low_includes_info_disclosure(self):
        assert any("Information disclosure" in p for p in DEFAULT_SECURITY_PRIORITIES["low"])

    def test_high_has_more_items_than_low(self):
        assert len(DEFAULT_SECURITY_PRIORITIES["high"]) > len(DEFAULT_SECURITY_PRIORITIES["low"])


class TestDefaultIgnorePatterns:
    """Tests for DEFAULT_IGNORE_PATTERNS."""

    def test_is_list(self):
        assert isinstance(DEFAULT_IGNORE_PATTERNS, list)

    def test_not_empty(self):
        assert len(DEFAULT_IGNORE_PATTERNS) > 0

    def test_includes_node_modules(self):
        assert "node_modules/**" in DEFAULT_IGNORE_PATTERNS

    def test_includes_venv(self):
        assert ".venv/**" in DEFAULT_IGNORE_PATTERNS or "venv/**" in DEFAULT_IGNORE_PATTERNS

    def test_includes_pycache(self):
        assert "__pycache__/**" in DEFAULT_IGNORE_PATTERNS

    def test_includes_git(self):
        assert ".git/**" in DEFAULT_IGNORE_PATTERNS

    def test_includes_lock_files(self):
        assert "package-lock.json" in DEFAULT_IGNORE_PATTERNS
        assert "yarn.lock" in DEFAULT_IGNORE_PATTERNS
        assert "poetry.lock" in DEFAULT_IGNORE_PATTERNS

    def test_includes_minified_js(self):
        assert "*.min.js" in DEFAULT_IGNORE_PATTERNS

    def test_includes_image_files(self):
        assert "*.png" in DEFAULT_IGNORE_PATTERNS
        assert "*.jpg" in DEFAULT_IGNORE_PATTERNS

    def test_includes_markdown_docs(self):
        assert "*.md" in DEFAULT_IGNORE_PATTERNS

    def test_includes_test_fixtures(self):
        assert "**/fixtures/**" in DEFAULT_IGNORE_PATTERNS

    def test_includes_test_specs(self):
        assert any("spec" in p for p in DEFAULT_IGNORE_PATTERNS)


class TestDefaultCodePatterns:
    """Tests for DEFAULT_CODE_PATTERNS."""

    def test_has_python(self):
        assert "python" in DEFAULT_CODE_PATTERNS

    def test_has_javascript(self):
        assert "javascript" in DEFAULT_CODE_PATTERNS

    def test_python_has_good_patterns(self):
        assert "good_patterns" in DEFAULT_CODE_PATTERNS["python"]
        assert len(DEFAULT_CODE_PATTERNS["python"]["good_patterns"]) > 0

    def test_python_has_anti_patterns(self):
        assert "anti_patterns" in DEFAULT_CODE_PATTERNS["python"]
        assert len(DEFAULT_CODE_PATTERNS["python"]["anti_patterns"]) > 0

    def test_python_good_patterns_content(self):
        good = DEFAULT_CODE_PATTERNS["python"]["good_patterns"]
        assert any("context manager" in p.lower() for p in good)
        assert any("dataclass" in p.lower() for p in good)

    def test_python_anti_patterns_content(self):
        anti = DEFAULT_CODE_PATTERNS["python"]["anti_patterns"]
        assert any("mutable default" in p.lower() for p in anti)
        assert any("except" in p.lower() for p in anti)

    def test_javascript_good_patterns_content(self):
        good = DEFAULT_CODE_PATTERNS["javascript"]["good_patterns"]
        assert any("async/await" in p for p in good)
        assert any("destructuring" in p.lower() for p in good)

    def test_javascript_anti_patterns_content(self):
        anti = DEFAULT_CODE_PATTERNS["javascript"]["anti_patterns"]
        assert any("var" in p.lower() for p in anti)
        assert any("callback" in p.lower() for p in anti)


class TestGetDefaultConfig:
    """Tests for get_default_config function."""

    def test_returns_dict(self):
        config = get_default_config()
        assert isinstance(config, dict)

    def test_has_style_rules(self):
        config = get_default_config()
        assert "style_rules" in config
        assert config["style_rules"] is DEFAULT_STYLE_RULES

    def test_has_security_priorities(self):
        config = get_default_config()
        assert "security_priorities" in config
        assert config["security_priorities"] is DEFAULT_SECURITY_PRIORITIES

    def test_has_ignore_patterns(self):
        config = get_default_config()
        assert "ignore_patterns" in config
        assert config["ignore_patterns"] is DEFAULT_IGNORE_PATTERNS

    def test_has_code_patterns(self):
        config = get_default_config()
        assert "code_patterns" in config
        assert config["code_patterns"] is DEFAULT_CODE_PATTERNS

    def test_has_review_settings(self):
        config = get_default_config()
        assert "review_settings" in config

    def test_review_settings_max_suggestions_per_file(self):
        config = get_default_config()
        assert config["review_settings"]["max_suggestions_per_file"] == 10

    def test_review_settings_max_suggestions_total(self):
        config = get_default_config()
        assert config["review_settings"]["max_suggestions_total"] == 50

    def test_review_settings_severity_threshold(self):
        config = get_default_config()
        assert config["review_settings"]["severity_threshold"] == "suggestion"

    def test_review_settings_enable_all_agents(self):
        config = get_default_config()
        assert config["review_settings"]["enable_all_agents"] is True

    def test_review_settings_require_tests_for_new_features(self):
        config = get_default_config()
        assert config["review_settings"]["require_tests_for_new_features"] is True

    def test_review_settings_check_documentation(self):
        config = get_default_config()
        assert config["review_settings"]["check_documentation_for_public_apis"] is True

    def test_returns_all_five_top_level_keys(self):
        config = get_default_config()
        expected_keys = {
            "style_rules",
            "security_priorities",
            "ignore_patterns",
            "code_patterns",
            "review_settings",
        }
        assert set(config.keys()) == expected_keys


class TestGetLanguageConfig:
    """Tests for get_language_config function."""

    def test_python_config_has_style_rules(self):
        config = get_language_config("python")
        assert "style_rules" in config
        assert config["style_rules"] == DEFAULT_STYLE_RULES["python"]

    def test_python_config_has_code_patterns(self):
        config = get_language_config("python")
        assert "code_patterns" in config
        assert config["code_patterns"] == DEFAULT_CODE_PATTERNS["python"]

    def test_python_config_has_security_priorities(self):
        config = get_language_config("python")
        assert "security_priorities" in config
        assert config["security_priorities"] is DEFAULT_SECURITY_PRIORITIES

    def test_python_config_has_ignore_patterns(self):
        config = get_language_config("python")
        assert "ignore_patterns" in config
        assert config["ignore_patterns"] is DEFAULT_IGNORE_PATTERNS

    def test_python_config_has_review_settings(self):
        config = get_language_config("python")
        assert "review_settings" in config

    def test_javascript_config(self):
        config = get_language_config("javascript")
        assert config["style_rules"] == DEFAULT_STYLE_RULES["javascript"]
        assert config["code_patterns"] == DEFAULT_CODE_PATTERNS["javascript"]

    def test_typescript_config(self):
        config = get_language_config("typescript")
        assert config["style_rules"] == DEFAULT_STYLE_RULES["typescript"]
        # TypeScript has no code_patterns entry, returns empty dict
        assert config["code_patterns"] == {}

    def test_unknown_language_returns_empty_style_rules(self):
        config = get_language_config("rust")
        assert config["style_rules"] == {}

    def test_unknown_language_returns_empty_code_patterns(self):
        config = get_language_config("rust")
        assert config["code_patterns"] == {}

    def test_unknown_language_still_has_security_priorities(self):
        config = get_language_config("rust")
        assert config["security_priorities"] is DEFAULT_SECURITY_PRIORITIES

    def test_unknown_language_still_has_ignore_patterns(self):
        config = get_language_config("rust")
        assert config["ignore_patterns"] is DEFAULT_IGNORE_PATTERNS

    def test_unknown_language_still_has_review_settings(self):
        config = get_language_config("rust")
        assert "review_settings" in config
        assert config["review_settings"]["max_suggestions_per_file"] == 10

    def test_returns_five_keys(self):
        config = get_language_config("python")
        expected_keys = {
            "style_rules",
            "code_patterns",
            "security_priorities",
            "ignore_patterns",
            "review_settings",
        }
        assert set(config.keys()) == expected_keys

    def test_empty_string_language(self):
        """Empty string language returns empty style/code patterns."""
        config = get_language_config("")
        assert config["style_rules"] == {}
        assert config["code_patterns"] == {}

    def test_case_sensitive_lookup(self):
        """Language lookup is case-sensitive."""
        config = get_language_config("Python")
        # "Python" != "python", so returns empty
        assert config["style_rules"] == {}
