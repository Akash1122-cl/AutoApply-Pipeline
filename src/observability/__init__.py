"""
Observability Module — Phase 10

Provides metrics collection, monitoring, and alerting capabilities
for the AutoApply platform.
"""

from .metrics_collector import MetricsCollector
from .alerts import AlertManager

__all__ = ['MetricsCollector', 'AlertManager']
