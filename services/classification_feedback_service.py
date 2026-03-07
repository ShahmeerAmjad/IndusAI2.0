"""Classification feedback service — logs human corrections and provides few-shot examples."""

import logging
import uuid

logger = logging.getLogger(__name__)

# Module-level DI
_feedback_service = None


def set_feedback_service(svc):
    global _feedback_service
    _feedback_service = svc


def get_feedback_service():
    return _feedback_service


class ClassificationFeedbackService:
    def __init__(self, db_manager):
        self._db = db_manager

    async def log_feedback(
        self,
        message_id: str,
        ai_intent: str,
        human_intent: str,
        is_correct: bool,
        ai_confidence: float = 0.0,
        text_excerpt: str = "",
        corrected_by: str | None = None,
    ) -> str:
        """Log a classification feedback entry. Returns feedback ID."""
        feedback_id = str(uuid.uuid4())
        async with self._db.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO classification_feedback
                   (id, message_id, ai_intent, ai_confidence, human_intent,
                    text_excerpt, is_correct, corrected_by)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                uuid.UUID(feedback_id),
                uuid.UUID(message_id),
                ai_intent,
                ai_confidence,
                human_intent,
                text_excerpt[:500] if text_excerpt else "",
                is_correct,
                uuid.UUID(corrected_by) if corrected_by else None,
            )
        return feedback_id

    async def get_few_shot_examples(self, intent_type: str, limit: int = 5) -> list[dict]:
        """Get recent correct classification examples for few-shot prompting."""
        async with self._db.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT cf.human_intent, cf.text_excerpt, cf.ai_confidence
                   FROM classification_feedback cf
                   WHERE cf.is_correct = TRUE
                     AND cf.human_intent = $1
                     AND cf.text_excerpt IS NOT NULL
                     AND cf.text_excerpt != ''
                   ORDER BY cf.created_at DESC
                   LIMIT $2""",
                intent_type,
                limit,
            )
        return [
            {
                "intent": r["human_intent"],
                "text": r["text_excerpt"],
                "confidence": r["ai_confidence"],
            }
            for r in rows
        ]

    async def get_accuracy_stats(self) -> dict:
        """Compute overall and per-intent accuracy rates."""
        async with self._db.pool.acquire() as conn:
            # Overall stats
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM classification_feedback"
            )
            correct = await conn.fetchval(
                "SELECT COUNT(*) FROM classification_feedback WHERE is_correct = TRUE"
            )

            # Per-intent stats
            rows = await conn.fetch(
                """SELECT ai_intent,
                          COUNT(*) AS total,
                          COUNT(*) FILTER (WHERE is_correct) AS correct
                   FROM classification_feedback
                   GROUP BY ai_intent
                   ORDER BY total DESC"""
            )

        overall_accuracy = round(correct / total * 100, 1) if total > 0 else 0.0

        per_intent = [
            {
                "intent": r["ai_intent"],
                "total": r["total"],
                "correct": r["correct"],
                "accuracy": round(r["correct"] / r["total"] * 100, 1) if r["total"] > 0 else 0.0,
            }
            for r in rows
        ]

        return {
            "total_feedback": total,
            "correct": correct,
            "accuracy": overall_accuracy,
            "per_intent": per_intent,
        }
