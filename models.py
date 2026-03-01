# ==============================================================================
# AI INTELLIGENCE ZONE — Control Arena
# Database Models — Complete Schema
# ==============================================================================
# Tables: User, Team, TeamMember, Mission, Submission, AILog,
#          AuditLog, SecurityEvent, Achievement, ScoreOverride
# ==============================================================================

from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
import uuid
import json

db = SQLAlchemy()


def utcnow():
    return datetime.now(timezone.utc)


def generate_uuid():
    return str(uuid.uuid4())


# ==============================================================================
# USER MODEL — Admin and team member authentication
# ==============================================================================
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="team_member")
    # Roles: "super_admin", "admin", "moderator", "team_lead", "team_member"
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime(timezone=True))
    last_login_ip = db.Column(db.String(45))  # IPv6 compatible
    login_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    team_memberships = db.relationship("TeamMember", back_populates="user", lazy="dynamic")
    audit_logs = db.relationship("AuditLog", back_populates="user", lazy="dynamic")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method="pbkdf2:sha256:600000")

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role in ("super_admin", "admin", "moderator")

    def to_dict(self, include_sensitive=False):
        data = {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "login_count": self.login_count,
            "created_at": self.created_at.isoformat(),
        }
        if include_sensitive:
            data["last_login_ip"] = self.last_login_ip
        return data


# ==============================================================================
# TEAM MODEL — Competition team entity
# ==============================================================================
class Team(db.Model):
    __tablename__ = "teams"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    team_code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    # Human-readable code: e.g., "TEAM-ALPHA-01"
    name = db.Column(db.String(100), nullable=False)
    institution = db.Column(db.String(200))
    status = db.Column(db.String(20), nullable=False, default="active")
    # Statuses: "active", "locked", "disqualified", "inactive", "pending"
    disqualification_reason = db.Column(db.Text)
    avatar_color = db.Column(db.String(7), default="#3B82F6")  # Hex color

    # Scoring
    total_score = db.Column(db.Float, default=0.0)
    missions_completed = db.Column(db.Integer, default=0)
    total_submissions = db.Column(db.Integer, default=0)
    successful_validations = db.Column(db.Integer, default=0)
    failed_validations = db.Column(db.Integer, default=0)
    current_rank = db.Column(db.Integer)
    bonus_points = db.Column(db.Float, default=0.0)

    # Health Metrics
    error_rate = db.Column(db.Float, default=0.0)  # Percentage
    hallucination_count = db.Column(db.Integer, default=0)
    avg_response_time = db.Column(db.Float, default=0.0)  # Seconds
    health_score = db.Column(db.Float, default=100.0)  # 0-100

    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    last_activity_at = db.Column(db.DateTime(timezone=True))

    # Relationships
    members = db.relationship("TeamMember", back_populates="team", lazy="dynamic",
                              cascade="all, delete-orphan")
    submissions = db.relationship("Submission", back_populates="team", lazy="dynamic",
                                  cascade="all, delete-orphan")
    ai_logs = db.relationship("AILog", back_populates="team", lazy="dynamic",
                              cascade="all, delete-orphan")
    achievements = db.relationship("Achievement", back_populates="team", lazy="dynamic",
                                   cascade="all, delete-orphan")
    score_overrides = db.relationship("ScoreOverride", back_populates="team", lazy="dynamic")

    @property
    def validation_rate(self):
        if self.total_submissions == 0:
            return 0.0
        return (self.successful_validations / self.total_submissions) * 100

    @property
    def active_member_count(self):
        return self.members.filter_by(is_active=True).count()

    def to_dict(self, include_members=False):
        data = {
            "id": self.id,
            "team_code": self.team_code,
            "name": self.name,
            "institution": self.institution,
            "status": self.status,
            "avatar_color": self.avatar_color,
            "total_score": round(self.total_score, 2),
            "missions_completed": self.missions_completed,
            "total_submissions": self.total_submissions,
            "successful_validations": self.successful_validations,
            "failed_validations": self.failed_validations,
            "validation_rate": round(self.validation_rate, 1),
            "current_rank": self.current_rank,
            "bonus_points": round(self.bonus_points, 2),
            "error_rate": round(self.error_rate, 1),
            "hallucination_count": self.hallucination_count,
            "health_score": round(self.health_score, 1),
            "last_activity_at": self.last_activity_at.isoformat() if self.last_activity_at else None,
            "created_at": self.created_at.isoformat(),
        }
        if include_members:
            data["members"] = [m.to_dict() for m in self.members.all()]
        return data

    def to_leaderboard_dict(self):
        return {
            "rank": self.current_rank,
            "team_code": self.team_code,
            "name": self.name,
            "total_score": round(self.total_score, 2),
            "missions_completed": self.missions_completed,
            "validation_rate": round(self.validation_rate, 1),
            "bonus_points": round(self.bonus_points, 2),
            "total_submissions": self.total_submissions,
            "avatar_color": self.avatar_color,
            "status": self.status,
        }


