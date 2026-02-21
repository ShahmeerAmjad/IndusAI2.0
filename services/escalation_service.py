# =======================
# Escalation Service - Support Ticket Management
# =======================

import logging
from typing import Dict, List, Optional


class EscalationService:
    """Manages creation and tracking of escalation tickets for issues
    that need human support intervention."""

    def __init__(self, settings, logger: logging.Logger, db_manager):
        self.settings = settings
        self.logger = logger
        self.db_manager = db_manager

        # In-memory stats (augmented by DB when available)
        self._total_created = 0
        self._total_resolved = 0

    async def create_ticket(
        self,
        customer_id: str,
        subject: str,
        description: str,
        priority: str = "medium",
    ) -> Optional[str]:
        """Create a new escalation ticket.

        Returns the ticket ID if persisted, or None when running without a database.
        """
        self.logger.info(
            f"Escalation ticket created — customer={customer_id}, "
            f"priority={priority}, subject={subject[:80]}"
        )
        self._total_created += 1

        ticket_id = await self.db_manager.create_escalation_ticket(
            customer_id=customer_id,
            subject=subject,
            description=description,
            priority=priority,
        )

        if ticket_id:
            self.logger.info(f"Ticket persisted: {ticket_id}")
        else:
            self.logger.warning("Ticket could not be persisted (no DB connection)")

        # TODO: Send notification to support team via email/Slack
        return ticket_id

    async def get_open_tickets(self, limit: int = 50) -> List[Dict]:
        """Return currently open escalation tickets."""
        return await self.db_manager.get_open_tickets(limit=limit)

    def get_stats(self) -> Dict:
        """Return escalation statistics for health/admin endpoints."""
        return {
            "total_created": self._total_created,
            "total_resolved": self._total_resolved,
        }
