# ==============================================================================
# AI INTELLIGENCE ZONE — Control Arena
# AI Response Validation Engine
# ==============================================================================
# Multi-stage validation pipeline:
#   Stage 1: JSON Parse
#   Stage 2: Schema Validation
#   Stage 3: Type Enforcement
#   Stage 4: Field Count Check
#   Stage 5: Regex Validation
#   Stage 6: Confidence Scoring
# ==============================================================================

import re
import json
import math
from typing import Any
from jsonschema import validate, ValidationError as JsonSchemaError, Draft7Validator


class ValidationResult:
    """Container for validation pipeline results."""

    def __init__(self):
        self.json_valid = False
        self.schema_valid = False
        self.type_check_valid = False
        self.regex_valid = False
        self.field_count_valid = False
        self.confidence_score = 0.0
        self.parsed_data = None
        self.errors = []
        self.warnings = []
        self.stage_results = {}

    @property
    def is_valid(self) -> bool:
        return all([
            self.json_valid,
            self.schema_valid,
            self.type_check_valid,
            self.field_count_valid,
        ])

    @property
    def overall_status(self) -> str:
        if self.is_valid:
            return "valid"
        if self.json_valid:
            return "invalid"  # Parsed but failed validation
        return "error"  # Couldn't even parse

    @property
    def accuracy_percentage(self) -> float:
        """Calculate accuracy as percentage of passed stages."""
        stages = [
            self.json_valid,
            self.schema_valid,
            self.type_check_valid,
            self.regex_valid,
            self.field_count_valid,
        ]
        passed = sum(1 for s in stages if s)
        return (passed / len(stages)) * 100

    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "overall_status": self.overall_status,
            "json_valid": self.json_valid,
            "schema_valid": self.schema_valid,
            "type_check_valid": self.type_check_valid,
            "regex_valid": self.regex_valid,
            "field_count_valid": self.field_count_valid,
            "confidence_score": round(self.confidence_score, 4),
            "accuracy_percentage": round(self.accuracy_percentage, 1),
            "errors": self.errors,
            "warnings": self.warnings,
            "stage_results": self.stage_results,
        }


