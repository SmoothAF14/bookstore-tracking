"""
core/maps_client.py — Google Maps client (MOCK DATA ONLY).

Produces deterministic route/ETA data derived from the delivery address. No
real Google Maps billing or network calls are made while GOOGLE_MAPS_USE_MOCK
is True (the default). The real path is intentionally left unimplemented so it
can never be hit by accident.
"""
import hashlib
from dataclasses import dataclass, field

from app.core.config import settings

# A fixed origin warehouse for the mock (the "store").
_ORIGIN = {"lat": 19.0760, "lng": 72.8777, "label": "Folio Fulfilment Centre, Mumbai"}

# A small set of plausible transit hubs the mock routes through.
_HUBS = [
    "Mumbai Sorting Hub",
    "Pune Regional Hub",
    "Nagpur Transit Point",
    "Local Delivery Centre",
]


@dataclass
class MockRoute:
    origin: dict
    destination: dict
    distance_km: float
    duration_hours: float
    hubs: list[str] = field(default_factory=list)


def _seed(address: str) -> int:
    """Stable integer seed derived from the address string."""
    digest = hashlib.sha256((address or "unknown").encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def geocode(address: str) -> dict:
    """Return a deterministic mock lat/lng for an address."""
    s = _seed(address)
    # Spread points across a plausible India bounding box.
    lat = 8.0 + (s % 2000) / 100.0          # ~8.0 – 28.0
    lng = 68.0 + ((s >> 11) % 2000) / 100.0  # ~68.0 – 88.0
    return {"lat": round(lat, 4), "lng": round(lng, 4), "label": address}


def get_route(destination_address: str) -> MockRoute:
    """Build a deterministic mock route + ETA from origin to the destination.

    Raises RuntimeError if real Maps is requested (not implemented on purpose).
    """
    if not settings.GOOGLE_MAPS_USE_MOCK:
        # We deliberately never make real billed calls in this project.
        raise RuntimeError(
            "Real Google Maps calls are disabled. Set GOOGLE_MAPS_USE_MOCK=True."
        )

    dest = geocode(destination_address)
    s = _seed(destination_address)

    # Deterministic distance 40–1240 km and a derived duration.
    distance_km = 40 + (s % 1200)
    duration_hours = round(distance_km / 45.0, 1)  # ~45 km/h effective avg

    # Pick a deterministic subset of hubs proportional to distance.
    hub_count = 1 + (s % len(_HUBS))
    hubs = _HUBS[:hub_count]

    return MockRoute(
        origin=dict(_ORIGIN),
        destination=dest,
        distance_km=float(distance_km),
        duration_hours=duration_hours,
        hubs=hubs,
    )
