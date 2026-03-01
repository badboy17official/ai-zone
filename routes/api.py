# ==============================================================================
# AI INTELLIGENCE ZONE — Control Arena
# API Routes — RESTful endpoints for Team Portal & integrations
# ==============================================================================
# Route Map:
#   POST   /api/submit                  — Submit a prompt for a mission
#   GET    /api/leaderboard             — Get current leaderboard
#   GET    /api/team/<id>               — Get team details
#   GET    /api/team/<id>/submissions   — Get team's submissions
#   GET    /api/missions                — List available missions
#   GET    /api/missions/<id>           — Get mission details
#   GET    /api/health                  — System health check
# ==============================================================================

import json
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, current_app, g

from models import db, Team, Mission, Submission, AILog, TeamMember
from validation_engine import ValidationEngine, HallucinationDetector
from scoring_engine import ScoringEngine
from security import InjectionDetector, AuditLogger, TamperDetector
from routes.auth import jwt_required

api_bp = Blueprint("api", __name__)


# ==============================================================================
# HEALTH CHECK
# ==============================================================================

@api_bp.route("/health", methods=["GET"])
def health_check():
    """System health check endpoint."""
    try:
        # Test database connection
        db.session.execute(db.text("SELECT 1"))
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    return jsonify({
        "status": "operational" if db_status == "healthy" else "degraded",
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "2.0.0",
    })


# ==============================================================================
# SUBMISSION ENDPOINT — Core competition interaction
# ==============================================================================