class ValidationEngine:
    """
    Multi-stage AI response validation engine.
    Processes AI outputs through a strict pipeline.
    """

    # ══════════════════════════════════════════════════════════════════════
    # MAIN VALIDATION PIPELINE
    # ══════════════════════════════════════════════════════════════════════

    @classmethod
    def validate(cls, raw_response: str, schema: dict = None,
                 expected_fields: list = None, regex_patterns: dict = None,
                 strict_mode: bool = True) -> ValidationResult:
        """
        Run the full validation pipeline on an AI response.

        Args:
            raw_response: Raw text output from AI
            schema: JSON Schema dict for validation
            expected_fields: List of required field names
            regex_patterns: Dict of {field_name: regex_pattern} for validation
            strict_mode: If True, extra fields cause failure

        Returns:
            ValidationResult with detailed stage-by-stage results
        """
        result = ValidationResult()

        # ── Stage 1: JSON Parse ───────────────────────────────────────
        parsed = cls._stage_json_parse(raw_response, result)
        if parsed is None:
            return result  # Can't continue without valid JSON

        # ── Stage 2: Schema Validation ────────────────────────────────
        if schema:
            cls._stage_schema_validation(parsed, schema, result)
        else:
            result.schema_valid = True
            result.stage_results["schema"] = {"status": "skipped", "reason": "no schema provided"}

        # ── Stage 3: Type Enforcement ─────────────────────────────────
        if schema and "properties" in schema:
            cls._stage_type_enforcement(parsed, schema, result)
        else:
            result.type_check_valid = True
            result.stage_results["type_check"] = {"status": "skipped"}

        # ── Stage 4: Field Count Check ────────────────────────────────
        cls._stage_field_count(parsed, expected_fields, strict_mode, result)

        # ── Stage 5: Regex Validation ─────────────────────────────────
        if regex_patterns:
            cls._stage_regex_validation(parsed, regex_patterns, result)
        else:
            result.regex_valid = True
            result.stage_results["regex"] = {"status": "skipped", "reason": "no patterns provided"}

        # ── Stage 6: Confidence Scoring ───────────────────────────────
        cls._stage_confidence_scoring(parsed, schema, expected_fields, result)

        return result

    # ══════════════════════════════════════════════════════════════════════
    # STAGE 1: JSON PARSE
    # ══════════════════════════════════════════════════════════════════════

    @classmethod
    def _stage_json_parse(cls, raw_response: str, result: ValidationResult):
        """Attempt to parse raw response as JSON."""
        stage = {"status": "failed", "attempts": []}

        # Attempt 1: Direct parse
        try:
            parsed = json.loads(raw_response)
            result.json_valid = True
            result.parsed_data = parsed
            stage["status"] = "success"
            stage["method"] = "direct_parse"
            result.stage_results["json_parse"] = stage
            return parsed
        except json.JSONDecodeError as e:
            stage["attempts"].append({"method": "direct", "error": str(e)})

        # Attempt 2: Extract JSON from markdown code blocks
        json_match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", raw_response)
        if json_match:
            try:
                parsed = json.loads(json_match.group(1).strip())
                result.json_valid = True
                result.parsed_data = parsed
                stage["status"] = "success"
                stage["method"] = "markdown_extraction"
                result.warnings.append("JSON was extracted from markdown code block")
                result.stage_results["json_parse"] = stage
                return parsed
            except json.JSONDecodeError as e:
                stage["attempts"].append({"method": "markdown", "error": str(e)})

        # Attempt 3: Find JSON-like structure with braces
        brace_match = re.search(r"\{[\s\S]*\}", raw_response)
        if brace_match:
            try:
                parsed = json.loads(brace_match.group(0))
                result.json_valid = True
                result.parsed_data = parsed
                stage["status"] = "success"
                stage["method"] = "brace_extraction"
                result.warnings.append("JSON was extracted from surrounding text")
                result.stage_results["json_parse"] = stage
                return parsed
            except json.JSONDecodeError as e:
                stage["attempts"].append({"method": "brace_extract", "error": str(e)})

        # Attempt 4: Find JSON array
        bracket_match = re.search(r"\[[\s\S]*\]", raw_response)
        if bracket_match:
            try:
                parsed = json.loads(bracket_match.group(0))
                result.json_valid = True
                result.parsed_data = parsed
                stage["status"] = "success"
                stage["method"] = "array_extraction"
                result.warnings.append("JSON array was extracted from surrounding text")
                result.stage_results["json_parse"] = stage
                return parsed
            except json.JSONDecodeError as e:
                stage["attempts"].append({"method": "array_extract", "error": str(e)})

        # All attempts failed
        result.errors.append("Failed to parse response as valid JSON after 4 extraction attempts")
        result.stage_results["json_parse"] = stage
        return None

    # ══════════════════════════════════════════════════════════════════════
    # STAGE 2: SCHEMA VALIDATION
    # ══════════════════════════════════════════════════════════════════════

    @classmethod
    def _stage_schema_validation(cls, data: Any, schema: dict, result: ValidationResult):
        """Validate parsed data against JSON Schema."""
        stage = {"status": "failed", "errors": []}

        try:
            validate(instance=data, schema=schema, cls=Draft7Validator)
            result.schema_valid = True
            stage["status"] = "success"
        except JsonSchemaError as e:
            result.errors.append(f"Schema validation error: {e.message}")
            stage["errors"].append({
                "path": list(e.absolute_path),
                "message": e.message,
                "validator": e.validator,
            })
        except Exception as e:
            result.errors.append(f"Schema validation exception: {str(e)}")
            stage["errors"].append({"message": str(e)})

        result.stage_results["schema"] = stage

    # ══════════════════════════════════════════════════════════════════════
    # STAGE 3: TYPE ENFORCEMENT
    # ══════════════════════════════════════════════════════════════════════

    TYPE_MAP = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
        "null": type(None),
    }

    @classmethod
    def _stage_type_enforcement(cls, data: Any, schema: dict, result: ValidationResult):
        """Strictly enforce types for each field based on schema."""
        if not isinstance(data, dict):
            result.type_check_valid = True
            result.stage_results["type_check"] = {"status": "skipped", "reason": "data not a dict"}
            return

        stage = {"status": "success", "checked": 0, "failed": 0, "details": []}
        properties = schema.get("properties", {})

        for field_name, field_schema in properties.items():
            if field_name not in data:
                continue

            stage["checked"] += 1
            expected_type = field_schema.get("type")

            if expected_type and expected_type in cls.TYPE_MAP:
                expected_python_type = cls.TYPE_MAP[expected_type]
                actual_value = data[field_name]

                if not isinstance(actual_value, expected_python_type):
                    stage["failed"] += 1
                    stage["details"].append({
                        "field": field_name,
                        "expected": expected_type,
                        "actual": type(actual_value).__name__,
                        "value_preview": str(actual_value)[:100],
                    })
                    result.errors.append(
                        f"Type mismatch for '{field_name}': "
                        f"expected {expected_type}, got {type(actual_value).__name__}"
                    )

        if stage["failed"] > 0:
            stage["status"] = "failed"
            result.type_check_valid = False
        else:
            result.type_check_valid = True

        result.stage_results["type_check"] = stage

    # ══════════════════════════════════════════════════════════════════════
    # STAGE 4: FIELD COUNT CHECK
    # ══════════════════════════════════════════════════════════════════════

    @classmethod
    def _stage_field_count(cls, data: Any, expected_fields: list,
                           strict_mode: bool, result: ValidationResult):
        """Verify field counts and presence."""
        if not isinstance(data, dict):
            result.field_count_valid = True
            result.stage_results["field_count"] = {"status": "skipped", "reason": "data not a dict"}
            return

        stage = {
            "status": "success",
            "actual_count": len(data),
            "expected_fields": expected_fields or [],
            "missing": [],
            "extra": [],
        }

        if expected_fields:
            actual_fields = set(data.keys())
            expected_set = set(expected_fields)

            stage["missing"] = list(expected_set - actual_fields)
            stage["extra"] = list(actual_fields - expected_set)

            if stage["missing"]:
                result.errors.append(f"Missing required fields: {stage['missing']}")
                stage["status"] = "failed"

            if strict_mode and stage["extra"]:
                result.warnings.append(f"Extra unexpected fields: {stage['extra']}")
                # In strict mode, extra fields are a failure
                stage["status"] = "failed"

        result.field_count_valid = stage["status"] == "success"
        result.stage_results["field_count"] = stage

    # ══════════════════════════════════════════════════════════════════════
    # STAGE 5: REGEX VALIDATION
    # ══════════════════════════════════════════════════════════════════════

    @classmethod
    def _stage_regex_validation(cls, data: Any, regex_patterns: dict, result: ValidationResult):
        """Validate specific fields against regex patterns."""
        if not isinstance(data, dict):
            result.regex_valid = True
            return

        stage = {"status": "success", "checked": 0, "failed": 0, "details": []}

        for field_name, pattern in regex_patterns.items():
            if field_name not in data:
                continue

            stage["checked"] += 1
            value = str(data[field_name])

            try:
                if not re.fullmatch(pattern, value):
                    stage["failed"] += 1
                    stage["details"].append({
                        "field": field_name,
                        "pattern": pattern,
                        "value_preview": value[:100],
                        "status": "no_match",
                    })
                    result.errors.append(
                        f"Regex validation failed for '{field_name}': "
                        f"value does not match pattern '{pattern}'"
                    )
            except re.error as e:
                stage["details"].append({
                    "field": field_name,
                    "error": f"Invalid regex: {e}",
                })

        if stage["failed"] > 0:
            stage["status"] = "failed"
            result.regex_valid = False
        else:
            result.regex_valid = True

        result.stage_results["regex"] = stage

    # ══════════════════════════════════════════════════════════════════════
    # STAGE 6: CONFIDENCE SCORING
    # ══════════════════════════════════════════════════════════════════════

    @classmethod
    def _stage_confidence_scoring(cls, data: Any, schema: dict = None,
                                   expected_fields: list = None,
                                   result: ValidationResult = None):
        """
        Calculate confidence score (0.0 - 1.0) based on multiple factors.

        Factors:
        - Completeness: Are all expected fields present?
        - Type accuracy: Do all types match?
        - Content quality: Are values non-empty and meaningful?
        - Structure: Does the nesting match expectations?
        """
        scores = []

        if not isinstance(data, dict):
            result.confidence_score = 0.1 if result.json_valid else 0.0
            result.stage_results["confidence"] = {"score": result.confidence_score, "method": "non_dict"}
            return

        # ── Completeness Score ────────────────────────────────────────
        if expected_fields:
            present = sum(1 for f in expected_fields if f in data)
            completeness = present / len(expected_fields)
            scores.append(("completeness", completeness))

        # ── Content Quality Score ─────────────────────────────────────
        non_empty = 0
        total = len(data)
        for key, value in data.items():
            if value is not None and value != "" and value != [] and value != {}:
                non_empty += 1
        quality = non_empty / max(total, 1)
        scores.append(("content_quality", quality))

        # ── Validation Pass Rate ──────────────────────────────────────
        stages_passed = sum([
            result.json_valid,
            result.schema_valid,
            result.type_check_valid,
            result.regex_valid,
            result.field_count_valid,
        ])
        validation_rate = stages_passed / 5
        scores.append(("validation_rate", validation_rate))

        # ── Error Penalty ─────────────────────────────────────────────
        error_penalty = max(0, 1 - (len(result.errors) * 0.15))
        scores.append(("error_penalty", error_penalty))

        # ── Weighted Average ──────────────────────────────────────────
        if scores:
            total_score = sum(s[1] for s in scores) / len(scores)
        else:
            total_score = 0.5 if result.json_valid else 0.0

        result.confidence_score = round(min(1.0, max(0.0, total_score)), 4)
        result.stage_results["confidence"] = {
            "score": result.confidence_score,
            "components": {name: round(val, 4) for name, val in scores},
        }


