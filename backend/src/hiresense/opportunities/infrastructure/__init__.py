from hiresense.opportunities.infrastructure.in_memory_repository import (
    InMemoryOpportunitiesRepository,
)
from hiresense.opportunities.infrastructure.orm import OpportunityOrm
from hiresense.opportunities.infrastructure.repository import OpportunitiesRepository

__all__ = [
    "InMemoryOpportunitiesRepository",
    "OpportunitiesRepository",
    "OpportunityOrm",
]
