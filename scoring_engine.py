# ==============================================================================
# AI INTELLIGENCE ZONE — Control Arena
# Leaderboard Scoring Engine
# ==============================================================================
# Implements the full scoring algorithm with:
#   - Base score calculation (accuracy × speed × validation)
#   - Bonus point system (first blood, speed demon, etc.)
#   - Tie-break resolution
#   - Anti-gaming measures
#   - Real-time rank calculation
# ==============================================================================

import math
from datetime import datetime, timezone
from models import db, Team, Submission, Mission, Achievement


class ScoringEngine:
    """
    Central scoring engine for the competition.
    All scoring logic is centralized here for consistency and auditability.
    """

    # ── Weight Configuration (loaded from app config at runtime) ──────
    DEFAULT_WEIGHTS = {
        "accuracy": 0.50,
        "speed": 0.20,
        "validation": 0.30,
    }

    DEFAULT_BONUSES = {
        "first_blood": 50,
        "perfect_parse": 25,
        "speed_demon": 30,
        "consistency": 20,
        "zero_error": 40,
        "innovation": 15,
    }

    # ══════════════════════════════════════════════════════════════════════
    # MISSION SCORE CALCULATION
    # ══════════════════════════════════════════════════════════════════════

    @classmethod
    def calculate_mission_score(cls, submission, mission, team, config=None):
        """
        Calculate the total score for a single mission submission.

        Formula:
            Mission_Score = (Accuracy × W_acc) + (Speed × W_spd) + (Validation × W_val)

        Returns dict with breakdown of all score components.
        """
        weights = config or cls.DEFAULT_WEIGHTS

        # ── Accuracy Score (0-100) ────────────────────────────────────
        accuracy = cls._calculate_accuracy(submission, mission)

        # ── Speed Bonus (0-100) ───────────────────────────────────────
        speed = cls._calculate_speed_score(submission, mission, team)

        # ── Validation Rate (0-100) ───────────────────────────────────
        validation = cls._calculate_validation_score(team)

        # ── Weighted Total ────────────────────────────────────────────
        base_score = (
            (accuracy * weights.get("accuracy", 0.50)) +
            (speed * weights.get("speed", 0.20)) +
            (validation * weights.get("validation", 0.30))
        )

        # ── Apply retry penalty (exponential decay) ───────────────────
        retry_penalty = math.exp(-0.1 * max(0, submission.attempt_number - 1))
        penalized_score = base_score * retry_penalty

        # ── Scale to mission max points ───────────────────────────────
        final_score = (penalized_score / 100) * mission.max_points

        return {
            "accuracy_score": round(accuracy, 2),
            "speed_score": round(speed, 2),
            "validation_score": round(validation, 2),
            "base_score": round(base_score, 2),
            "retry_penalty": round(retry_penalty, 4),
            "penalized_score": round(penalized_score, 2),
            "final_score": round(final_score, 2),
            "max_possible": mission.max_points,
            "attempt_number": submission.attempt_number,
        }

    @classmethod
    def _calculate_accuracy(cls, submission, mission):
        """
        Calculate accuracy score (0-100).

        Based on:
        - Field correctness (from validation)
        - Schema compliance multiplier
        - Confidence score
        """
        # Base accuracy from confidence score
        base = submission.confidence_score * 100

        # Schema compliance multiplier
        if submission.schema_valid and submission.json_valid and submission.type_check_valid:
            multiplier = 1.0  # Perfect compliance
        elif submission.json_valid and submission.schema_valid:
            multiplier = 0.8  # Minor issues
        elif submission.json_valid:
            multiplier = 0.5  # Parsed but schema failed
        else:
            multiplier = 0.0  # Can't parse

        return min(100, base * multiplier)

    @classmethod
    def _calculate_speed_score(cls, submission, mission, team):
        """
        Calculate speed score (0-100) with exponential decay for retries.

        Formula: max(0, 100 - ((time_taken / time_limit) × 100)) × decay
        """
        if not submission.response_time_ms or not mission.time_limit_seconds:
            return 50  # Default middle score if timing not available

        time_limit_ms = mission.time_limit_seconds * 1000
        time_taken_ms = submission.response_time_ms

        # Calculate raw speed score
        time_ratio = time_taken_ms / time_limit_ms
        raw_speed = max(0, 100 - (time_ratio * 100))

        # Apply attempt decay
        decay = math.exp(-0.1 * max(0, submission.attempt_number - 1))

        return raw_speed * decay

    @classmethod
    def _calculate_validation_score(cls, team):
        """
        Calculate validation rate score (0-100).

        Based on team's overall successful validation ratio.
        """
        if team.total_submissions == 0:
            return 100  # Benefit of the doubt for first submission

        return (team.successful_validations / team.total_submissions) * 100

    # ══════════════════════════════════════════════════════════════════════
    # BONUS CALCULATION
    # ══════════════════════════════════════════════════════════════════════

    @classmethod
    def check_and_award_bonuses(cls, submission, mission, team, bonuses=None):
        """
        Check all bonus conditions and award applicable bonuses.
        Returns list of awarded bonuses.
        """
        bonus_config = bonuses or cls.DEFAULT_BONUSES
        awarded = []

        # ── First Blood: First team to complete this mission ──────────
        if not mission.first_blood_team_id and submission.validation_status == "valid":
            mission.first_blood_team_id = team.id
            mission.first_blood_at = datetime.now(timezone.utc)
            bonus = bonus_config["first_blood"]
            awarded.append(cls._create_achievement(
                team, "first_blood", "🩸 First Blood",
                f"First to complete mission: {mission.title}",
                "🩸", bonus, mission.id
            ))

        # ── Perfect Parse: Zero errors on first attempt ───────────────
        if (submission.attempt_number == 1 and
                submission.validation_status == "valid" and
                len(submission.validation_errors or "[]") <= 2):  # "[]"
            bonus = bonus_config["perfect_parse"]
            awarded.append(cls._create_achievement(
                team, "perfect_parse", "✨ Perfect Parse",
                f"Zero errors on first try: {mission.title}",
                "✨", bonus, mission.id
            ))

        # ── Speed Demon: Under 25% of time limit ─────────────────────
        if (submission.response_time_ms and mission.time_limit_seconds and
                submission.response_time_ms < (mission.time_limit_seconds * 1000 * 0.25)):
            bonus = bonus_config["speed_demon"]
            awarded.append(cls._create_achievement(
                team, "speed_demon", "⚡ Speed Demon",
                f"Blazing fast completion: {mission.title}",
                "⚡", bonus, mission.id
            ))

        # ── Consistency: 5 consecutive valid submissions ──────────────
        recent_subs = Submission.query.filter_by(
            team_id=team.id, validation_status="valid"
        ).order_by(Submission.created_at.desc()).limit(5).all()

        if len(recent_subs) >= 5:
            # Check if already awarded
            existing = Achievement.query.filter_by(
                team_id=team.id, achievement_type="consistency"
            ).first()
            if not existing:
                bonus = bonus_config["consistency"]
                awarded.append(cls._create_achievement(
                    team, "consistency", "🎯 Consistency King",
                    "5 consecutive valid submissions",
                    "🎯", bonus
                ))

        return awarded

    @classmethod
    def _create_achievement(cls, team, atype, title, desc, icon, points, mission_id=None):
        """Create and persist an achievement."""
        achievement = Achievement(
            team_id=team.id,
            achievement_type=atype,
            title=title,
            description=desc,
            icon=icon,
            points_awarded=points,
            mission_id=mission_id,
        )
        db.session.add(achievement)
        team.bonus_points += points
        return achievement.to_dict() if hasattr(achievement, 'to_dict') else {
            "type": atype, "title": title, "points": points
        }

    # ══════════════════════════════════════════════════════════════════════
    # LEADERBOARD RANKING
    # ══════════════════════════════════════════════════════════════════════

    @classmethod
    def recalculate_rankings(cls):
        """
        Recalculate all team rankings using the tie-break algorithm.

        Tie-break priority:
        1. Total score (highest)
        2. Fewer total submissions (efficiency)
        3. Earlier final submission timestamp
        4. Higher average confidence score
        5. Lower hallucination rate
        """
        teams = Team.query.filter(
            Team.status.in_(["active", "locked"])
        ).all()

        # Compute sort key for each team
        team_data = []
        for team in teams:
            # Get latest submission timestamp
            latest_sub = Submission.query.filter_by(team_id=team.id).order_by(
                Submission.created_at.desc()
            ).first()
            latest_ts = latest_sub.created_at.timestamp() if latest_sub else float('inf')

            # Get average confidence score
            avg_conf_result = db.session.query(
                db.func.avg(Submission.confidence_score)
            ).filter_by(team_id=team.id).scalar()
            avg_confidence = avg_conf_result or 0

            team_data.append({
                "team": team,
                "total_score": team.total_score + team.bonus_points,
                "total_submissions": team.total_submissions,
                "latest_timestamp": latest_ts,
                "avg_confidence": avg_confidence,
                "hallucination_count": team.hallucination_count,
            })

        # Sort with tie-break logic
        team_data.sort(key=lambda t: (
            -t["total_score"],           # 1. Higher score first
            t["total_submissions"],       # 2. Fewer submissions
            t["latest_timestamp"],        # 3. Earlier final submission
            -t["avg_confidence"],         # 4. Higher confidence
            t["hallucination_count"],     # 5. Fewer hallucinations
        ))

        # Assign ranks
        for rank, data in enumerate(team_data, 1):
            data["team"].current_rank = rank

        db.session.commit()

        return [
            {
                "rank": data["team"].current_rank,
                "team_code": data["team"].team_code,
                "name": data["team"].name,
                "total_score": round(data["total_score"], 2),
                "missions_completed": data["team"].missions_completed,
                "total_submissions": data["team"].total_submissions,
                "validation_rate": round(data["team"].validation_rate, 1),
            }
            for data in team_data
        ]

    # ══════════════════════════════════════════════════════════════════════
    # TEAM HEALTH SCORE
    # ══════════════════════════════════════════════════════════════════════

    @classmethod
    def calculate_health_score(cls, team):
        """
        Calculate team health score (0-100).
        Composite of activity, error rate, quality, and participation.
        """
        scores = []

        # Activity score (based on submission frequency)
        if team.total_submissions > 0:
            scores.append(min(100, team.total_submissions * 10))
        else:
            scores.append(0)

        # Error rate score (inverse — lower error rate = higher score)
        scores.append(max(0, 100 - team.error_rate))

        # Validation quality
        scores.append(team.validation_rate)

        # Member participation
        active_members = team.active_member_count
        total_members = team.members.count()
        if total_members > 0:
            scores.append((active_members / total_members) * 100)
        else:
            scores.append(0)

        # Hallucination penalty
        halluc_penalty = min(50, team.hallucination_count * 5)
        scores.append(max(0, 100 - halluc_penalty))

        health = sum(scores) / len(scores) if scores else 0
        return round(min(100, max(0, health)), 1)
