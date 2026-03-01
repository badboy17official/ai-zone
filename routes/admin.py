# ==============================================================================
# AI INTELLIGENCE ZONE — Control Arena
# Admin Panel Routes — Dashboard, Team Mgmt, Monitoring, Logs
# ==============================================================================
# Route Map:
#   GET    /admin/                    — Main dashboard
#   GET    /admin/teams               — Team management
#   POST   /admin/teams/create        — Create team
#   POST   /admin/teams/<id>/lock     — Lock/unlock team
#   POST   /admin/teams/<id>/dq       — Disqualify team
#   POST   /admin/teams/<id>/override — Score override
#   GET    /admin/activity            — Activity monitor
#   GET    /admin/logs                — AI logs viewer
#   GET    /admin/leaderboard         — Leaderboard management
#   GET    /admin/security            — Security events
#   GET    /admin/audit               — Audit trail
#   GET    /admin/missions            — Mission management
#   POST   /admin/missions/create     — Create mission
# ==============================================================================

import json
from datetime import datetime, timezone, timedelta

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user

from models import (db, User, Team, TeamMember, Mission, Submission,
                    AILog, AuditLog, SecurityEvent, Achievement, ScoreOverride)
from security import require_admin, AuditLogger
from scoring_engine import ScoringEngine

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ==============================================================================
# DASHBOARD — Real-time overview
# ==============================================================================

@admin_bp.route("/")
@login_required
@require_admin
def dashboard():
    """Main admin dashboard with real-time stats."""
    # Team statistics
    total_teams = Team.query.count()
    active_teams = Team.query.filter_by(status="active").count()
    locked_teams = Team.query.filter_by(status="locked").count()
    disqualified_teams = Team.query.filter_by(status="disqualified").count()

    # Submission statistics
    total_submissions = Submission.query.count()
    valid_submissions = Submission.query.filter_by(validation_status="valid").count()
    invalid_submissions = Submission.query.filter_by(validation_status="invalid").count()
    error_submissions = Submission.query.filter_by(validation_status="error").count()

    # Recent activity (last hour)
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    recent_submissions = Submission.query.filter(
        Submission.created_at >= one_hour_ago
    ).count()

    # Security stats
    open_security_events = SecurityEvent.query.filter_by(status="open").count()
    flagged_submissions = Submission.query.filter_by(is_flagged=True).count()

    # Top teams
    top_teams = Team.query.filter_by(status="active").order_by(
        Team.current_rank.asc().nullslast()
    ).limit(10).all()

    # Recent submissions
    recent_subs = Submission.query.order_by(
        Submission.created_at.desc()
    ).limit(15).all()

    # Validation rate
    validation_rate = (valid_submissions / total_submissions * 100) if total_submissions > 0 else 0

    return render_template("admin/dashboard.html",
        total_teams=total_teams,
        active_teams=active_teams,
        locked_teams=locked_teams,
        disqualified_teams=disqualified_teams,
        total_submissions=total_submissions,
        valid_submissions=valid_submissions,
        invalid_submissions=invalid_submissions,
        error_submissions=error_submissions,
        recent_submissions=recent_submissions,
        validation_rate=round(validation_rate, 1),
        open_security_events=open_security_events,
        flagged_submissions=flagged_submissions,
        top_teams=top_teams,
        recent_subs=recent_subs,
    )


# ==============================================================================
# TEAM MANAGEMENT
# ==============================================================================

@admin_bp.route("/teams")
@login_required
@require_admin
def teams():
    """Team management page."""
    status_filter = request.args.get("status", "all")
    search = request.args.get("search", "").strip()

    query = Team.query
    if status_filter != "all":
        query = query.filter_by(status=status_filter)
    if search:
        query = query.filter(
            db.or_(
                Team.name.ilike(f"%{search}%"),
                Team.team_code.ilike(f"%{search}%"),
            )
        )

    teams_list = query.order_by(Team.created_at.desc()).all()
    return render_template("admin/teams.html", teams=teams_list,
                         status_filter=status_filter, search=search)


