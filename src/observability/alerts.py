"""
Alert Manager — Phase 10

Handles alerting for failures, cost breaches, and SLA misses.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import json

from .metrics_collector import MetricsCollector


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(Enum):
    FAILURE_SPIKE = "failure_spike"
    COST_BREACH = "cost_breach"
    SLA_MISS = "sla_miss"
    CAP_VIOLATION = "cap_violation"
    ERROR_RATE_HIGH = "error_rate_high"


@dataclass
class Alert:
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    timestamp: datetime
    metadata: Dict[str, Any]
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class AlertRule:
    def __init__(self, name: str, alert_type: AlertType, severity: AlertSeverity, 
                 condition: Callable[[MetricsCollector], bool], message_template: str):
        self.name = name
        self.alert_type = alert_type
        self.severity = severity
        self.condition = condition
        self.message_template = message_template
        self.last_triggered = None
        self.cooldown_minutes = 60  # Default cooldown to prevent spam
    
    def should_trigger(self, metrics: MetricsCollector) -> bool:
        if self.cooldown_minutes and self.last_triggered:
            cooldown_until = self.last_triggered + timedelta(minutes=self.cooldown_minutes)
            if datetime.now() < cooldown_until:
                return False
        
        return self.condition(metrics)
    
    def create_alert(self, metrics: MetricsCollector) -> Alert:
        self.last_triggered = datetime.now()
        return Alert(
            alert_type=self.alert_type,
            severity=self.severity,
            title=f"{self.alert_type.value.upper()}: {self.name}",
            message=self._format_message(metrics),
            timestamp=datetime.now(),
            metadata={'rule_name': self.name}
        )
    
    def _format_message(self, metrics: MetricsCollector) -> str:
        # Simple message formatting - avoid complex template logic for now
        return self.message_template


class AlertManager:
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector
        self.alerts: List[Alert] = []
        self.rules: List[AlertRule] = []
        self.alert_handlers: List[Callable[[Alert], None]] = []
        
        # Configure default alert rules
        self._setup_default_rules()
        
        # Thresholds
        self.thresholds = {
            'failure_rate_percent': 10.0,
            'cost_daily_usd': 50.0,
            'cost_monthly_usd': 500.0,
            'error_rate_percent': 15.0,
            'failure_spike_multiplier': 2.0
        }
    
    def _setup_default_rules(self):
        """Configure default alerting rules."""
        
        # Failure spike detection
        self.add_rule(AlertRule(
            name="High Failure Rate",
            alert_type=AlertType.ERROR_RATE_HIGH,
            severity=AlertSeverity.ERROR,
            condition=lambda m: m.get_execution_metrics(hours=1)['failure_rate'] > self.thresholds['failure_rate_percent'],
            message_template=lambda m: "Failure rate is {failure_rate:.1f}% (threshold: {threshold}%)".format(
                failure_rate=m.get_execution_metrics(hours=1)['failure_rate'],
                threshold=self.thresholds['failure_rate_percent']
            )
        ))
        
        # Cost breach alerts
        self.add_rule(AlertRule(
            name="Daily Cost Breach",
            alert_type=AlertType.COST_BREACH,
            severity=AlertSeverity.WARNING,
            condition=lambda m: self._get_daily_cost(m) > self.thresholds['cost_daily_usd'],
            message_template=lambda m: "Daily cost ${:.2f} exceeds threshold ${:.2f}".format(
                self._get_daily_cost(m), self.thresholds['cost_daily_usd']
            )
        ))
        
        self.add_rule(AlertRule(
            name="Monthly Cost Breach",
            alert_type=AlertType.COST_BREACH,
            severity=AlertSeverity.CRITICAL,
            condition=lambda m: self._get_monthly_cost(m) > self.thresholds['cost_monthly_usd'],
            message_template=lambda m: "Monthly cost ${:.2f} exceeds threshold ${:.2f}".format(
                self._get_monthly_cost(m), self.thresholds['cost_monthly_usd']
            )
        ))
        
        # SLA miss alerts
        self.add_rule(AlertRule(
            name="CP1 SLA Miss",
            alert_type=AlertType.SLA_MISS,
            severity=AlertSeverity.WARNING,
            condition=lambda m: m.get_sla_attainment(hours=24)['cp1_sla_met'] < 90.0,
            message_template=lambda m: "CP1 SLA attainment is {:.1f}% (target: >90%)".format(
                m.get_sla_attainment(hours=24)['cp1_sla_met']
            )
        ))
        
        self.add_rule(AlertRule(
            name="CP2 SLA Miss",
            alert_type=AlertType.SLA_MISS,
            severity=AlertSeverity.WARNING,
            condition=lambda m: m.get_sla_attainment(hours=24)['cp2_sla_met'] < 90.0,
            message_template=lambda m: "CP2 SLA attainment is {:.1f}% (target: >90%)".format(
                m.get_sla_attainment(hours=24)['cp2_sla_met']
            )
        ))
        
        # Gmail cap violation
        self.add_rule(AlertRule(
            name="Gmail Cap Violation",
            alert_type=AlertType.CAP_VIOLATION,
            severity=AlertSeverity.ERROR,
            condition=lambda m: m.get_sla_attainment(hours=24)['gmail_cap_violations'] > 0,
            message_template=lambda m: "Gmail cap violations detected: {} violations".format(
                m.get_sla_attainment(hours=24)['gmail_cap_violations']
            )
        ))
        
        # Error rate alerts
        self.add_rule(AlertRule(
            name="High Error Rate",
            alert_type=AlertType.ERROR_RATE_HIGH,
            severity=AlertSeverity.ERROR,
            condition=lambda m: self._get_error_rate(m) > self.thresholds['error_rate_percent'],
            message_template=lambda m: "Error rate is {:.1f}% (threshold: {:.1f}%)".format(
                self._get_error_rate(m), self.thresholds['error_rate_percent']
            )
        ))
    
    def add_rule(self, rule: AlertRule):
        """Add a new alert rule."""
        self.rules.append(rule)
    
    def add_alert_handler(self, handler: Callable[[Alert], None]):
        """Add a handler for alert notifications (email, Slack, etc.)."""
        self.alert_handlers.append(handler)
    
    def check_alerts(self) -> List[Alert]:
        """Check all rules and return triggered alerts."""
        triggered_alerts = []
        
        for rule in self.rules:
            if rule.should_trigger(self.metrics):
                alert = rule.create_alert(self.metrics)
                triggered_alerts.append(alert)
                self.alerts.append(alert)
                
                # Notify handlers
                for handler in self.alert_handlers:
                    try:
                        handler(alert)
                    except Exception as e:
                        print(f"Alert handler failed: {e}")
        
        return triggered_alerts
    
    def get_active_alerts(self, severity: Optional[AlertSeverity] = None) -> List[Alert]:
        """Get unresolved alerts, optionally filtered by severity."""
        active = [a for a in self.alerts if not a.resolved]
        if severity:
            active = [a for a in active if a.severity == severity]
        return sorted(active, key=lambda a: a.timestamp, reverse=True)
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Mark an alert as resolved."""
        for alert in self.alerts:
            if str(id(alert)) == alert_id and not alert.resolved:
                alert.resolved = True
                alert.resolved_at = datetime.now()
                return True
        return False
    
    def get_alert_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get summary of recent alerts."""
        since = datetime.now() - timedelta(hours=hours)
        recent_alerts = [a for a in self.alerts if a.timestamp >= since]
        
        return {
            'total_alerts': len(recent_alerts),
            'active_alerts': len([a for a in recent_alerts if not a.resolved]),
            'by_severity': {
                severity.value: len([a for a in recent_alerts if a.severity == severity])
                for severity in AlertSeverity
            },
            'by_type': {
                alert_type.value: len([a for a in recent_alerts if a.alert_type == alert_type])
                for alert_type in AlertType
            }
        }
    
    def _get_daily_cost(self, metrics: MetricsCollector) -> float:
        """Calculate total cost for today."""
        cost_trends = metrics.get_cost_trends(days=1)
        total_cost = 0.0
        
        for metric_data in cost_trends.values():
            if metric_data:
                total_cost += sum(item['cost'] for item in metric_data)
        
        return total_cost
    
    def _get_monthly_cost(self, metrics: MetricsCollector) -> float:
        """Calculate total cost for current month."""
        cost_trends = metrics.get_cost_trends(days=30)
        total_cost = 0.0
        
        for metric_data in cost_trends.values():
            if metric_data:
                total_cost += sum(item['cost'] for item in metric_data)
        
        return total_cost
    
    def _get_error_rate(self, metrics: MetricsCollector) -> float:
        """Calculate current error rate."""
        return metrics.get_execution_metrics(hours=1)['failure_rate']
    
    # Default alert handlers
    @staticmethod
    def console_handler(alert: Alert):
        """Simple console alert handler."""
        timestamp = alert.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {alert.severity.value.upper()}: {alert.title}")
        print(f"  {alert.message}")
        if alert.metadata:
            print(f"  Metadata: {json.dumps(alert.metadata, indent=2)}")
        print("-" * 50)
    
    @staticmethod
    def log_handler(alert: Alert):
        """Log alert to file for persistence."""
        log_entry = {
            'timestamp': alert.timestamp.isoformat(),
            'type': alert.alert_type.value,
            'severity': alert.severity.value,
            'title': alert.title,
            'message': alert.message,
            'metadata': alert.metadata,
            'resolved': alert.resolved,
            'resolved_at': alert.resolved_at.isoformat() if alert.resolved_at else None
        }
        
        # In a real implementation, this would write to a log file or database
        print(f"ALERT_LOG: {json.dumps(log_entry)}")
