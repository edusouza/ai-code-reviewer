import re
from typing import List, Dict, Any
from src.agents.base import BaseAgent
from src.graph.state import ChunkInfo, Suggestion
from src.llm.client import VertexAIClient


class SecurityAgent(BaseAgent):
    """Agent that finds security vulnerabilities in code."""
    
    def __init__(self):
        super().__init__(name="security", priority=1)
        self.llm_client = VertexAIClient()
        self.patterns = self._load_security_patterns()
    
    def _load_security_patterns(self) -> List[Dict[str, Any]]:
        """Load security patterns for pattern-based detection."""
        return [
            {
                "name": "sql_injection",
                "pattern": r"(execute|cursor\.execute|raw|query)\s*\(\s*[^)]*\+[^)]*\)",
                "message": "Potential SQL injection vulnerability detected",
                "severity": "error",
                "languages": ["python", "javascript", "typescript", "java", "php"]
            },
            {
                "name": "hardcoded_password",
                "pattern": r"(password|passwd|pwd|secret|api_key|apikey)\s*=\s*['\"][^'\"]+['\"]",
                "message": "Hardcoded credential detected",
                "severity": "error",
                "languages": ["python", "javascript", "typescript", "java", "go", "ruby", "php"]
            },
            {
                "name": "eval_usage",
                "pattern": r"\beval\s*\(|\bexec\s*\(",
                "message": "Use of eval/exec can lead to code injection",
                "severity": "warning",
                "languages": ["python", "javascript"]
            },
            {
                "name": "pickle_usage",
                "pattern": r"\bpickle\.loads?\s*\(",
                "message": "Pickle deserialization can execute arbitrary code",
                "severity": "warning",
                "languages": ["python"]
            },
            {
                "name": "xss_vulnerability",
                "pattern": r"innerHTML|dangerouslySetInnerHTML",
                "message": "Potential XSS vulnerability - consider sanitizing input",
                "severity": "warning",
                "languages": ["javascript", "typescript"]
            },
            {
                "name": "shell_injection",
                "pattern": r"(os\.system|subprocess\.call|subprocess\.Popen)\s*\(\s*[^)]*\+[^)]*\)",
                "message": "Potential shell injection vulnerability",
                "severity": "error",
                "languages": ["python"]
            },
            {
                "name": "insecure_hash",
                "pattern": r"\bmd5\s*\(|\bsha1\s*\(",
                "message": "Insecure hash algorithm - use SHA-256 or higher",
                "severity": "warning",
                "languages": ["python", "javascript", "typescript", "java", "go"]
            },
            {
                "name": "disabled_ssl_verification",
                "pattern": r"verify\s*=\s*False|verify_ssl\s*=\s*False|NODE_TLS_REJECT_UNAUTHORIZED",
                "message": "SSL verification disabled - security risk",
                "severity": "error",
                "languages": ["python", "javascript", "typescript"]
            }
        ]
    
    def get_system_prompt(self) -> str:
        """Get the system prompt for security analysis."""
        return """You are a security expert analyzing code for vulnerabilities.

Analyze the provided code for:
1. SQL injection vulnerabilities
2. Cross-site scripting (XSS) risks
3. Hardcoded secrets/credentials
4. Insecure deserialization
5. Command injection
6. Path traversal
7. Insecure cryptographic practices
8. Authentication/authorization flaws

For each issue found, provide:
- Line number
- Description of the vulnerability
- Severity (error/warning/suggestion)
- Suggested fix
- Confidence score (0.0-1.0)

Format your response as a JSON array of findings."""
    
    async def analyze(self, chunk: ChunkInfo, context: Dict[str, Any]) -> List[Suggestion]:
        """Analyze code for security vulnerabilities."""
        suggestions = []
        
        # Pattern-based detection
        for pattern_def in self.patterns:
            if chunk["language"] in pattern_def["languages"]:
                for match in re.finditer(pattern_def["pattern"], chunk["content"], re.IGNORECASE):
                    line_num = chunk["start_line"] + chunk["content"][:match.start()].count("\n")
                    suggestions.append(self.format_suggestion(
                        file_path=chunk["file_path"],
                        line_number=line_num,
                        message=pattern_def["message"],
                        severity=pattern_def["severity"],
                        category="security",
                        confidence=0.9
                    ))
        
        # LLM-based analysis for complex vulnerabilities
        try:
            llm_suggestions = await self._llm_analysis(chunk, context)
            suggestions.extend(llm_suggestions)
        except Exception:
            # Continue with pattern-based results if LLM fails
            pass
        
        return suggestions
    
    async def _llm_analysis(self, chunk: ChunkInfo, context: Dict[str, Any]) -> List[Suggestion]:
        """Use LLM for deeper security analysis."""
        # Skip LLM analysis for small or non-code chunks
        if len(chunk["content"]) < 100:
            return []
        
        prompt = f"""Analyze this {chunk['language']} code for security vulnerabilities:

```
{chunk['content']}
```

Context: {context.get('agnets_md', 'No AGENTS.md context')}

Find any security issues and return them as a JSON array with fields: line_number, message, severity, suggestion, confidence"""
        
        try:
            response = await self.llm_client.generate(
                prompt=prompt,
                system_prompt=self.get_system_prompt(),
                temperature=0.1
            )
            
            # Parse LLM response
            import json
            findings = json.loads(response)
            
            suggestions = []
            for finding in findings:
                suggestions.append(self.format_suggestion(
                    file_path=chunk["file_path"],
                    line_number=finding.get("line_number", chunk["start_line"]),
                    message=finding.get("message", "Security issue detected"),
                    severity=finding.get("severity", "warning"),
                    suggestion=finding.get("suggestion"),
                    category="security",
                    confidence=finding.get("confidence", 0.7)
                ))
            
            return suggestions
        
        except Exception:
            return []
    
    def should_analyze(self, chunk: ChunkInfo) -> bool:
        """Security agent analyzes all code files."""
        return chunk["language"] != "unknown"
