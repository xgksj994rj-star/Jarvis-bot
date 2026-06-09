"""Real-time Code Review & Pair Programming - AI-assisted coding with live suggestions"""
import json
import ast
import re


def analyze_code_quality(code, language="python"):
    """Analyze code for quality, bugs, and improvements"""
    try:
        issues = []
        suggestions = []

        if language == "python":
            try:
                ast.parse(code)
                suggestions.append("✅ Code syntax is valid")
            except SyntaxError as e:
                issues.append(f"❌ Syntax error: {e}")

            # Check for common issues
            if "print(" in code and "f-string" not in code:
                suggestions.append("💡 Consider using f-strings for better formatting")

            if len([line for line in code.split('\n') if line.strip()]) > 50:
                suggestions.append("📏 Consider breaking large functions into smaller ones")

            if "TODO" in code or "FIXME" in code:
                issues.append("📝 Found TODO/FIXME comments that need attention")

        return {
            "issues": issues,
            "suggestions": suggestions,
            "complexity_score": len(code.split()) // 10,
            "maintainability": "high" if len(issues) == 0 else "medium" if len(issues) < 3 else "low"
        }
    except Exception as e:
        return {"error": str(e)}


def suggest_code_improvements(code_snippet, context=""):
    """Suggest specific code improvements"""
    try:
        suggestions = []

        # Pattern-based suggestions
        if "for i in range(len(" in code_snippet:
            suggestions.append("Use enumerate() instead of range(len()) for better readability")

        if "if x == True:" in code_snippet:
            suggestions.append("Simplify 'if x == True:' to 'if x:'")

        if "except Exception as e:" in code_snippet and "pass" in code_snippet:
            suggestions.append("Avoid bare 'except' clauses - catch specific exceptions")

        if len(code_snippet.split('\n')) > 20:
            suggestions.append("Consider extracting this into a separate function")

        return suggestions
    except Exception as e:
        return [f"Error analyzing code: {str(e)}"]


def start_pair_programming_session(partner_email, project_name):
    """Start a collaborative coding session"""
    try:
        session = {
            "session_id": f"pair_{project_name}_{partner_email}",
            "participants": ["user", partner_email],
            "project": project_name,
            "start_time": "now",
            "shared_cursor": True,
            "real_time_editing": True
        }
        return f"Pair programming session started with {partner_email} on project '{project_name}'"
    except Exception as e:
        return f"Error starting pair programming: {str(e)}"


def detect_code_smells(code, language="python"):
    """Detect common code smells and anti-patterns"""
    try:
        smells = []

        # Long method smell
        if len(code.split('\n')) > 30:
            smells.append("Long method - consider breaking into smaller functions")

        # Duplicate code smell
        lines = code.split('\n')
        duplicates = []
        for i, line in enumerate(lines):
            if line.strip() and line in lines[i+1:]:
                duplicates.append(line.strip())
        if duplicates:
            smells.append(f"Duplicate code detected: {duplicates[:3]}")

        # Magic numbers
        magic_nums = re.findall(r'\b\d{2,}\b', code)
        if magic_nums:
            smells.append(f"Consider replacing magic numbers: {magic_nums[:5]}")

        return smells
    except Exception as e:
        return [f"Error detecting smells: {str(e)}"]


def generate_unit_tests(code, language="python"):
    """Generate unit tests for the given code"""
    try:
        if language == "python":
            # Simple test generation for functions
            functions = re.findall(r'def (\w+)\([^)]*\):', code)
            tests = []
            for func in functions:
                tests.append(f"""
def test_{func}():
    # Test case for {func}
    result = {func}()
    assert result is not None  # Add proper assertions
""")
            return "\n".join(tests)
        return "Test generation not supported for this language"
    except Exception as e:
        return f"Error generating tests: {str(e)}"


def optimize_performance(code, language="python"):
    """Suggest performance optimizations"""
    try:
        optimizations = []

        if "for" in code and "append" in code:
            optimizations.append("Consider using list comprehensions instead of for loops with append")

        if "range(len(" in code:
            optimizations.append("Use enumerate() to avoid calling len() in loops")

        if "+" in code and "string" in code.lower():
            optimizations.append("Use ''.join() for string concatenation in loops")

        return optimizations
    except Exception as e:
        return [f"Error optimizing: {str(e)}"]