@admin_bp.route("/teams/create", methods=["POST"])
@login_required
@require_admin
def create_team():
    """Create a new team."""
    team_code = request.form.get("team_code", "").strip().upper()
    name = request.form.get("name", "").strip()
    institution = request.form.get("institution", "").strip()

    if not team_code or not name:
        flash("Team code and name are required.", "danger")
        return redirect(url_for("admin.teams"))

    # Check for duplicate
    if Team.query.filter_by(team_code=team_code).first():
        flash(f"Team code '{team_code}' already exists.", "danger")
        return redirect(url_for("admin.teams"))

    team = Team(
        team_code=team_code,
        name=name,
        institution=institution,
        status="active",
    )
    db.session.add(team)
    db.session.commit()

    AuditLogger.log("team_created", f"Team created: {team_code} - {name}",
                   resource_type="team", resource_id=team.id)
    flash(f"Team '{name}' ({team_code}) created successfully!", "success")
    return redirect(url_for("admin.teams"))


@admin_bp.route("/teams/<team_id>/add_member", methods=["POST"])
@login_required
@require_admin
def add_team_member(team_id):
    """Add a member to a team."""
    team = Team.query.get_or_404(team_id)
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()
    role_in_team = request.form.get("role_in_team", "member")

    if not username or not email or not password:
        flash("Username, email, and password are required.", "danger")
        return redirect(url_for("admin.teams"))

    # Create user if doesn't exist
    user = User.query.filter_by(username=username).first()
    if not user:
        user = User(username=username, email=email, role="team_member")
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

    # Check if already a member
    existing = TeamMember.query.filter_by(team_id=team_id, user_id=user.id).first()
    if existing:
        flash(f"User '{username}' is already a member of this team.", "warning")
        return redirect(url_for("admin.teams"))

    member = TeamMember(
        team_id=team_id,
        user_id=user.id,
        role_in_team=role_in_team,
    )
    db.session.add(member)
    db.session.commit()

    AuditLogger.log("member_added", f"Member {username} added to team {team.team_code}",
                   resource_type="team_member", resource_id=member.id, team_id=team_id)
    flash(f"Member '{username}' added to team '{team.name}'.", "success")
    return redirect(url_for("admin.teams"))


@admin_bp.route("/teams/<team_id>/lock", methods=["POST"])
@login_required
@require_admin
def toggle_team_lock(team_id):
    """Lock or unlock a team."""
    team = Team.query.get_or_404(team_id)

    if team.status == "locked":
        team.status = "active"
        action = "team_unlocked"
        msg = f"Team '{team.name}' has been unlocked."
    else:
        team.status = "locked"
        action = "team_locked"
        msg = f"Team '{team.name}' has been locked."

    db.session.commit()
    AuditLogger.log(action, msg, resource_type="team", resource_id=team_id,
                   team_id=team_id, severity="warning")
    flash(msg, "warning")
    return redirect(url_for("admin.teams"))


@admin_bp.route("/teams/<team_id>/disqualify", methods=["POST"])
@login_required
@require_admin
def disqualify_team(team_id):
    """Disqualify a team."""
    team = Team.query.get_or_404(team_id)
    reason = request.form.get("reason", "Admin decision")

    team.status = "disqualified"
    team.disqualification_reason = reason
    db.session.commit()

    AuditLogger.log("team_disqualified",
                   f"Team '{team.name}' disqualified. Reason: {reason}",
                   resource_type="team", resource_id=team_id,
                   team_id=team_id, severity="critical")
    flash(f"Team '{team.name}' has been disqualified.", "danger")
    return redirect(url_for("admin.teams"))


