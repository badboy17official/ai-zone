# ==============================================================================
# AI INTELLIGENCE ZONE — Control Arena
# Security Engine — Injection Detection, Rate Limiting, Tamper Detection
# ==============================================================================

import re
import hashlib
import json
import math
from datetime import datetime, timezone, timedelta
from collections import Counter
from functools import wraps

from flask import request, g, abort, current_app
from models import db, SecurityEvent, AuditLog


# ==============================================================================
# PROMPT INJECTION DETECTION ENGINE
# ==============================================================================
class InjectionDetector:
    """
    Multi-layered prompt injection detection system.
    Uses pattern matching, entropy analysis, and structural analysis.
    """

    # ── Known Injection Patterns ──────────────────────────────────────────
    INJECTION_PATTERNS = [
        # Direct instruction override
        (r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?|rules?)", 0.95, "instruction_override"),
        (r"disregard\s+(all\s+)?(previous|above|prior)", 0.90, "instruction_override"),
        (r"forget\s+(everything|all|what)\s+(you|i)\s+(told|said|know)", 0.90, "instruction_override"),

        # System prompt extraction
        (r"(show|reveal|display|print|output)\s+(your|the|system)\s+(system\s+)?(prompt|instructions?)", 0.95, "prompt_extraction"),
        (r"what\s+(are|is)\s+your\s+(system\s+)?(instructions?|prompt|rules?)", 0.85, "prompt_extraction"),
        (r"repeat\s+(your|the)\s+(system\s+)?(prompt|instructions?)", 0.90, "prompt_extraction"),

        # Role play attacks
        (r"(pretend|act|imagine|roleplay)\s+(you\s+are|to\s+be|as)\s+(a\s+)?(different|new|another)", 0.80, "role_manipulation"),
        (r"you\s+are\s+now\s+(DAN|a\s+new|an?\s+unrestricted)", 0.95, "role_manipulation"),
        (r"jailbreak", 0.95, "jailbreak_attempt"),

        # Code injection
        (r"<script[^>]*>", 0.95, "xss_attempt"),
        (r"javascript\s*:", 0.90, "xss_attempt"),
        (r"on(load|error|click)\s*=", 0.85, "xss_attempt"),

        # SQL injection
        (r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE)\b.*\b(FROM|INTO|TABLE|SET)\b)", 0.85, "sql_injection"),
        (r"(--|;)\s*(DROP|DELETE|ALTER)\b", 0.95, "sql_injection"),
        (r"'\s*(OR|AND)\s*'?\d*'?\s*=\s*'?\d*", 0.90, "sql_injection"),

        # OS command injection
        (r";\s*(ls|cat|rm|wget|curl|chmod|bash|sh|python|node)\b", 0.90, "command_injection"),
        (r"\|\s*(ls|cat|rm|bash|sh)\b", 0.85, "command_injection"),
        (r"\$\(.*\)", 0.70, "command_injection"),

        # Path traversal
        (r"\.\./\.\./", 0.85, "path_traversal"),
        (r"/etc/(passwd|shadow|hosts)", 0.95, "path_traversal"),

        # Encoding tricks
        (r"&#x?[0-9a-fA-F]+;", 0.60, "encoding_evasion"),
        (r"\\u[0-9a-fA-F]{4}", 0.50, "encoding_evasion"),
        (r"base64\s*[:\(]", 0.70, "encoding_evasion"),

        # Token/boundary manipulation
        (r"\[INST\]|\[/INST\]|<\|system\|>|<\|user\|>|<\|assistant\|>", 0.95, "token_manipulation"),
        (r"<<SYS>>|<</SYS>>", 0.95, "token_manipulation"),
    ]

    @classmethod
    def analyze(cls, prompt_text: str) -> dict:
        """
        Analyze a prompt for injection attempts.

        Returns:
            dict with keys: is_suspicious, injection_score, patterns_found, details
        """
        if not prompt_text:
            return {"is_suspicious": False, "injection_score": 0.0, "patterns_found": [], "details": []}

        results = {
            "is_suspicious": False,
            "injection_score": 0.0,
            "patterns_found": [],
            "details": [],
        }

        max_score = 0.0

        # ── Pattern Matching ──────────────────────────────────────────
        for pattern, weight, category in cls.INJECTION_PATTERNS:
            matches = re.findall(pattern, prompt_text, re.IGNORECASE | re.DOTALL)
            if matches:
                max_score = max(max_score, weight)
                results["patterns_found"].append({
                    "category": category,
                    "weight": weight,
                    "match_count": len(matches),
                })

        # ── Entropy Analysis ──────────────────────────────────────────
        entropy = cls._calculate_entropy(prompt_text)
        if entropy > 5.5:
            results["details"].append({
                "check": "entropy_analysis",
                "value": round(entropy, 3),
                "threshold": 5.5,
                "status": "high_entropy",
            })
            max_score = max(max_score, min(0.5, (entropy - 5.5) / 2))

        # ── Length Anomaly ────────────────────────────────────────────
        if len(prompt_text) > 5000:
            anomaly_score = min(0.7, (len(prompt_text) - 5000) / 10000)
            results["details"].append({
                "check": "length_anomaly",
                "value": len(prompt_text),
                "threshold": 5000,
                "status": "excessive_length",
            })
            max_score = max(max_score, anomaly_score)

        # ── Special Character Density ─────────────────────────────────
        special_chars = sum(1 for c in prompt_text if not c.isalnum() and not c.isspace())
        density = special_chars / max(len(prompt_text), 1)
        if density > 0.3:
            results["details"].append({
                "check": "special_char_density",
                "value": round(density, 3),
                "threshold": 0.3,
                "status": "high_density",
            })
            max_score = max(max_score, min(0.6, density))

        # ── Nested Structure Detection ────────────────────────────────
        nested_braces = max(
            cls._count_max_nesting(prompt_text, "{", "}"),
            cls._count_max_nesting(prompt_text, "[", "]"),
            cls._count_max_nesting(prompt_text, "(", ")"),
        )
        if nested_braces > 5:
            results["details"].append({
                "check": "nesting_depth",
                "value": nested_braces,
                "threshold": 5,
                "status": "deep_nesting",
            })
            max_score = max(max_score, min(0.5, nested_braces / 15))

        # ── Final Scoring ─────────────────────────────────────────────
        results["injection_score"] = round(max_score, 3)
        results["is_suspicious"] = max_score >= 0.5

        return results

    @staticmethod
    def _calculate_entropy(text: str) -> float:
        """Calculate Shannon entropy of text."""
        if not text:
            return 0.0
        freq = Counter(text)
        length = len(text)
        return -sum(
            (count / length) * math.log2(count / length)
            for count in freq.values()
        )

    @staticmethod
    def _count_max_nesting(text: str, open_char: str, close_char: str) -> int:
        """Count maximum nesting depth of bracket pairs."""
        depth = 0
        max_depth = 0
        for char in text:
            if char == open_char:
                depth += 1
                max_depth = max(max_depth, depth)
            elif char == close_char:
                depth = max(0, depth - 1)
        return max_depth


