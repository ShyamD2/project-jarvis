"""
Project J.A.R.V.I.S. Automated Disaster Recovery & Drill Subsystem.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.recovery.disaster_drill import DisasterRecoveryDrill

def __getattr__(name: str):
    if name == "DisasterRecoveryDrill":
        from services.recovery.disaster_drill import DisasterRecoveryDrill
        return DisasterRecoveryDrill
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["DisasterRecoveryDrill"]