@admin_bp.route("/teams/<team_id>/override", methods=["POST"])
@login_required
@require_admin
def score_override(team_id):
    """Manual score override for a team."""
    team = Team.query.get_or_404(team_id)
    new_score = float(request.form.get("new_score", 0))
    reason = request.form.get("reason", "").strip()
    override_type = request.form.get("override_type", "correction")

    if not reason:
        flash("A reason is required for score overrides.", "danger")
        return redirect(url_for("admin.teams"))

    override = ScoreOverride(
        team_id=team_id,
        admin_id=current_user.id,
        previous_score=team.total_score,
        new_score=new_score,
        reason=reason,
        override_type=override_type,
    )
    db.session.add(override)

    team.total_score = new_score
    db.session.commit()

    # Recalculate rankings
    ScoringEngine.recalculate_rankings()

    AuditLogger.log("score_override",
                   f"Score override for team '{team.name}': "
                   f"{override.previous_score} → {new_score}. Reason: {reason}",
                   resource_type="team", resource_id=team_id,
                   team_id=team_id, severity="critical")
    flash(f"Score updated for '{team.name}': {new_score}", "warning")
    return redirect(url_for("admin.teams"))


# ==============================================================================
# ACTIVITY MONITOR
# ==============================================================================

@admin_bp.route("/activity")
@login_required
@require_admin
def activity_monitor():
    """Real-time activity monitoring page."""
    # Recent submissions with team info
    recent = db.session.query(Submission, Team).join(
        Team, Submission.team_id == Team.id
    ).order_by(Submission.created_at.desc()).limit(50).all()

    # Submission frequency per team (last hour)
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    frequency = db.session.query(
        Team.team_code,
        Team.name,
        db.func.count(Submission.id).label("count")
    ).join(Team, Submission.team_id == Team.id).filter(
        Submission.created_at >= one_hour_ago
    ).group_by(Team.team_code, Team.name).order_by(
        db.func.count(Submission.id).desc()
    ).all()

    # Flagged submissions
    flagged = Submission.query.filter_by(is_flagged=True).order_by(
        Submission.created_at.desc()
    ).limit(20).all()

    # Hallucination stats per team
    hallucination_data = db.session.query(
        Team.team_code,
        Team.name,
        Team.hallucination_count,
        Team.total_submissions,
    ).filter(Team.hallucination_count > 0).order_by(
        Team.hallucination_count.desc()
    ).all()

    return render_template("admin/activity.html",
        recent=recent,
        frequency=frequency,
        flagged=flagged,
        hallucination_data=hallucination_data,
    )


# ==============================================================================
# AI LOGS VIEWER
# ==============================================================================

