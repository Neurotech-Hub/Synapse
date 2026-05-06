from __future__ import annotations

from app.models import FundingOpportunity


def funding_is_publicly_visible(funding: FundingOpportunity) -> bool:
    return bool(
        funding.is_public
        and funding.is_reviewed
        and funding.status in {"active", "expired"}
        and funding.archived_at is None
    )