# ==============================================================================
# TEAM MEMBER MODEL — Individual participants within a team
# ==============================================================================
class TeamMember(db.Model):
    __tablename__ = "team_members"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    team_id = db.Column(db.String(36), db.ForeignKey("teams.id"), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    role_in_team = db.Column(db.String(20), default="member")
    # Roles: "lead", "member"
    is_active = db.Column(db.Boolean, default=True)
    submissions_count = db.Column(db.Integer, default=0)
    participation_score = db.Column(db.Float, default=0.0)  # Track individual contribution
    joined_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    last_active_at = db.Column(db.DateTime(timezone=True))

    # Relationships
    team = db.relationship("Team", back_populates="members")
    user = db.relationship("User", back_populates="team_memberships")

    __table_args__ = (
        db.UniqueConstraint("team_id", "user_id", name="uq_team_user"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.user.username if self.user else None,
            "email": self.user.email if self.user else None,
            "role_in_team": self.role_in_team,
            "is_active": self.is_active,
            "submissions_count": self.submissions_count,
            "participation_score": round(self.participation_score, 1),
            "joined_at": self.joined_at.isoformat(),
            "last_active_at": self.last_active_at.isoformat() if self.last_active_at else None,
        }


# ==============================================================================
# MISSION MODEL — Competition challenges/tasks
# ==============================================================================
class Mission(db.Model):
    __tablename__ = "missions"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    mission_code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(20), default="medium")
    # Difficulties: "easy", "medium", "hard", "legendary"
    category = db.Column(db.String(50))
    max_points = db.Column(db.Float, nullable=False, default=100.0)
    time_limit_seconds = db.Column(db.Integer, default=600)  # 10 minutes default
    max_retries = db.Column(db.Integer, default=20)

    # Expected response schema (JSON string)
    expected_schema = db.Column(db.Text)  # JSON Schema for validation
    expected_fields = db.Column(db.Text)  # JSON list of required field names
    validation_regex = db.Column(db.Text)  # Optional regex patterns (JSON)
    sample_response = db.Column(db.Text)  # Example valid response

    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_visible = db.Column(db.Boolean, default=False)
    unlock_after_mission = db.Column(db.String(36))  # Sequential unlock
    order_index = db.Column(db.Integer, default=0)

    # Stats
    first_blood_team_id = db.Column(db.String(36))
    first_blood_at = db.Column(db.DateTime(timezone=True))
    total_attempts = db.Column(db.Integer, default=0)
    total_completions = db.Column(db.Integer, default=0)
    avg_completion_time = db.Column(db.Float, default=0.0)

    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    starts_at = db.Column(db.DateTime(timezone=True))
    ends_at = db.Column(db.DateTime(timezone=True))

    # Relationships
    submissions = db.relationship("Submission", back_populates="mission", lazy="dynamic")

    def get_schema(self):
        if self.expected_schema:
            return json.loads(self.expected_schema)
        return None

    def to_dict(self, include_schema=False):
        data = {
            "id": self.id,
            "mission_code": self.mission_code,
            "title": self.title,
            "description": self.description,
            "difficulty": self.difficulty,
            "category": self.category,
            "max_points": self.max_points,
            "time_limit_seconds": self.time_limit_seconds,
            "max_retries": self.max_retries,
            "is_active": self.is_active,
            "is_visible": self.is_visible,
            "order_index": self.order_index,
            "total_attempts": self.total_attempts,
            "total_completions": self.total_completions,
            "first_blood_team_id": self.first_blood_team_id,
        }
        if include_schema:
            data["expected_schema"] = self.get_schema()
            data["expected_fields"] = json.loads(self.expected_fields) if self.expected_fields else []
            data["sample_response"] = self.sample_response
        return data


# ==============================================================================
# SUBMISSION MODEL — Team submissions for missions
# ==============================================================================
class Submission(db.Model):
    __tablename__ = "submissions"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    team_id = db.Column(db.String(36), db.ForeignKey("teams.id"), nullable=False, index=True)
    mission_id = db.Column(db.String(36), db.ForeignKey("missions.id"), nullable=False, index=True)
    submitted_by = db.Column(db.String(36), db.ForeignKey("users.id"), index=True)
    attempt_number = db.Column(db.Integer, nullable=False, default=1)

    # Content
    prompt_text = db.Column(db.Text, nullable=False)
    ai_raw_response = db.Column(db.Text)
    parsed_response = db.Column(db.Text)  # JSON string of parsed data

    # Validation Results
    validation_status = db.Column(db.String(20), nullable=False, default="pending")
    # Statuses: "pending", "valid", "invalid", "error", "timeout", "rejected"
    json_valid = db.Column(db.Boolean)
    schema_valid = db.Column(db.Boolean)
    type_check_valid = db.Column(db.Boolean)
    regex_valid = db.Column(db.Boolean)
    field_count_valid = db.Column(db.Boolean)
    validation_errors = db.Column(db.Text)  # JSON list of error messages

    # Scoring
    accuracy_score = db.Column(db.Float, default=0.0)
    speed_score = db.Column(db.Float, default=0.0)
    validation_score = db.Column(db.Float, default=0.0)
    confidence_score = db.Column(db.Float, default=0.0)
    total_score = db.Column(db.Float, default=0.0)
    bonus_awarded = db.Column(db.Float, default=0.0)
    bonus_type = db.Column(db.String(50))

    # Metadata
    response_time_ms = db.Column(db.Integer)  # AI response time
    prompt_length = db.Column(db.Integer)
    response_length = db.Column(db.Integer)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))

    # Security Flags
    is_flagged = db.Column(db.Boolean, default=False)
    flag_reason = db.Column(db.String(200))
    injection_detected = db.Column(db.Boolean, default=False)
    is_hallucinated = db.Column(db.Boolean, default=False)

    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    validated_at = db.Column(db.DateTime(timezone=True))

    # Relationships
    team = db.relationship("Team", back_populates="submissions")
    mission = db.relationship("Mission", back_populates="submissions")

    __table_args__ = (
        db.Index("idx_team_mission", "team_id", "mission_id"),
        db.Index("idx_created_at", "created_at"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "team_id": self.team_id,
            "mission_id": self.mission_id,
            "attempt_number": self.attempt_number,
            "prompt_text": self.prompt_text,
            "ai_raw_response": self.ai_raw_response,
            "validation_status": self.validation_status,
            "json_valid": self.json_valid,
            "schema_valid": self.schema_valid,
            "type_check_valid": self.type_check_valid,
            "regex_valid": self.regex_valid,
            "field_count_valid": self.field_count_valid,
            "validation_errors": json.loads(self.validation_errors) if self.validation_errors else [],
            "accuracy_score": round(self.accuracy_score, 2),
            "speed_score": round(self.speed_score, 2),
            "confidence_score": round(self.confidence_score, 2),
            "total_score": round(self.total_score, 2),
            "bonus_awarded": round(self.bonus_awarded, 2),
            "bonus_type": self.bonus_type,
            "response_time_ms": self.response_time_ms,
            "is_flagged": self.is_flagged,
            "flag_reason": self.flag_reason,
            "injection_detected": self.injection_detected,
            "created_at": self.created_at.isoformat(),
        }


# ==============================================================================
# AI LOG MODEL — Complete audit of AI interactions
# ==============================================================================
class AILog(db.Model):
    __tablename__ = "ai_logs"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    team_id = db.Column(db.String(36), db.ForeignKey("teams.id"), nullable=False, index=True)
    submission_id = db.Column(db.String(36), db.ForeignKey("submissions.id"), index=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), index=True)

    # Full Prompt/Response Chain
    prompt_text = db.Column(db.Text, nullable=False)
    system_prompt_used = db.Column(db.Text)
    ai_model_used = db.Column(db.String(50))
    ai_raw_output = db.Column(db.Text)
    ai_parsed_output = db.Column(db.Text)

    # Validation Pipeline Results
    parse_result = db.Column(db.String(20))  # "success", "partial", "failed"
    validation_result = db.Column(db.String(20))  # "pass", "fail", "error"
    error_details = db.Column(db.Text)  # JSON
    rejected = db.Column(db.Boolean, default=False)
    rejection_reason = db.Column(db.String(500))
    retry_attempt = db.Column(db.Integer, default=0)

    # Analysis Metrics
    token_count_prompt = db.Column(db.Integer)
    token_count_response = db.Column(db.Integer)
    response_latency_ms = db.Column(db.Integer)
    confidence_score = db.Column(db.Float)
    hallucination_probability = db.Column(db.Float, default=0.0)

    # Security
    injection_score = db.Column(db.Float, default=0.0)  # 0.0 = clean, 1.0 = definite injection
    suspicious_patterns = db.Column(db.Text)  # JSON list of detected patterns
    ip_address = db.Column(db.String(45))

    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    # Relationships
    team = db.relationship("Team", back_populates="ai_logs")

    __table_args__ = (
        db.Index("idx_ailog_team_created", "team_id", "created_at"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "team_id": self.team_id,
            "submission_id": self.submission_id,
            "prompt_text": self.prompt_text,
            "ai_model_used": self.ai_model_used,
            "ai_raw_output": self.ai_raw_output,
            "parse_result": self.parse_result,
            "validation_result": self.validation_result,
            "error_details": json.loads(self.error_details) if self.error_details else None,
            "rejected": self.rejected,
            "rejection_reason": self.rejection_reason,
            "retry_attempt": self.retry_attempt,
            "confidence_score": self.confidence_score,
            "hallucination_probability": self.hallucination_probability,
            "injection_score": self.injection_score,
            "response_latency_ms": self.response_latency_ms,
            "created_at": self.created_at.isoformat(),
        }


# ==============================================================================
# AUDIT LOG MODEL — System-wide action audit trail
# ==============================================================================
class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), index=True)
    team_id = db.Column(db.String(36), index=True)

    # Action Details
    action = db.Column(db.String(100), nullable=False, index=True)
    # Actions: "login", "logout", "submit", "validate", "score_override",
    #          "team_lock", "team_disqualify", "mission_create", "export", etc.
    resource_type = db.Column(db.String(50))  # "team", "submission", "mission", "user"
    resource_id = db.Column(db.String(36))
    description = db.Column(db.Text)

    # Request Context
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    request_method = db.Column(db.String(10))
    request_path = db.Column(db.String(500))
    request_payload_hash = db.Column(db.String(64))  # SHA-256 of request body
    response_status = db.Column(db.Integer)

    # Severity
    severity = db.Column(db.String(20), default="info")
    # Severities: "debug", "info", "warning", "critical", "alert"

    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, index=True)

    # Relationships
    user = db.relationship("User", back_populates="audit_logs")

    __table_args__ = (
        db.Index("idx_audit_action_time", "action", "created_at"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "team_id": self.team_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "description": self.description,
            "ip_address": self.ip_address,
            "severity": self.severity,
            "response_status": self.response_status,
            "created_at": self.created_at.isoformat(),
        }


# ==============================================================================
# SECURITY EVENT MODEL — Security-specific incidents
# ==============================================================================
class SecurityEvent(db.Model):
    __tablename__ = "security_events"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    team_id = db.Column(db.String(36), index=True)
    user_id = db.Column(db.String(36), index=True)
    submission_id = db.Column(db.String(36))

    # Event Details
    event_type = db.Column(db.String(50), nullable=False, index=True)
    # Types: "injection_attempt", "rate_limit_exceeded", "suspicious_pattern",
    #        "unauthorized_access", "tampering_detected", "brute_force",
    #        "session_hijack", "anomaly_detected"
    severity = db.Column(db.String(20), nullable=False, default="medium")
    # Severities: "low", "medium", "high", "critical"
    description = db.Column(db.Text, nullable=False)
    evidence = db.Column(db.Text)  # JSON with detailed evidence
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))

    # Resolution
    status = db.Column(db.String(20), default="open")
    # Statuses: "open", "investigating", "resolved", "false_positive"
    resolved_by = db.Column(db.String(36))
    resolved_at = db.Column(db.DateTime(timezone=True))
    resolution_notes = db.Column(db.Text)

    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "team_id": self.team_id,
            "user_id": self.user_id,
            "event_type": self.event_type,
            "severity": self.severity,
            "description": self.description,
            "evidence": json.loads(self.evidence) if self.evidence else None,
            "ip_address": self.ip_address,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


