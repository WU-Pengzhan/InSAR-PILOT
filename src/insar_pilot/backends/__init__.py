"""Canonical processing backend adapters and their production registry."""

from insar_pilot.backends.isce2 import Isce2TopsStackTaskBackend
from insar_pilot.backends.isce3 import NisarIsce3TaskBackend
from insar_pilot.providers.task_runtime import TaskBackendRegistry


def build_default_task_backend_registry() -> TaskBackendRegistry:
    """Register exactly one official execution adapter for each supported mission."""

    registry = TaskBackendRegistry()
    registry.register(Isce2TopsStackTaskBackend())
    registry.register(NisarIsce3TaskBackend())
    return registry


__all__ = [
    "Isce2TopsStackTaskBackend",
    "NisarIsce3TaskBackend",
    "build_default_task_backend_registry",
]