@admin_bp.route("/logs")
@login_required
@require_admin
def ai_logs():
    """AI interaction logs viewer."""
    page = int(request.args.get("page", 1))
    per_page = 25
    team_filter = request.args.get("team_id")
    mission_filter = request.args.get("mission_id")
    status_filter = request.args.get("status")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    flagged_only = request.args.get("flagged") == "1"

    query = db.session.query(AILog, Team).join(Team, AILog.team_id == Team.id)

    if team_filter:
        query = query.filter(AILog.team_id == team_filter)
    if mission_filter:
        query = query.join(Submission, AILog.submission_id == Submission.id).filter(
            Submission.mission_id == mission_filter
        )
    if status_filter:
        query = query.filter(AILog.validation_result == status_filter)
    if flagged_only:
        query = query.filter(AILog.injection_score > 0.5)
    if date_from:
        try:
            start_dt = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            query = query.filter(AILog.created_at >= start_dt)
        except ValueError:
            pass
    if date_to:
        try:
            end_dt = datetime.strptime(date_to, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
            query = query.filter(AILog.created_at <= end_dt)
        except ValueError:
            pass

    pagination = query.order_by(AILog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    teams_list = Team.query.order_by(Team.team_code).all()
    missions_list = Mission.query.filter_by(is_active=True).order_by(Mission.order_index.asc()).all()

    return render_template("admin/logs.html",
        logs=pagination.items,
        pagination=pagination,
        teams=teams_list,
        missions=missions_list,
        team_filter=team_filter,
        mission_filter=mission_filter,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
        flagged_only=flagged_only,
    )


@admin_bp.route("/api/logs/<log_id>")
@login_required
@require_admin
def api_log_detail(log_id):
    """Return detailed AI log payload for lazy-render modal."""
    log = AILog.query.get_or_404(log_id)
    team = Team.query.get(log.team_id)
    mission_title = None

    if log.submission_id:
        submission = Submission.query.get(log.submission_id)
        mission_title = submission.mission.title if submission and submission.mission else None

    return jsonify({
        "id": log.id,
        "team_code": team.team_code if team else "N/A",
        "mission_title": mission_title,
        "created_at": log.created_at.isoformat() if log.created_at else None,
        "prompt_text": (log.prompt_text or "")[:10000],
        "ai_raw_output": (log.ai_raw_output or "")[:20000],
        "ai_parsed_output": (log.ai_parsed_output or "")[:15000],
        "parse_result": log.parse_result,
        "validation_result": log.validation_result,
        "confidence_score": log.confidence_score or 0,
        "hallucination_probability": log.hallucination_probability or 0,
        "injection_score": log.injection_score or 0,
        "rejected": log.rejected,
        "rejection_reason": log.rejection_reason,
        "error_details": (log.error_details or "")[:10000],
        "retry_attempt": log.retry_attempt,
        "ip_address": log.ip_address,
    })


# ==============================================================================
# LEADERBOARD MANAGEMENT
# ==============================================================================

@admin_bp.route("/leaderboard")
@login_required
@require_admin
def leaderboard():
    """Leaderboard management and display."""
    teams_list = Team.query.filter(
        Team.status.in_(["active", "locked"])
    ).order_by(Team.current_rank.asc().nullslast()).all()

    return render_template("admin/leaderboard.html", teams=teams_list)


@admin_bp.route("/leaderboard/recalculate", methods=["POST"])
@login_required
@require_admin
def recalculate_leaderboard():
    """Force recalculate all rankings."""
    rankings = ScoringEngine.recalculate_rankings()
    AuditLogger.log("leaderboard_recalculated",
                   f"Admin forced leaderboard recalculation. {len(rankings)} teams ranked.",
                   severity="info")
    flash(f"Leaderboard recalculated. {len(rankings)} teams ranked.", "success")
    return redirect(url_for("admin.leaderboard"))


# ==============================================================================
# SECURITY EVENTS
# ==============================================================================

@admin_bp.route("/security")
@login_required
@require_admin
def security():
    """Security events dashboard."""
    page = int(request.args.get("page", 1))
    severity_filter = request.args.get("severity")
    status_filter = request.args.get("status")

    query = SecurityEvent.query
    if severity_filter:
        query = query.filter_by(severity=severity_filter)
    if status_filter:
        query = query.filter_by(status=status_filter)

    pagination = query.order_by(SecurityEvent.created_at.desc()).paginate(
        page=page, per_page=25, error_out=False
    )

    # Stats
    total_events = SecurityEvent.query.count()
    critical_events = SecurityEvent.query.filter_by(severity="critical").count()
    open_events = SecurityEvent.query.filter_by(status="open").count()

    return render_template("admin/security.html",
        events=pagination,
        total_events=total_events,
        critical_events=critical_events,
        open_events=open_events,
        severity_filter=severity_filter,
        status_filter=status_filter,
    )


@admin_bp.route("/security/<event_id>/resolve", methods=["POST"])
@login_required
@require_admin
def resolve_security_event(event_id):
    """Resolve a security event."""
    event = SecurityEvent.query.get_or_404(event_id)
    event.status = request.form.get("status", "resolved")
    event.resolved_by = current_user.id
    event.resolved_at = datetime.now(timezone.utc)
    event.resolution_notes = request.form.get("notes", "")
    db.session.commit()

    AuditLogger.log("security_event_resolved",
                   f"Security event {event_id} resolved as {event.status}",
                   resource_type="security_event", resource_id=event_id,
                   severity="info")
    flash("Security event updated.", "success")
    return redirect(url_for("admin.security"))


# ==============================================================================
# AUDIT TRAIL
# ==============================================================================

@admin_bp.route("/audit")
@login_required
@require_admin
def audit_trail():
    """System audit trail viewer."""
    page = int(request.args.get("page", 1))
    action_filter = request.args.get("action")
    severity_filter = request.args.get("severity")

    query = AuditLog.query
    if action_filter:
        query = query.filter_by(action=action_filter)
    if severity_filter:
        query = query.filter_by(severity=severity_filter)

    pagination = query.order_by(AuditLog.created_at.desc()).paginate(
        page=page, per_page=50, error_out=False
    )

    # Unique actions for filter dropdown
    actions = db.session.query(AuditLog.action).distinct().all()
    action_list = [a[0] for a in actions]

    return render_template("admin/audit.html",
        logs=pagination,
        action_list=action_list,
        action_filter=action_filter,
        severity_filter=severity_filter,
    )


@admin_bp.route("/audit/export", methods=["POST"])
@login_required
@require_admin
def export_audit():
    """Export audit logs as JSON."""
    from flask import Response

    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).all()
    data = json.dumps([log.to_dict() for log in logs], indent=2, default=str)

    AuditLogger.log("audit_export", f"Audit logs exported ({len(logs)} records)",
                   severity="warning")

    return Response(
        data,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment;filename=audit_log_export.json"}
    )


# ==============================================================================
# MISSION MANAGEMENT
# ==============================================================================

@admin_bp.route("/missions")
@login_required
@require_admin
def missions():
    """Mission management page."""
    missions_list = Mission.query.order_by(Mission.order_index.asc()).all()
    return render_template("admin/missions.html", missions=missions_list)


@admin_bp.route("/missions/create", methods=["POST"])
@login_required
@require_admin
def create_mission():
    """Create a new mission."""
    mission = Mission(
        mission_code=request.form.get("mission_code", "").strip().upper(),
        title=request.form.get("title", "").strip(),
        description=request.form.get("description", "").strip(),
        difficulty=request.form.get("difficulty", "medium"),
        category=request.form.get("category", "").strip(),
        max_points=float(request.form.get("max_points", 100)),
        time_limit_seconds=int(request.form.get("time_limit", 600)),
        max_retries=int(request.form.get("max_retries", 20)),
        expected_schema=request.form.get("expected_schema", ""),
        expected_fields=request.form.get("expected_fields", ""),
        validation_regex=request.form.get("validation_regex", ""),
        sample_response=request.form.get("sample_response", ""),
        is_active=True,
        is_visible="is_visible" in request.form,
        order_index=int(request.form.get("order_index", 0)),
    )

    db.session.add(mission)
    db.session.commit()

    AuditLogger.log("mission_created",
                   f"Mission created: {mission.mission_code} - {mission.title}",
                   resource_type="mission", resource_id=mission.id)
    flash(f"Mission '{mission.title}' created!", "success")
    return redirect(url_for("admin.missions"))


@admin_bp.route("/missions/<mission_id>/toggle", methods=["POST"])
@login_required
@require_admin
def toggle_mission(mission_id):
    """Toggle mission visibility."""
    mission = Mission.query.get_or_404(mission_id)
    mission.is_visible = not mission.is_visible
    db.session.commit()

    status = "visible" if mission.is_visible else "hidden"
    AuditLogger.log("mission_toggled",
                   f"Mission {mission.mission_code} set to {status}",
                   resource_type="mission", resource_id=mission_id)
    flash(f"Mission '{mission.title}' is now {status}.", "info")
    return redirect(url_for("admin.missions"))


# ==============================================================================
# API ENDPOINTS FOR DASHBOARD REFRESH (AJAX)
# ==============================================================================

@admin_bp.route("/api/stats")
@login_required
@require_admin
def api_stats():
    """Return dashboard stats as JSON for auto-refresh."""
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

    return jsonify({
        "teams": {
            "total": Team.query.count(),
            "active": Team.query.filter_by(status="active").count(),
            "locked": Team.query.filter_by(status="locked").count(),
            "disqualified": Team.query.filter_by(status="disqualified").count(),
        },
        "submissions": {
            "total": Submission.query.count(),
            "valid": Submission.query.filter_by(validation_status="valid").count(),
            "invalid": Submission.query.filter_by(validation_status="invalid").count(),
            "error": Submission.query.filter_by(validation_status="error").count(),
            "recent_hour": Submission.query.filter(Submission.created_at >= one_hour_ago).count(),
        },
        "security": {
            "open_events": SecurityEvent.query.filter_by(status="open").count(),
            "flagged": Submission.query.filter_by(is_flagged=True).count(),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@admin_bp.route("/api/activity_feed")
@login_required
@require_admin
def api_activity_feed():
    """Return recent activity feed as JSON."""
    limit = min(int(request.args.get("limit", 20)), 50)
    recent = db.session.query(Submission, Team).join(
        Team, Submission.team_id == Team.id
    ).order_by(Submission.created_at.desc()).limit(limit).all()

    feed = []
    for sub, team in recent:
        feed.append({
            "id": sub.id,
            "team_code": team.team_code,
            "team_name": team.name,
            "mission": sub.mission.title if sub.mission else "Unknown Mission",
            "status": sub.validation_status,
            "score": round(sub.total_score, 2),
            "attempt": sub.attempt_number,
            "prompt_length": sub.prompt_length or (len(sub.prompt_text) if sub.prompt_text else 0),
            "flagged": sub.is_flagged,
            "suspicious": bool(sub.is_flagged or sub.injection_detected or sub.is_hallucinated),
            "created_at": sub.created_at.isoformat(),
        })

    return jsonify({"feed": feed})


@admin_bp.route("/api/analytics")
@login_required
@require_admin
def api_analytics():
    """Return lightweight chart data for dashboard visual widgets."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=24)

    hourly = []
    for i in range(24):
        bucket_start = start + timedelta(hours=i)
        bucket_end = bucket_start + timedelta(hours=1)
        total = Submission.query.filter(
            Submission.created_at >= bucket_start,
            Submission.created_at < bucket_end,
        ).count()
        invalid = Submission.query.filter(
            Submission.created_at >= bucket_start,
            Submission.created_at < bucket_end,
            Submission.validation_status.in_(["invalid", "error"]),
        ).count()
        hourly.append({
            "hour": bucket_start.strftime("%H:00"),
            "total": total,
            "invalid": invalid,
        })

    status_counts = {
        "valid": Submission.query.filter_by(validation_status="valid").count(),
        "invalid": Submission.query.filter_by(validation_status="invalid").count(),
        "error": Submission.query.filter_by(validation_status="error").count(),
    }

    active_teams = Team.query.filter(
        Team.last_activity_at >= (now - timedelta(minutes=15)),
        Team.status == "active",
    ).count()

    return jsonify({
        "hourly": hourly,
        "status_counts": status_counts,
        "active_teams_15m": active_teams,
        "hallucination_rate": round(
            (Team.query.with_entities(db.func.sum(Team.hallucination_count)).scalar() or 0)
            / max(Submission.query.count(), 1) * 100,
            2,
        ),
        "server_load": {
            "queue_depth": SecurityEvent.query.filter_by(status="open").count(),
            "events_open": SecurityEvent.query.filter_by(status="open").count(),
        },
    })