@api_bp.route("/submit", methods=["POST"])
@jwt_required
def submit_prompt():
    """
    Submit a prompt for AI processing and validation.

    Expected JSON body:
    {
        "team_id": "...",
        "mission_id": "...",
        "prompt_text": "...",
        "ai_response": "..."   // The AI-generated response to validate
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON request body required"}), 400

    # ── Extract Fields ────────────────────────────────────────────────
    team_id = data.get("team_id")
    mission_id = data.get("mission_id")
    prompt_text = data.get("prompt_text", "").strip()
    ai_response = data.get("ai_response", "").strip()

    # ── Basic Validation ──────────────────────────────────────────────
    if not all([team_id, mission_id, prompt_text, ai_response]):
        return jsonify({"error": "Missing required fields: team_id, mission_id, prompt_text, ai_response"}), 400

    # ── Verify Team ───────────────────────────────────────────────────
    team = Team.query.get(team_id)
    if not team:
        return jsonify({"error": "Team not found"}), 404
    if team.status != "active":
        return jsonify({"error": f"Team is {team.status}. Cannot submit."}), 403

    # ── Verify Mission ────────────────────────────────────────────────
    mission = Mission.query.get(mission_id)
    if not mission:
        return jsonify({"error": "Mission not found"}), 404
    if not mission.is_active or not mission.is_visible:
        return jsonify({"error": "Mission is not currently available"}), 403

    # ── Check Retry Limit ─────────────────────────────────────────────
    attempt_count = Submission.query.filter_by(
        team_id=team_id, mission_id=mission_id
    ).count()

    max_retries = mission.max_retries or current_app.config.get("MAX_RETRIES_PER_MISSION", 20)
    if attempt_count >= max_retries:
        return jsonify({
            "error": f"Maximum retries ({max_retries}) reached for this mission",
            "attempts_used": attempt_count,
        }), 429

    # ── Security: Injection Detection ─────────────────────────────────
    injection_result = InjectionDetector.analyze(prompt_text)
    is_injection = injection_result["is_suspicious"]

    if is_injection:
        AuditLogger.log_security_event(
            event_type="injection_attempt",
            description=f"Prompt injection detected from team {team.team_code}",
            severity="high" if injection_result["injection_score"] > 0.8 else "medium",
            team_id=team_id,
            user_id=getattr(g, "current_user_id", None),
            evidence=injection_result,
        )

        # If high confidence injection, reject outright
        if injection_result["injection_score"] > 0.9:
            return jsonify({
                "error": "Submission rejected: suspicious content detected",
                "submission_id": None,
                "flagged": True,
            }), 403

    # ── Run Validation Engine ─────────────────────────────────────────
    schema = mission.get_schema()
    expected_fields = json.loads(mission.expected_fields) if mission.expected_fields else None
    regex_patterns = json.loads(mission.validation_regex) if mission.validation_regex else None

    validation = ValidationEngine.validate(
        raw_response=ai_response,
        schema=schema,
        expected_fields=expected_fields,
        regex_patterns=regex_patterns,
        strict_mode=True,
    )

    # ── Hallucination Detection ───────────────────────────────────────
    hallucination_prob = HallucinationDetector.estimate_probability(
        prompt_text, ai_response, validation.parsed_data
    )

    # ── Create Submission Record ──────────────────────────────────────
    submission = Submission(
        team_id=team_id,
        mission_id=mission_id,
        submitted_by=getattr(g, "current_user_id", None),
        attempt_number=attempt_count + 1,
        prompt_text=prompt_text,
        ai_raw_response=ai_response,
        parsed_response=json.dumps(validation.parsed_data) if validation.parsed_data else None,
        validation_status=validation.overall_status,
        json_valid=validation.json_valid,
        schema_valid=validation.schema_valid,
        type_check_valid=validation.type_check_valid,
        regex_valid=validation.regex_valid,
        field_count_valid=validation.field_count_valid,
        validation_errors=json.dumps(validation.errors),
        confidence_score=validation.confidence_score,
        prompt_length=len(prompt_text),
        response_length=len(ai_response),
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent", "")[:500],
        is_flagged=is_injection,
        flag_reason="Injection patterns detected" if is_injection else None,
        injection_detected=is_injection,
        is_hallucinated=hallucination_prob > 0.7,
        response_time_ms=data.get("response_time_ms"),
    )

    # ── Calculate Score ───────────────────────────────────────────────
    if validation.overall_status == "valid":
        score_result = ScoringEngine.calculate_mission_score(submission, mission, team)
        submission.accuracy_score = score_result["accuracy_score"]
        submission.speed_score = score_result["speed_score"]
        submission.validation_score = score_result["validation_score"]
        submission.total_score = score_result["final_score"]

        # Update team stats
        team.successful_validations += 1
        team.missions_completed = Submission.query.filter_by(
            team_id=team_id, validation_status="valid"
        ).distinct(Submission.mission_id).count()
        team.total_score += score_result["final_score"]

        # Check for bonuses
        bonuses = ScoringEngine.check_and_award_bonuses(submission, mission, team)
        if bonuses:
            submission.bonus_awarded = sum(b.get("points", 0) for b in bonuses)
            submission.bonus_type = ", ".join(b.get("type", "") for b in bonuses)

        # Update mission stats
        mission.total_completions += 1
    else:
        score_result = {"final_score": 0}
        team.failed_validations += 1

    # ── Update Team Metrics ───────────────────────────────────────────
    team.total_submissions += 1
    team.last_activity_at = datetime.now(timezone.utc)
    team.error_rate = (team.failed_validations / team.total_submissions) * 100
    if hallucination_prob > 0.7:
        team.hallucination_count += 1
    team.health_score = ScoringEngine.calculate_health_score(team)

    # Update mission stats
    mission.total_attempts += 1

    # ── Create AI Log ─────────────────────────────────────────────────
    ai_log = AILog(
        team_id=team_id,
        submission_id=submission.id,
        user_id=getattr(g, "current_user_id", None),
        prompt_text=prompt_text,
        ai_raw_output=ai_response,
        ai_parsed_output=json.dumps(validation.parsed_data) if validation.parsed_data else None,
        parse_result="success" if validation.json_valid else "failed",
        validation_result="pass" if validation.is_valid else "fail",
        error_details=json.dumps(validation.errors) if validation.errors else None,
        rejected=is_injection and injection_result["injection_score"] > 0.9,
        retry_attempt=attempt_count,
        confidence_score=validation.confidence_score,
        hallucination_probability=hallucination_prob,
        injection_score=injection_result["injection_score"],
        suspicious_patterns=json.dumps(injection_result["patterns_found"]) if injection_result["patterns_found"] else None,
        ip_address=request.remote_addr,
        response_latency_ms=data.get("response_time_ms"),
    )

    # ── Persist ───────────────────────────────────────────────────────
    db.session.add(submission)
    db.session.add(ai_log)
    db.session.commit()

    # ── Recalculate Rankings ──────────────────────────────────────────
    if validation.overall_status == "valid":
        ScoringEngine.recalculate_rankings()

    # ── Audit Log ─────────────────────────────────────────────────────
    AuditLogger.log(
        action="submission_created",
        description=f"Team {team.team_code} submitted for mission {mission.mission_code} "
                    f"(attempt #{attempt_count + 1}, status: {validation.overall_status})",
        resource_type="submission",
        resource_id=submission.id,
        team_id=team_id,
    )

    # ── Response ──────────────────────────────────────────────────────
    return jsonify({
        "submission_id": submission.id,
        "status": validation.overall_status,
        "attempt_number": attempt_count + 1,
        "attempts_remaining": max_retries - (attempt_count + 1),
        "validation": validation.to_dict(),
        "score": {
            "total": round(submission.total_score, 2),
            "accuracy": round(submission.accuracy_score, 2),
            "speed": round(submission.speed_score, 2),
            "confidence": round(submission.confidence_score, 4),
            "bonus": round(submission.bonus_awarded, 2),
        },
        "security": {
            "flagged": is_injection,
            "injection_score": round(injection_result["injection_score"], 3),
            "hallucination_probability": round(hallucination_prob, 3),
        },
        "team_stats": {
            "total_score": round(team.total_score, 2),
            "rank": team.current_rank,
            "health_score": round(team.health_score, 1),
        },
    }), 201


# ==============================================================================
# LEADERBOARD
# ==============================================================================

@api_bp.route("/leaderboard", methods=["GET"])
def get_leaderboard():
    """
    Get the current leaderboard rankings.

    Query params:
        sort_by: "score" (default), "accuracy", "speed", "validation_rate"
        limit: Number of teams to return (default: 50)
    """
    sort_by = request.args.get("sort_by", "score")
    limit = min(int(request.args.get("limit", 50)), 100)

    query = Team.query.filter(Team.status.in_(["active", "locked"]))

    if sort_by == "accuracy":
        # Sort by validation rate
        query = query.order_by(
            db.case((Team.total_submissions > 0,
                     Team.successful_validations * 100.0 / Team.total_submissions),
                    else_=0).desc()
        )
    elif sort_by == "speed":
        query = query.order_by(Team.avg_response_time.asc())
    elif sort_by == "validation_rate":
        query = query.order_by(
            db.case((Team.total_submissions > 0,
                     Team.successful_validations * 100.0 / Team.total_submissions),
                    else_=0).desc()
        )
    else:
        query = query.order_by(Team.current_rank.asc().nullslast())

    teams = query.limit(limit).all()

    return jsonify({
        "leaderboard": [t.to_leaderboard_dict() for t in teams],
        "total_teams": Team.query.filter_by(status="active").count(),
        "sort_by": sort_by,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })


# ==============================================================================
# TEAM ENDPOINTS
# ==============================================================================

@api_bp.route("/team/<team_id>", methods=["GET"])
@jwt_required
def get_team(team_id):
    """Get detailed team information."""
    team = Team.query.get_or_404(team_id)
    return jsonify({"team": team.to_dict(include_members=True)})


@api_bp.route("/team/<team_id>/submissions", methods=["GET"])
@jwt_required
def get_team_submissions(team_id):
    """Get all submissions for a team."""
    team = Team.query.get_or_404(team_id)

    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)
    mission_id = request.args.get("mission_id")

    query = Submission.query.filter_by(team_id=team_id)
    if mission_id:
        query = query.filter_by(mission_id=mission_id)

    query = query.order_by(Submission.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "submissions": [s.to_dict() for s in pagination.items],
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
        "pages": pagination.pages,
    })


@api_bp.route("/team/<team_id>/achievements", methods=["GET"])
@jwt_required
def get_team_achievements(team_id):
    """Get all achievements for a team."""
    from models import Achievement
    team = Team.query.get_or_404(team_id)
    achievements = Achievement.query.filter_by(team_id=team_id).order_by(
        Achievement.awarded_at.desc()
    ).all()
    return jsonify({
        "achievements": [a.to_dict() for a in achievements],
        "total_bonus": round(team.bonus_points, 2),
    })


# ==============================================================================
# MISSION ENDPOINTS
# ==============================================================================

@api_bp.route("/missions", methods=["GET"])
@jwt_required
def list_missions():
    """List all visible missions."""
    missions = Mission.query.filter_by(
        is_active=True, is_visible=True
    ).order_by(Mission.order_index.asc()).all()

    return jsonify({
        "missions": [m.to_dict() for m in missions],
        "total": len(missions),
    })


@api_bp.route("/missions/<mission_id>", methods=["GET"])
@jwt_required
def get_mission(mission_id):
    """Get detailed mission information."""
    mission = Mission.query.get_or_404(mission_id)
    return jsonify({"mission": mission.to_dict(include_schema=True)})