# ==============================================================================
# HALLUCINATION DETECTOR
# ==============================================================================
class HallucinationDetector:
    """
    Basic hallucination detection heuristics.
    Checks for common patterns that indicate AI hallucination.
    """

    @staticmethod
    def estimate_probability(prompt: str, response: str, parsed_data: dict = None) -> float:
        """
        Estimate the probability that the response contains hallucinations.
        Returns float between 0.0 (likely real) and 1.0 (likely hallucinated).
        """
        score = 0.0
        checks = 0

        if not response:
            return 0.0

        # ── Check 1: Response much longer than prompt ─────────────────
        if len(response) > len(prompt) * 10:
            score += 0.3
        checks += 1

        # ── Check 2: Contains hedging language ────────────────────────
        hedging_patterns = [
            r"\bi think\b", r"\bprobably\b", r"\bmaybe\b",
            r"\bI'm not sure\b", r"\bI believe\b", r"\bpossibly\b",
            r"\bapproximately\b", r"\bI don't have\b",
        ]
        hedging_count = sum(
            1 for p in hedging_patterns
            if re.search(p, response, re.IGNORECASE)
        )
        if hedging_count >= 3:
            score += 0.4
        elif hedging_count >= 1:
            score += 0.15
        checks += 1

        # ── Check 3: Contradictory statements ────────────────────────
        if re.search(r"\bhowever\b.*\bbut\b", response, re.IGNORECASE | re.DOTALL):
            score += 0.1
        checks += 1

        # ── Check 4: Repetitive content ──────────────────────────────
        sentences = re.split(r'[.!?]+', response)
        if len(sentences) > 3:
            unique_ratio = len(set(s.strip().lower() for s in sentences if s.strip())) / len(sentences)
            if unique_ratio < 0.5:
                score += 0.4
        checks += 1

        # ── Check 5: Contains fabricated-looking data ────────────────
        if parsed_data and isinstance(parsed_data, dict):
            # Check for suspiciously round numbers
            round_count = 0
            total_numbers = 0
            for value in parsed_data.values():
                if isinstance(value, (int, float)):
                    total_numbers += 1
                    if value == round(value) and value > 0:
                        round_count += 1
            if total_numbers > 3 and round_count / total_numbers > 0.8:
                score += 0.2
        checks += 1

        return min(1.0, score / (checks * 0.3))  # Normalize
