from hiresense.tracking.domain.services import TrackingService


def get_tracking_service() -> TrackingService:
    raise NotImplementedError("Must be overridden during app startup via dependency_overrides")
