# ==============================================================================
# AI INTELLIGENCE ZONE — Control Arena
# Database Seeder — Populate with demo data for testing
# ==============================================================================

import json
import random
from datetime import datetime, timezone, timedelta

from app import create_app
from models import db, User, Team, TeamMember, Mission, Submission, AILog, Achievement


def seed_database():
    """Seed the database with realistic demo data."""
    app = create_app()

    with app.app_context():
        print("🗑️  Clearing existing data...")
        db.drop_all()
        db.create_all()

        # ── Create Admin Users ────────────────────────────────────
        print("👤 Creating admin users...")
        admin = User(
            username="arena_admin",
            email="admin@controlarena.local",
            role="super_admin",
            is_active=True,
        )
        admin.set_password("ChangeMe@2026!")

        moderator = User(
            username="arena_mod",
            email="mod@controlarena.local",
            role="moderator",
            is_active=True,
        )
        moderator.set_password("ModPass@2026!")

        db.session.add_all([admin, moderator])
        db.session.flush()

        # ── Create Teams ──────────────────────────────────────────
        print("👥 Creating teams...")
        team_data = [
            ("TEAM-ALPHA-01", "Neural Knights", "#6366f1", "MIT"),
            ("TEAM-BETA-02", "Tensor Titans", "#10b981", "Stanford"),
            ("TEAM-GAMMA-03", "Gradient Gang", "#f59e0b", "CMU"),
            ("TEAM-DELTA-04", "Loss Function", "#ef4444", "Berkeley"),
            ("TEAM-EPSILON-05", "Epoch Masters", "#8b5cf6", "Harvard"),
            ("TEAM-ZETA-06", "Deep Dreamers", "#06b6d4", "Caltech"),
            ("TEAM-ETA-07", "Batch Normies", "#ec4899", "Princeton"),
            ("TEAM-THETA-08", "Overfitters", "#14b8a6", "Yale"),
            ("TEAM-IOTA-09", "Weight Watchers", "#f97316", "Oxford"),
            ("TEAM-KAPPA-10", "The Transformers", "#a855f7", "Cambridge"),
        ]

        teams = []
        colors = ["#6366f1", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
                  "#06b6d4", "#ec4899", "#14b8a6", "#f97316", "#a855f7"]

        for code, name, color, institution in team_data:
            team = Team(
                team_code=code,
                name=name,
                institution=institution,
                status="active",
                avatar_color=color,
            )
            db.session.add(team)
            db.session.flush()
            teams.append(team)

            # Create team members
            for j in range(random.randint(2, 4)):
                member_user = User(
                    username=f"{code.lower().replace('-', '_')}_m{j+1}",
                    email=f"{code.lower().replace('-', '_')}_m{j+1}@team.local",
                    role="team_member",
                    is_active=True,
                )
                member_user.set_password(f"Team{code[-2:]}Pass!")
                db.session.add(member_user)
                db.session.flush()

                member = TeamMember(
                    team_id=team.id,
                    user_id=member_user.id,
                    role_in_team="lead" if j == 0 else "member",
                )
                db.session.add(member)

        # ── Create Missions ───────────────────────────────────────
        print("🎯 Creating missions...")
        missions = [
            {
                "code": "MISSION-01",
                "title": "JSON Identity Parser",
                "desc": "Generate a valid JSON object containing your team identity with fields: team_name, team_code, member_count, and motto.",
                "difficulty": "easy",
                "category": "Parsing",
                "points": 100,
                "time": 300,
                "schema": json.dumps({
                    "type": "object",
                    "properties": {
                        "team_name": {"type": "string"},
                        "team_code": {"type": "string"},
                        "member_count": {"type": "integer"},
                        "motto": {"type": "string"},
                    },
                    "required": ["team_name", "team_code", "member_count", "motto"],
                }),
                "fields": json.dumps(["team_name", "team_code", "member_count", "motto"]),
            },
            {
                "code": "MISSION-02",
                "title": "Sentiment Classifier",
                "desc": "Analyze a given text and return a structured JSON with: text, sentiment (positive/negative/neutral), confidence (0-1), and keywords (array).",
                "difficulty": "medium",
                "category": "NLP",
                "points": 150,
                "time": 600,
                "schema": json.dumps({
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "keywords": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["text", "sentiment", "confidence", "keywords"],
                }),
                "fields": json.dumps(["text", "sentiment", "confidence", "keywords"]),
            },
            {
                "code": "MISSION-03",
                "title": "Data Structure Generator",
                "desc": "Create a valid JSON representing a binary tree node structure with: value (integer), left (node or null), right (node or null), depth (integer).",
                "difficulty": "hard",
                "category": "Data Structures",
                "points": 200,
                "time": 900,
                "schema": json.dumps({
                    "type": "object",
                    "properties": {
                        "value": {"type": "integer"},
                        "left": {},
                        "right": {},
                        "depth": {"type": "integer"},
                    },
                    "required": ["value", "depth"],
                }),
                "fields": json.dumps(["value", "left", "right", "depth"]),
            },
            {
                "code": "MISSION-04",
                "title": "API Response Simulator",
                "desc": "Generate a realistic API error response with: status_code, error_type, message, timestamp (ISO 8601), and request_id (UUID format).",
                "difficulty": "medium",
                "category": "API Design",
                "points": 150,
                "time": 600,
                "schema": json.dumps({
                    "type": "object",
                    "properties": {
                        "status_code": {"type": "integer"},
                        "error_type": {"type": "string"},
                        "message": {"type": "string"},
                        "timestamp": {"type": "string"},
                        "request_id": {"type": "string"},
                    },
                    "required": ["status_code", "error_type", "message", "timestamp", "request_id"],
                }),
                "fields": json.dumps(["status_code", "error_type", "message", "timestamp", "request_id"]),
            },
            {
                "code": "MISSION-05",
                "title": "The Final Challenge",
                "desc": "Generate a complete competition summary with: team_name, missions_completed (array of mission codes), total_score, rank, achievements (array), and final_statement.",
                "difficulty": "legendary",
                "category": "Integration",
                "points": 300,
                "time": 1200,
                "schema": json.dumps({
                    "type": "object",
                    "properties": {
                        "team_name": {"type": "string"},
                        "missions_completed": {"type": "array", "items": {"type": "string"}},
                        "total_score": {"type": "number"},
                        "rank": {"type": "integer"},
                        "achievements": {"type": "array", "items": {"type": "string"}},
                        "final_statement": {"type": "string"},
                    },
                    "required": ["team_name", "missions_completed", "total_score", "rank", "achievements", "final_statement"],
                }),
                "fields": json.dumps(["team_name", "missions_completed", "total_score", "rank", "achievements", "final_statement"]),
            },
        ]

        mission_objects = []
        for i, m in enumerate(missions):
            mission = Mission(
                mission_code=m["code"],
                title=m["title"],
                description=m["desc"],
                difficulty=m["difficulty"],
                category=m["category"],
                max_points=m["points"],
                time_limit_seconds=m["time"],
                expected_schema=m["schema"],
                expected_fields=m["fields"],
                is_active=True,
                is_visible=True,
                order_index=i,
            )
            db.session.add(mission)
            db.session.flush()
            mission_objects.append(mission)

        # ── Create Sample Submissions ─────────────────────────────
        print("📝 Creating sample submissions...")
        statuses = ["valid", "valid", "valid", "invalid", "error"]

        for team in teams:
            for mission in mission_objects[:random.randint(2, 5)]:
                num_attempts = random.randint(1, 5)
                for attempt in range(1, num_attempts + 1):
                    status = random.choice(statuses)
                    is_valid = status == "valid"
                    confidence = random.uniform(0.7, 1.0) if is_valid else random.uniform(0.1, 0.5)
                    score = random.uniform(50, 100) if is_valid else 0

                    sub = Submission(
                        team_id=team.id,
                        mission_id=mission.id,
                        attempt_number=attempt,
                        prompt_text=f"Generate a response for {mission.title}",
                        ai_raw_response=json.dumps({"sample": "data", "valid": is_valid}),
                        validation_status=status,
                        json_valid=True,
                        schema_valid=is_valid,
                        type_check_valid=is_valid,
                        regex_valid=True,
                        field_count_valid=is_valid,
                        validation_errors=json.dumps([] if is_valid else ["Schema mismatch"]),
                        accuracy_score=score * 0.5 if is_valid else 0,
                        speed_score=score * 0.2 if is_valid else 0,
                        validation_score=score * 0.3 if is_valid else 0,
                        confidence_score=confidence,
                        total_score=score if is_valid else 0,
                        response_time_ms=random.randint(200, 5000),
                        prompt_length=random.randint(20, 200),
                        response_length=random.randint(50, 500),
                        ip_address=f"192.168.1.{random.randint(10, 200)}",
                        is_flagged=random.random() < 0.05,
                        injection_detected=random.random() < 0.03,
                        is_hallucinated=random.random() < 0.1,
                        created_at=datetime.now(timezone.utc) - timedelta(
                            minutes=random.randint(0, 480)
                        ),
                    )
                    db.session.add(sub)

                    # Update team stats
                    team.total_submissions += 1
                    if is_valid:
                        team.successful_validations += 1
                        team.total_score += score
                    else:
                        team.failed_validations += 1

            # Update team metrics
            team.error_rate = (team.failed_validations / max(team.total_submissions, 1)) * 100
            team.missions_completed = random.randint(1, min(4, len(mission_objects)))
            team.hallucination_count = random.randint(0, 3)
            team.health_score = random.uniform(60, 100)
            team.last_activity_at = datetime.now(timezone.utc) - timedelta(minutes=random.randint(0, 60))

        # ── Assign Rankings ───────────────────────────────────────
        sorted_teams = sorted(teams, key=lambda t: t.total_score, reverse=True)
        for rank, team in enumerate(sorted_teams, 1):
            team.current_rank = rank

        # ── Create Sample Achievements ────────────────────────────
        print("🏆 Creating achievements...")
        if teams:
            first_blood = Achievement(
                team_id=sorted_teams[0].id,
                achievement_type="first_blood",
                title="🩸 First Blood",
                description="First team to complete Mission 01",
                icon="🩸",
                points_awarded=50,
                mission_id=mission_objects[0].id,
            )
            db.session.add(first_blood)
            sorted_teams[0].bonus_points += 50

        db.session.commit()

        print(f"\n✅ Database seeded successfully!")
        print(f"   👤 Admin users: 2")
        print(f"   👥 Teams: {len(teams)}")
        print(f"   🎯 Missions: {len(mission_objects)}")
        print(f"   📝 Submissions: {Submission.query.count()}")
        print(f"\n🔑 Login Credentials:")
        print(f"   Admin:     arena_admin / ChangeMe@2026!")
        print(f"   Moderator: arena_mod / ModPass@2026!")
        print(f"\n🌐 Start server: python app.py")
        print(f"   Dashboard: http://localhost:5000/admin/")


if __name__ == "__main__":
    seed_database()