# ==============================================================================
# TAMPER DETECTION
# ==============================================================================
class TamperDetector:
    """Detect response tampering and manipulation."""

    @staticmethod
    def compute_hash(data: str) -> str:
        """Compute SHA-256 hash for integrity verification."""
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    @staticmethod
    def verify_integrity(data: str, expected_hash: str) -> bool:
        """Verify data has not been tampered with."""
        actual_hash = hashlib.sha256(data.encode("utf-8")).hexdigest()
        return actual_hash == expected_hash

    @staticmethod
    def detect_score_anomaly(team_scores: list, new_score: float) -> bool:
        """
        Detect statistically improbable score jumps.
        Uses Z-score method: flag if new score is > 3 standard deviations.
        """
        if len(team_scores) < 3:
            return False

        mean = sum(team_scores) / len(team_scores)
        variance = sum((x - mean) ** 2 for x in team_scores) / len(team_scores)
        std_dev = math.sqrt(variance) if variance > 0 else 1

        z_score = abs(new_score - mean) / std_dev
        return z_score > 3.0


# ==============================================================================
# AUDIT LOGGER
# ==============================================================================
class AuditLogger:
    """Centralized audit logging for all system actions."""

    @staticmethod
    def log(action: str, description: str = None, resource_type: str = None,
            resource_id: str = None, severity: str = "info", user_id: str = None,
            team_id: str = None):
        """Create an audit log entry."""
        try:
            log_entry = AuditLog(
                user_id=user_id or getattr(g, "current_user_id", None),
                team_id=team_id or getattr(g, "current_team_id", None),
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                description=description,
                ip_address=request.remote_addr if request else None,
                user_agent=request.headers.get("User-Agent", "")[:500] if request else None,
                request_method=request.method if request else None,
                request_path=request.path if request else None,
                request_payload_hash=TamperDetector.compute_hash(
                    request.get_data(as_text=True)
                ) if request and request.data else None,
                severity=severity,
            )
            db.session.add(log_entry)
            db.session.commit()
            return log_entry
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Audit log failed: {e}")
            return None

    @staticmethod
    def log_security_event(event_type: str, description: str, severity: str = "medium",
                           team_id: str = None, user_id: str = None,
                           submission_id: str = None, evidence: dict = None):
        """Log a security-specific event."""
        try:
            event = SecurityEvent(
                team_id=team_id,
                user_id=user_id,
                submission_id=submission_id,
                event_type=event_type,
                severity=severity,
                description=description,
                evidence=json.dumps(evidence) if evidence else None,
                ip_address=request.remote_addr if request else None,
                user_agent=request.headers.get("User-Agent", "")[:500] if request else None,
            )
            db.session.add(event)
            db.session.commit()
            return event
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Security event log failed: {e}")
            return None


