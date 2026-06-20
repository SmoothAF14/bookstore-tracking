"""
schemas/tracking.py — Request/response models for the tracking service.

The TrackingCheckpoint shape is the shared contract with bookstore-delivery:
its timeline_service merges these checkpoints into the per-order
delivery-status timeline, and its tracking_client pulls them from
GET /tracking/{order_id}.
"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

# Ordered tracking stages the shipment moves through. These map 1:1 to the
# order status the orchestrator drives on the Django backend.
TrackingStatus = Literal[
    "pending",
    "dispatched",
    "in_transit",
    "out_for_delivery",
    "delivered",
]

# Order-status values written back to the Django backend for each stage.
STATUS_TO_ORDER_STATUS: dict[str, str] = {
    "pending": "confirmed",
    "dispatched": "processing",
    "in_transit": "shipped",
    "out_for_delivery": "shipped",
    "delivered": "delivered",
}


class GeoPoint(BaseModel):
    """A mock lat/lng point on the route."""
    lat: float
    lng: float
    label: Optional[str] = None


class TrackingCheckpoint(BaseModel):
    """A single point on the shipment's journey.

    Shared contract: bookstore-delivery merges these into its timeline.
    """
    status: TrackingStatus
    label: str = Field(..., description="Human-readable status, e.g. 'Out for delivery'")
    description: Optional[str] = None
    location: Optional[str] = Field(None, description="City / hub name for this checkpoint")
    point: Optional[GeoPoint] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    is_current: bool = False


class StartTrackingRequest(BaseModel):
    """Begin tracking an order. The address is read from the order's delivery
    record on the backend, but may be supplied to override / for testing."""
    order_id: str
    destination_address: Optional[str] = Field(
        None, description="Full delivery address; if omitted, read from the order."
    )
    auto_advance: bool = Field(
        True, description="Schedule Celery jobs to advance tracking automatically."
    )


class TrackingStateResponse(BaseModel):
    """Current tracking state for an order + its full checkpoint history."""
    order_id: str
    status: TrackingStatus
    order_status: str = Field(..., description="Corresponding Django order status")
    origin: Optional[str] = None
    destination: Optional[str] = None
    destination_address: Optional[str] = Field(None, description="Full delivery address (for geocoding)")
    distance_km: Optional[float] = None
    eta: Optional[datetime] = Field(None, description="Estimated delivery time")
    # Geo points for map rendering (mock coordinates, real map tiles client-side).
    origin_point: Optional[GeoPoint] = Field(None, description="Fulfilment centre coordinates")
    destination_point: Optional[GeoPoint] = Field(None, description="Delivery destination coordinates")
    current_point: Optional[GeoPoint] = Field(None, description="Live shipment position for this stage")
    checkpoints: list[TrackingCheckpoint] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AdvanceResponse(BaseModel):
    """Result of advancing tracking one step."""
    order_id: str
    advanced: bool
    status: TrackingStatus
    message: str
