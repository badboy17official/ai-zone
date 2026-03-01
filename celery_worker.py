# ==============================================================================
# AI INTELLIGENCE ZONE — Control Arena
# Celery Worker — Async Task Processing
# ==============================================================================

import os
from celery import Celery
from celery.schedules import crontab
from datetime import datetime, timezone, timedelta

# ── Celery Configuration ──────────────────────────────────────────────────────

celery = Celery(
    "arena_tasks",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
    task_soft_time_limit=300,
    task_time_limit=600,
)

# ── Periodic Tasks (Celery Beat) ──────────────────────────────────────────────

celery.conf.beat_schedule = {
    "recalculate-rankings-every-60s": {
        "task": "celery_worker.recalculate_rankings_task",
        "schedule": 60.0,
    },
    "update-team-health-scores-every-5m": {
        "task": "celery_worker.update_health_scores_task",
        "schedule": 300.0,
    },
    "cleanup-expired-sessions-hourly": {
        "task": "celery_worker.cleanup_sessions_task",
        "schedule": crontab(minute=0),
    },
    "generate-activity-report-every-15m": {
        "task": "celery_worker.generate_activity_report_task",
        "schedule": 900.0,
    },
    "detect-anomalies-every-2m": {
        "task": "celery_worker.detect_anomalies_task",
        "schedule": 120.0,
    },
}


def get_flask_app():
    """Lazy import to avoid circular imports."""
    from app import create_app
    return create_app()


# ── Task Definitions ──────────────────────────────────────────────────────────

@celery.task(name="celery_worker.recalculate_rankings_task", bind=True, max_retries=3)
def recalculate_rankings_task(self):
    """Recalculate all team rankings."""
    try:
        app = get_flask_app()
        with app.app_context():
            from models import db, Team
            from scoring_engine import ScoringEngine

            ScoringEngine.recalculate_rankings()
            return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
    except Exception as exc:
        self.retry(exc=exc, countdown=10)


@celery.task(name="celery_worker.update_health_scores_task", bind=True, max_retries=3)
def update_health_scores_task(self):
    """Recalculate health scores for all active teams."""
    try:
        app = get_flask_app()
        with app.app_context():
            from models import db, Team
            from scoring_engine import ScoringEngine

            teams = Team.query.filter_by(status="active").all()
            updated = 0
            for team in teams:
                health = ScoringEngine.calculate_health_score(team.id)
                team.health_score = health.get("overall_health", 0)
                updated += 1

            db.session.commit()
            return {"status": "ok", "teams_updated": updated}
    except Exception as exc:
        self.retry(exc=exc, countdown=15)


@celery.task(name="celery_worker.cleanup_sessions_task")
def cleanup_sessions_task():
    """Clean up expired sessions and stale data."""
    app = get_flask_app()
    with app.app_context():
        from models import db, AuditLog
        from datetime import timedelta

        # Purge audit logs older than 90 days
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        deleted = AuditLog.query.filter(AuditLog.created_at < cutoff).delete()
        db.session.commit()

        return {"status": "ok", "purged_audit_logs": deleted}


@celery.task(name="celery_worker.generate_activity_report_task")
def generate_activity_report_task():
    """Generate periodic activity summary for monitoring."""
    app = get_flask_app()
    with app.app_context():
        from models import db, Submission, Team
        from sqlalchemy import func

        window = datetime.now(timezone.utc) - timedelta(minutes=15)

        recent_subs = Submission.query.filter(
            Submission.created_at >= window
        ).count()

        flagged = Submission.query.filter(
            Submission.created_at >= window,
            Submission.is_flagged == True
        ).count()

        active_teams = db.session.query(
            func.count(func.distinct(Submission.team_id))
        ).filter(Submission.created_at >= window).scalar()

        return {
            "status": "ok",
            "period_minutes": 15,
            "submissions": recent_subs,
            "flagged": flagged,
            "active_teams": active_teams,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@celery.task(name="celery_worker.detect_anomalies_task")
def detect_anomalies_task():
    """Detect submission anomalies — rapid-fire submissions, score manipulation."""
    app = get_flask_app()
    with app.app_context():
        from models import db, Submission, Team, SecurityEvent
        from sqlalchemy import func

        window = datetime.now(timezone.utc) - timedelta(minutes=2)
        alerts = []

        # Check for rapid-fire submissions (>20 in 2 minutes per team)
        rapid_fire = db.session.query(
            Submission.team_id,
            func.count(Submission.id).label("count")
        ).filter(
            Submission.created_at >= window
        ).group_by(Submission.team_id).having(
            func.count(Submission.id) > 20
        ).all()

        for team_id, count in rapid_fire:
            team = Team.query.get(team_id)
            event = SecurityEvent(
                event_type="rapid_fire_submissions",
                severity="high",
                source_ip="system",
                team_id=team_id,
                description=f"Team '{team.name}' submitted {count} times in 2 minutes (threshold: 20)",
                evidence=f'{{"team_id": {team_id}, "count": {count}, "window_minutes": 2}}',
            )
            db.session.add(event)
            alerts.append(f"rapid_fire:{team_id}")

        # Check for injection spikes
        injection_count = Submission.query.filter(
            Submission.created_at >= window,
            Submission.injection_detected == True
        ).count()

        if injection_count > 5:
            event = SecurityEvent(
                event_type="injection_spike",
                severity="critical",
                source_ip="system",
                description=f"Detected {injection_count} injection attempts in 2 minutes",
                evidence=f'{{"count": {injection_count}, "window_minutes": 2}}',
            )
            db.session.add(event)
            alerts.append(f"injection_spike:{injection_count}")

        db.session.commit()
        return {"status": "ok", "alerts": alerts}


@celery.task(name="celery_worker.process_submission_async", bind=True, max_retries=2)
def process_submission_async(self, submission_id):
    """Post-process a submission asynchronously (heavy tasks)."""
    try:
        app = get_flask_app()
        with app.app_context():
            from models import db, Submission
            from scoring_engine import ScoringEngine

            submission = Submission.query.get(submission_id)
            if not submission:
                return {"status": "error", "message": "Submission not found"}

            # Recalculate rankings after submission
            ScoringEngine.recalculate_rankings()

            return {"status": "ok", "submission_id": submission_id}
    except Exception as exc:
        self.retry(exc=exc, countdown=5)