# ==============================================================================
# RBAC DECORATORS
# ==============================================================================
def require_role(*roles):
    """Decorator to enforce role-based access control."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask_login import current_user
            if not current_user.is_authenticated:
                abort(401, description="Authentication required")
            if current_user.role not in roles:
                AuditLogger.log(
                    action="unauthorized_access",
                    description=f"User {current_user.username} attempted to access {request.path} "
                                f"with role {current_user.role}, required: {roles}",
                    severity="warning",
                )
                abort(403, description="Insufficient permissions")
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_admin(f):
    """Shortcut decorator for admin-only routes."""
    return require_role("super_admin", "admin", "moderator")(f)


def require_team_access(f):
    """Decorator to ensure user has access to the requested team."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask_login import current_user
        if not current_user.is_authenticated:
            abort(401)
        # Admins can access any team
        if current_user.is_admin:
            return f(*args, **kwargs)
        # Team members can only access their own team
        team_id = kwargs.get("team_id") or request.view_args.get("team_id")
        if team_id:
            from models import TeamMember
            membership = TeamMember.query.filter_by(
                user_id=current_user.id,
                team_id=team_id,
                is_active=True
            ).first()
            if not membership:
                abort(403, description="You don't have access to this team")
        return f(*args, **kwargs)
    return decorated_function


# ==============================================================================
# REQUEST FINGERPRINTING
# ==============================================================================
class RequestFingerprint:
    """Generate fingerprints for request deduplication and tracking."""

    @staticmethod
    def generate(req=None):
        """Generate a unique fingerprint for the current request."""
        r = req or request
        components = [
            r.remote_addr or "",
            r.headers.get("User-Agent", ""),
            r.headers.get("Accept-Language", ""),
            r.headers.get("Accept-Encoding", ""),
        ]
        raw = "|".join(components)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
