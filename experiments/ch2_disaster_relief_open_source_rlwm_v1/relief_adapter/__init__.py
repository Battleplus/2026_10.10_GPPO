"""Public-observation adapter for the existing civilian relief simulator."""

from .decision_repeat import (
    ADAPTER_SCHEMA,
    DEFAULT_MAX_DEPOT_SLOTS,
    DEFAULT_MAX_PLATFORM_SLOTS,
    DEFAULT_MAX_TASK_SLOTS,
    DecisionRepeatReliefAdapter,
)

__all__ = [
    "ADAPTER_SCHEMA",
    "DEFAULT_MAX_DEPOT_SLOTS",
    "DEFAULT_MAX_PLATFORM_SLOTS",
    "DEFAULT_MAX_TASK_SLOTS",
    "DecisionRepeatReliefAdapter",
]
