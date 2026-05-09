"""
Metrics Collector — Phase 10

Collects and aggregates operational metrics across the AutoApply pipeline.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class MetricType(Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


@dataclass
class MetricPoint:
    timestamp: datetime
    value: float
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class Metric:
    name: str
    metric_type: MetricType
    points: List[MetricPoint] = field(default_factory=list)
    
    def add_point(self, value: float, tags: Optional[Dict[str, str]] = None):
        point = MetricPoint(
            timestamp=datetime.now(),
            value=value,
            tags=tags or {}
        )
        self.points.append(point)
        
        # Keep only last 1000 points to prevent memory bloat
        if len(self.points) > 1000:
            self.points = self.points[-1000:]
    
    def get_latest(self) -> Optional[MetricPoint]:
        return self.points[-1] if self.points else None
    
    def get_sum(self, since: Optional[datetime] = None) -> float:
        if since:
            relevant_points = [p for p in self.points if p.timestamp >= since]
        else:
            relevant_points = self.points
        return sum(p.value for p in relevant_points)
    
    def get_average(self, since: Optional[datetime] = None) -> float:
        if since:
            relevant_points = [p for p in self.points if p.timestamp >= since]
        else:
            relevant_points = self.points
        return sum(p.value for p in relevant_points) / len(relevant_points) if relevant_points else 0.0


class MetricsCollector:
    def __init__(self):
        self.metrics: Dict[str, Metric] = {}
        self.sla_targets = {
            'cp1_digest_delay_minutes': 30,
            'cp2_digest_delay_minutes': 30,
            'human_decision_hours': 24,
            'gmail_daily_cap': 20
        }
        
    def _get_or_create_metric(self, name: str, metric_type: MetricType) -> Metric:
        if name not in self.metrics:
            self.metrics[name] = Metric(name, metric_type)
        return self.metrics[name]
    
    def increment_counter(self, name: str, value: float = 1.0, tags: Optional[Dict[str, str]] = None):
        metric = self._get_or_create_metric(name, MetricType.COUNTER)
        metric.add_point(value, tags)
    
    def set_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        metric = self._get_or_create_metric(name, MetricType.GAUGE)
        metric.add_point(value, tags)
    
    def record_histogram(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        metric = self._get_or_create_metric(name, MetricType.HISTOGRAM)
        metric.add_point(value, tags)
    
    def get_pipeline_throughput(self, hours: int = 24) -> Dict[str, float]:
        since = datetime.now() - timedelta(hours=hours)
        return {
            'jobs_discovered': self.metrics.get('jobs_discovered', Metric('', MetricType.COUNTER)).get_sum(since),
            'jobs_qualified': self.metrics.get('jobs_qualified', Metric('', MetricType.COUNTER)).get_sum(since),
            'contacts_found': self.metrics.get('contacts_found', Metric('', MetricType.COUNTER)).get_sum(since),
            'cvs_generated': self.metrics.get('cvs_generated', Metric('', MetricType.COUNTER)).get_sum(since),
            'applications_submitted': self.metrics.get('applications_submitted', Metric('', MetricType.COUNTER)).get_sum(since),
            'emails_sent': self.metrics.get('emails_sent', Metric('', MetricType.COUNTER)).get_sum(since),
            'linkedin_dms_sent': self.metrics.get('linkedin_dms_sent', Metric('', MetricType.COUNTER)).get_sum(since)
        }
    
    def get_ats_outcomes(self, hours: int = 24) -> Dict[str, float]:
        since = datetime.now() - timedelta(hours=hours)
        return {
            'ats_pass_first_try': self.metrics.get('ats_pass_first_try', Metric('', MetricType.COUNTER)).get_sum(since),
            'ats_pass_after_revision': self.metrics.get('ats_pass_after_revision', Metric('', MetricType.COUNTER)).get_sum(since),
            'ats_failures': self.metrics.get('ats_failures', Metric('', MetricType.COUNTER)).get_sum(since),
            'ats_score_avg': self.metrics.get('ats_score', Metric('', MetricType.HISTOGRAM)).get_average(since)
        }
    
    def get_execution_metrics(self, hours: int = 24) -> Dict[str, float]:
        since = datetime.now() - timedelta(hours=hours)
        return {
            'success_rate': self._calculate_success_rate(since),
            'failure_rate': self._calculate_failure_rate(since),
            'retry_rate': self.metrics.get('retry_attempts', Metric('', MetricType.COUNTER)).get_sum(since),
            'avg_execution_time': self.metrics.get('execution_time', Metric('', MetricType.HISTOGRAM)).get_average(since)
        }
    
    def get_cost_trends(self, days: int = 7) -> Dict[str, List[Dict[str, Any]]]:
        since = datetime.now() - timedelta(days=days)
        cost_metrics = ['api_costs', 'infra_costs', 'total_costs']
        trends = {}
        
        for metric_name in cost_metrics:
            metric = self.metrics.get(metric_name)
            if metric and metric.points:
                daily_costs = {}
                for point in metric.points:
                    if point.timestamp >= since:
                        date_key = point.timestamp.strftime('%Y-%m-%d')
                        daily_costs[date_key] = daily_costs.get(date_key, 0) + point.value
                
                trends[metric_name] = [
                    {'date': date, 'cost': cost}
                    for date, cost in sorted(daily_costs.items())
                ]
        
        return trends
    
    def get_sla_attainment(self, hours: int = 24) -> Dict[str, Any]:
        since = datetime.now() - timedelta(hours=hours)
        
        cp1_delays = self.metrics.get('cp1_digest_delay_minutes', Metric('', MetricType.HISTOGRAM))
        cp2_delays = self.metrics.get('cp2_digest_delay_minutes', Metric('', MetricType.HISTOGRAM))
        human_delays = self.metrics.get('human_decision_hours', Metric('', MetricType.HISTOGRAM))
        
        return {
            'cp1_sla_met': self._calculate_sla_compliance(cp1_delays, since, self.sla_targets['cp1_digest_delay_minutes']),
            'cp2_sla_met': self._calculate_sla_compliance(cp2_delays, since, self.sla_targets['cp2_digest_delay_minutes']),
            'human_decision_sla_met': self._calculate_sla_compliance(human_delays, since, self.sla_targets['human_decision_hours']),
            'gmail_cap_violations': self.metrics.get('gmail_cap_violations', Metric('', MetricType.COUNTER)).get_sum(since)
        }
    
    def get_failure_spikes(self, hours: int = 24) -> Dict[str, Any]:
        since = datetime.now() - timedelta(hours=hours)
        failure_metrics = ['agent_failures', 'api_failures', 'execution_failures']
        
        spikes = {}
        for metric_name in failure_metrics:
            metric = self.metrics.get(metric_name)
            if metric:
                recent_failures = metric.get_sum(since)
                baseline_failures = metric.get_sum(since - timedelta(hours=hours), since)
                
                # Simple spike detection: > 2x baseline
                spike_threshold = baseline_failures * 2
                spikes[metric_name] = {
                    'recent_count': recent_failures,
                    'baseline_count': baseline_failures,
                    'is_spike': recent_failures > spike_threshold,
                    'threshold': spike_threshold
                }
        
        return spikes
    
    def _calculate_success_rate(self, since: datetime) -> float:
        successes = self.metrics.get('execution_successes', Metric('', MetricType.COUNTER)).get_sum(since)
        total = self.metrics.get('execution_attempts', Metric('', MetricType.COUNTER)).get_sum(since)
        return (successes / total * 100) if total > 0 else 0.0
    
    def _calculate_failure_rate(self, since: datetime) -> float:
        failures = self.metrics.get('execution_failures', Metric('', MetricType.COUNTER)).get_sum(since)
        total = self.metrics.get('execution_attempts', Metric('', MetricType.COUNTER)).get_sum(since)
        return (failures / total * 100) if total > 0 else 0.0
    
    def _calculate_sla_compliance(self, metric: Metric, since: datetime, target: float) -> float:
        if not metric.points:
            return 100.0
        
        relevant_points = [p for p in metric.points if p.timestamp >= since]
        if not relevant_points:
            return 100.0
        
        compliant_count = sum(1 for p in relevant_points if p.value <= target)
        return (compliant_count / len(relevant_points) * 100) if relevant_points else 100.0
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        return {
            'pipeline_throughput': self.get_pipeline_throughput(),
            'ats_outcomes': self.get_ats_outcomes(),
            'execution_metrics': self.get_execution_metrics(),
            'cost_trends': self.get_cost_trends(),
            'sla_attainment': self.get_sla_attainment(),
            'failure_spikes': self.get_failure_spikes(),
            'last_updated': datetime.now().isoformat()
        }
