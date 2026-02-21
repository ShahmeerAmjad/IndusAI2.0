# =======================
# Workflow / State Machine Engine
# =======================
"""
Lightweight workflow engine for multi-step business processes.
Supports: order approval, PO approval, RMA approval, credit checks, price overrides.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# State machine definitions per workflow type
WORKFLOW_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "order_approval": {
        "initial_state": "pending_review",
        "final_states": ["approved", "rejected"],
        "transitions": {
            "pending_review": {
                "approve": "approved",
                "reject": "rejected",
                "request_info": "pending_info",
            },
            "pending_info": {
                "provide_info": "pending_review",
                "cancel": "rejected",
            },
        },
    },
    "po_approval": {
        "initial_state": "pending_review",
        "final_states": ["approved", "rejected"],
        "transitions": {
            "pending_review": {
                "approve": "approved",
                "reject": "rejected",
                "escalate": "pending_manager",
            },
            "pending_manager": {
                "approve": "approved",
                "reject": "rejected",
            },
        },
    },
    "rma_approval": {
        "initial_state": "requested",
        "final_states": ["approved", "rejected"],
        "transitions": {
            "requested": {
                "approve": "approved",
                "reject": "rejected",
                "request_inspection": "pending_inspection",
            },
            "pending_inspection": {
                "pass_inspection": "approved",
                "fail_inspection": "rejected",
            },
        },
    },
    "credit_check": {
        "initial_state": "pending",
        "final_states": ["passed", "failed", "override_approved"],
        "transitions": {
            "pending": {
                "pass": "passed",
                "fail": "failed",
            },
            "failed": {
                "override": "override_approved",
            },
        },
    },
    "price_override": {
        "initial_state": "requested",
        "final_states": ["approved", "rejected"],
        "transitions": {
            "requested": {
                "approve": "approved",
                "reject": "rejected",
            },
        },
    },
}


class WorkflowEngine:
    """
    Manages workflow lifecycle: creation, state transitions, and queries.
    All state is persisted to PostgreSQL via db_manager.
    """

    def __init__(self, db_manager, logger):
        self.db = db_manager
        self.logger = logger

    async def create_workflow(
        self,
        workflow_type: str,
        reference_type: Optional[str] = None,
        reference_id: Optional[str] = None,
        assigned_to: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Create a new workflow instance. Returns workflow ID."""
        definition = WORKFLOW_DEFINITIONS.get(workflow_type)
        if not definition:
            self.logger.error(f"Unknown workflow type: {workflow_type}")
            return None

        if not self.db.pool:
            return None

        wf_id = str(uuid.uuid4())
        initial_state = definition["initial_state"]

        try:
            async with self.db.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO workflows
                        (id, workflow_type, reference_type, reference_id,
                         current_state, assigned_to, data)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    wf_id, workflow_type, reference_type, reference_id,
                    initial_state, assigned_to, json.dumps(data or {}),
                )
                # Record the initial transition
                await conn.execute(
                    """
                    INSERT INTO workflow_transitions
                        (id, workflow_id, from_state, to_state, action, performed_by)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    str(uuid.uuid4()), wf_id, None, initial_state, "create", "system",
                )
            self.logger.info(f"Workflow created: {workflow_type} ({wf_id})")
            return wf_id
        except Exception as e:
            self.logger.error(f"Failed to create workflow: {e}")
            return None

    async def transition(
        self,
        workflow_id: str,
        action: str,
        performed_by: str,
        notes: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Execute a state transition on a workflow.
        Returns updated workflow state or None if transition is invalid.
        """
        if not self.db.pool:
            return None

        try:
            async with self.db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT workflow_type, current_state, data FROM workflows WHERE id = $1",
                    workflow_id,
                )
                if not row:
                    self.logger.warning(f"Workflow not found: {workflow_id}")
                    return None

                wf_type = row["workflow_type"]
                current_state = row["current_state"]
                definition = WORKFLOW_DEFINITIONS.get(wf_type)
                if not definition:
                    return None

                # Check if transition is valid
                state_transitions = definition["transitions"].get(current_state, {})
                new_state = state_transitions.get(action)
                if not new_state:
                    self.logger.warning(
                        f"Invalid transition: {wf_type} / {current_state} -> {action}"
                    )
                    return None

                now = datetime.now(timezone.utc)
                completed_at = now if new_state in definition["final_states"] else None

                # Update workflow
                await conn.execute(
                    """
                    UPDATE workflows
                    SET current_state = $1, previous_state = $2,
                        completed_at = $3, updated_at = $4
                    WHERE id = $5
                    """,
                    new_state, current_state, completed_at, now, workflow_id,
                )

                # Record transition
                await conn.execute(
                    """
                    INSERT INTO workflow_transitions
                        (id, workflow_id, from_state, to_state, action, performed_by, notes)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    str(uuid.uuid4()), workflow_id,
                    current_state, new_state, action, performed_by, notes,
                )

                self.logger.info(
                    f"Workflow transition: {wf_type} {current_state} -> {new_state} ({action})"
                )
                return {
                    "workflow_id": workflow_id,
                    "workflow_type": wf_type,
                    "previous_state": current_state,
                    "current_state": new_state,
                    "action": action,
                    "is_complete": completed_at is not None,
                }

        except Exception as e:
            self.logger.error(f"Workflow transition failed: {e}")
            return None

    async def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get workflow details with transition history."""
        if not self.db.pool:
            return None

        try:
            async with self.db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, workflow_type, reference_type, reference_id,
                           current_state, previous_state, assigned_to, data,
                           started_at, completed_at, updated_at
                    FROM workflows WHERE id = $1
                    """,
                    workflow_id,
                )
                if not row:
                    return None

                transitions = await conn.fetch(
                    """
                    SELECT from_state, to_state, action, performed_by, notes, created_at
                    FROM workflow_transitions
                    WHERE workflow_id = $1
                    ORDER BY created_at ASC
                    """,
                    workflow_id,
                )

                result = dict(row)
                result["data"] = json.loads(result["data"]) if result["data"] else {}
                result["transitions"] = [dict(t) for t in transitions]
                # Convert timestamps to ISO strings
                for key in ("started_at", "completed_at", "updated_at"):
                    if result.get(key):
                        result[key] = result[key].isoformat()
                for t in result["transitions"]:
                    if t.get("created_at"):
                        t["created_at"] = t["created_at"].isoformat()
                return result

        except Exception as e:
            self.logger.error(f"Failed to get workflow: {e}")
            return None

    async def get_pending_workflows(
        self, workflow_type: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get workflows that are not yet completed."""
        if not self.db.pool:
            return []

        try:
            async with self.db.pool.acquire() as conn:
                if workflow_type:
                    rows = await conn.fetch(
                        """
                        SELECT id, workflow_type, reference_type, reference_id,
                               current_state, assigned_to, started_at
                        FROM workflows
                        WHERE completed_at IS NULL AND workflow_type = $1
                        ORDER BY started_at ASC
                        LIMIT $2
                        """,
                        workflow_type, limit,
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT id, workflow_type, reference_type, reference_id,
                               current_state, assigned_to, started_at
                        FROM workflows
                        WHERE completed_at IS NULL
                        ORDER BY started_at ASC
                        LIMIT $1
                        """,
                        limit,
                    )

                results = []
                for row in rows:
                    d = dict(row)
                    if d.get("started_at"):
                        d["started_at"] = d["started_at"].isoformat()
                    results.append(d)
                return results

        except Exception as e:
            self.logger.error(f"Failed to get pending workflows: {e}")
            return []

    async def get_available_actions(self, workflow_id: str) -> List[str]:
        """Return the list of valid actions for the workflow's current state."""
        if not self.db.pool:
            return []

        try:
            async with self.db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT workflow_type, current_state FROM workflows WHERE id = $1",
                    workflow_id,
                )
                if not row:
                    return []

                definition = WORKFLOW_DEFINITIONS.get(row["workflow_type"], {})
                transitions = definition.get("transitions", {}).get(row["current_state"], {})
                return list(transitions.keys())

        except Exception as e:
            self.logger.error(f"Failed to get available actions: {e}")
            return []