# ==============================================================================
# ACHIEVEMENT MODEL — Gamification badges/achievements
# ==============================================================================
class Achievement(db.Model):
    __tablename__ = "achievements"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    team_id = db.Column(db.String(36), db.ForeignKey("teams.id"), nullable=False, index=True)
    achievement_type = db.Column(db.String(50), nullable=False)
    # Types: "first_blood", "perfect_parse", "speed_demon", "consistency",
    #        "zero_error", "comeback_king", "json_ninja", "innovation"
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500))
    icon = db.Column(db.String(10))  # Emoji icon
    points_awarded = db.Column(db.Float, default=0.0)
    mission_id = db.Column(db.String(36))
    awarded_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    # Relationships
    team = db.relationship("Team", back_populates="achievements")

    def to_dict(self):
        return {
            "id": self.id,
            "team_id": self.team_id,
            "achievement_type": self.achievement_type,
            "title": self.title,
            "description": self.description,
            "icon": self.icon,
            "points_awarded": self.points_awarded,
            "awarded_at": self.awarded_at.isoformat(),
        }


# ==============================================================================
# SCORE OVERRIDE MODEL — Admin manual score adjustments
# ==============================================================================
class ScoreOverride(db.Model):
    __tablename__ = "score_overrides"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    team_id = db.Column(db.String(36), db.ForeignKey("teams.id"), nullable=False, index=True)
    admin_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    mission_id = db.Column(db.String(36))

    # Override Details
    previous_score = db.Column(db.Float, nullable=False)
    new_score = db.Column(db.Float, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    override_type = db.Column(db.String(20), nullable=False)
    # Types: "bonus", "penalty", "correction", "disqualification"

    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    # Relationships
    team = db.relationship("Team", back_populates="score_overrides")

    def to_dict(self):
        return {
            "id": self.id,
            "team_id": self.team_id,
            "admin_id": self.admin_id,
            "previous_score": self.previous_score,
            "new_score": self.new_score,
            "reason": self.reason,
            "override_type": self.override_type,
            "created_at": self.created_at.isoformat(),
        }
