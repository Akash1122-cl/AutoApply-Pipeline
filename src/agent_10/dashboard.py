"""
Dashboard Module — Phase 10

Provides dashboards and aggregates for pipeline metrics visualization.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import json

from src.observability.metrics_collector import MetricsCollector
from src.observability.alerts import AlertManager
from src.shared.sheets_gateway import SheetsGateway


class Dashboard:
    def __init__(self, metrics_collector: MetricsCollector, alert_manager: AlertManager, sheets: SheetsGateway):
        self.metrics = metrics_collector
        self.alerts = alert_manager
        self.sheets = sheets
    
    def get_pipeline_dashboard(self, hours: int = 24) -> Dict[str, Any]:
        """Get comprehensive pipeline dashboard data."""
        return {
            "title": "Pipeline Dashboard",
            "timeframe": f"Last {hours} hours",
            "last_updated": datetime.now().isoformat(),
            "metrics": {
                "throughput": self.metrics.get_pipeline_throughput(hours),
                "ats_outcomes": self.metrics.get_ats_outcomes(hours),
                "execution": self.metrics.get_execution_metrics(hours)
            },
            "status_breakdown": self._get_status_breakdown(),
            "trend_data": self._get_trend_data(hours),
            "bottlenecks": self._identify_bottlenecks(hours)
        }
    
    def get_sla_dashboard(self, hours: int = 24) -> Dict[str, Any]:
        """Get SLA monitoring dashboard."""
        sla_data = self.metrics.get_sla_attainment(hours)
        
        return {
            "title": "SLA Dashboard",
            "timeframe": f"Last {hours} hours",
            "last_updated": datetime.now().isoformat(),
            "sla_metrics": sla_data,
            "sla_targets": {
                "cp1_digest_delay_minutes": 30,
                "cp2_digest_delay_minutes": 30,
                "human_decision_hours": 24,
                "gmail_cap_daily": 20
            },
            "compliance_scores": self._calculate_sla_compliance_scores(sla_data),
            "violations": self._get_sla_violations(hours)
        }
    
    def get_cost_dashboard(self, days: int = 7) -> Dict[str, Any]:
        """Get cost monitoring dashboard."""
        cost_trends = self.metrics.get_cost_trends(days)
        
        return {
            "title": "Cost Dashboard",
            "timeframe": f"Last {days} days",
            "last_updated": datetime.now().isoformat(),
            "daily_costs": self._format_cost_trends(cost_trends),
            "cost_breakdown": self._get_cost_breakdown(days),
            "cost_forecast": self._forecast_costs(days),
            "budget_utilization": self._calculate_budget_utilization(days)
        }
    
    def get_quality_dashboard(self, hours: int = 24) -> Dict[str, Any]:
        """Get quality and performance dashboard."""
        return {
            "title": "Quality Dashboard",
            "timeframe": f"Last {hours} hours",
            "last_updated": datetime.now().isoformat(),
            "quality_metrics": {
                "ats_scores": self._get_ats_score_distribution(hours),
                "fit_scores": self._get_fit_score_distribution(hours),
                "content_quality": self._assess_content_quality(hours)
            },
            "error_analysis": {
                "error_rates": self._get_error_rates(hours),
                "failure_patterns": self._get_failure_patterns(hours),
                "recovery_success": self._get_recovery_metrics(hours)
            },
            "performance_indicators": self._get_performance_indicators(hours)
        }
    
    def get_alerts_dashboard(self, hours: int = 24) -> Dict[str, Any]:
        """Get alert monitoring dashboard."""
        alert_summary = self.alerts.get_alert_summary(hours)
        active_alerts = self.alerts.get_active_alerts()
        
        return {
            "title": "Alerts Dashboard",
            "timeframe": f"Last {hours} hours",
            "last_updated": datetime.now().isoformat(),
            "summary": alert_summary,
            "active_alerts": [
                {
                    "id": str(id(alert)),
                    "type": alert.alert_type.value,
                    "severity": alert.severity.value,
                    "title": alert.title,
                    "message": alert.message,
                    "timestamp": alert.timestamp.isoformat(),
                    "metadata": alert.metadata
                }
                for alert in active_alerts[:20]  # Limit to 20 most recent
            ],
            "alert_trends": self._get_alert_trends(hours),
            "escalation_status": self._get_escalation_status()
        }
    
    def get_recovery_dashboard(self) -> Dict[str, Any]:
        """Get recovery operations dashboard."""
        from src.orchestrator.recovery_service import RecoveryService
        
        recovery_service = RecoveryService(self.sheets, None)  # Logger not needed for dashboard
        recovery_report = recovery_service.get_recovery_queue_report()
        
        return {
            "title": "Recovery Dashboard",
            "last_updated": datetime.now().isoformat(),
            "queue_status": recovery_report,
            "recovery_actions": self._get_recovery_action_stats(),
            "success_metrics": self._get_recovery_success_metrics(),
            "recommended_priorities": self._prioritize_recovery_actions(recovery_report)
        }
    
    def get_executive_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get high-level executive summary."""
        pipeline_data = self.get_pipeline_dashboard(hours)
        sla_data = self.get_sla_dashboard(hours)
        cost_data = self.get_cost_dashboard(7)
        quality_data = self.get_quality_dashboard(hours)
        alerts_data = self.get_alerts_dashboard(hours)
        
        health_status = self._calculate_overall_health(pipeline_data, sla_data, alerts_data)
        return {
            "title": "Executive Summary",
            "timeframe": f"Last {hours} hours",
            "last_updated": datetime.now().isoformat(),
            "key_metrics": {
                "jobs_processed": pipeline_data["metrics"]["throughput"]["jobs_discovered"],
                "applications_submitted": pipeline_data["metrics"]["throughput"]["applications_submitted"],
                "success_rate": pipeline_data["metrics"]["execution"]["success_rate"],
                "sla_compliance": sla_data["compliance_scores"]["overall"],
                "daily_cost": cost_data["cost_breakdown"]["total_today"],
                "active_alerts": len(alerts_data["active_alerts"]),
                "failed_rows": recovery_report["failed_rows_count"] if (recovery_report := self._get_recovery_report()) else 0
            },
            "health_status": health_status,
            "attention_items": self._identify_attention_items(pipeline_data, sla_data, alerts_data),
            "trend_highlights": self._get_trend_highlights(pipeline_data, cost_data)
        }
    
    def _get_status_breakdown(self) -> Dict[str, int]:
        """Get current status breakdown of all rows."""
        statuses = [
            "SCRAPED", "SCORED", "AWAITING_HUMAN_REVIEW", "AWAITING_CONTENT_REVIEW",
            "CONTACT_DISCOVERY", "CONTENT_GENERATION", "ATS_REVIEW",
            "APPROVED_FOR_EXECUTION", "APPLIED", "OUTREACH_SENT", "MONITORING",
            "RESPONSE_RECEIVED", "FAILED", "HUMAN_REVIEW", "SKIPPED"
        ]
        
        breakdown = {}
        for status in statuses:
            rows = self.sheets.get_rows_by_status(status)
            breakdown[status] = len(rows)
        
        return breakdown
    
    def _get_trend_data(self, hours: int) -> Dict[str, List[Dict[str, Any]]]:
        """Get hourly trend data for key metrics."""
        trends = {}
        current_time = datetime.now()
        
        for hour_offset in range(hours):
            hour_time = current_time - timedelta(hours=hour_offset)
            hour_start = hour_time.replace(minute=0, second=0, microsecond=0)
            hour_end = hour_start + timedelta(hours=1)
            
            # This is a simplified version - in production, you'd query historical data
            pass
        
        return trends
    
    def _identify_bottlenecks(self, hours: int) -> List[Dict[str, Any]]:
        """Identify pipeline bottlenecks."""
        bottlenecks = []
        status_breakdown = self._get_status_breakdown()
        
        # Check for large queues at each checkpoint
        if status_breakdown.get("AWAITING_HUMAN_REVIEW", 0) > 20:
            bottlenecks.append({
                "checkpoint": "CP1 Human Review",
                "queue_size": status_breakdown["AWAITING_HUMAN_REVIEW"],
                "severity": "high",
                "recommendation": "Review pending items at CP1"
            })
        
        if status_breakdown.get("CP2_PENDING", 0) > 15:
            bottlenecks.append({
                "checkpoint": "CP2 Approval",
                "queue_size": status_breakdown["CP2_PENDING"],
                "severity": "medium",
                "recommendation": "Review and approve content at CP2"
            })
        
        if status_breakdown.get("FAILED", 0) > 10:
            bottlenecks.append({
                "checkpoint": "Failed Rows",
                "queue_size": status_breakdown["FAILED"],
                "severity": "high",
                "recommendation": "Address failed rows and implement recovery"
            })
        
        return bottlenecks
    
    def _calculate_sla_compliance_scores(self, sla_data: Dict[str, Any]) -> Dict[str, float]:
        """Calculate overall SLA compliance scores."""
        scores = {
            "cp1_compliance": sla_data.get("cp1_sla_met", 0),
            "cp2_compliance": sla_data.get("cp2_sla_met", 0),
            "human_decision_compliance": sla_data.get("human_decision_sla_met", 0),
            "gmail_compliance": 100.0 if sla_data.get("gmail_cap_violations", 0) == 0 else 0.0
        }
        
        scores["overall"] = sum(scores.values()) / len(scores)
        return scores
    
    def _get_sla_violations(self, hours: int) -> List[Dict[str, Any]]:
        """Get recent SLA violations."""
        violations = []
        
        # This would query actual violation data in production
        return violations
    
    def _format_cost_trends(self, cost_trends: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
        """Format cost trends for dashboard display."""
        return cost_trends
    
    def _get_cost_breakdown(self, days: int) -> Dict[str, Any]:
        """Get cost breakdown by category."""
        # Simplified implementation
        return {
            "api_costs": 0.0,
            "infra_costs": 0.0,
            "total_today": 0.0,
            "total_week": 0.0
        }
    
    def _forecast_costs(self, days: int) -> Dict[str, Any]:
        """Forecast costs for next period."""
        # Simplified forecasting based on recent trends
        return {
            "projected_daily": 0.0,
            "projected_weekly": 0.0,
            "projected_monthly": 0.0
        }
    
    def _calculate_budget_utilization(self, days: int) -> Dict[str, float]:
        """Calculate budget utilization percentages."""
        # Simplified implementation
        return {
            "daily_utilization": 0.0,
            "weekly_utilization": 0.0,
            "monthly_utilization": 0.0
        }
    
    def _get_ats_score_distribution(self, hours: int) -> Dict[str, Any]:
        """Get ATS score distribution."""
        # This would query actual ATS scores from the data
        return {
            "average": 0.0,
            "median": 0.0,
            "distribution": {
                "90-100": 0,
                "80-89": 0,
                "70-79": 0,
                "60-69": 0,
                "below_60": 0
            }
        }
    
    def _get_fit_score_distribution(self, hours: int) -> Dict[str, Any]:
        """Get job fit score distribution."""
        return {
            "average": 0.0,
            "median": 0.0,
            "distribution": {
                "90-100": 0,
                "80-89": 0,
                "70-79": 0,
                "60-69": 0,
                "below_60": 0
            }
        }
    
    def _assess_content_quality(self, hours: int) -> Dict[str, Any]:
        """Assess content quality metrics."""
        return {
            "cv_quality_score": 0.0,
            "email_quality_score": 0.0,
            "linkedin_quality_score": 0.0
        }
    
    def _get_error_rates(self, hours: int) -> Dict[str, float]:
        """Get error rates by component."""
        return {
            "agent_failures": 0.0,
            "api_failures": 0.0,
            "execution_failures": 0.0
        }
    
    def _get_failure_patterns(self, hours: int) -> Dict[str, int]:
        """Get failure patterns analysis."""
        return {
            "timeouts": 0,
            "api_errors": 0,
            "validation_errors": 0,
            "other": 0
        }
    
    def _get_recovery_metrics(self, hours: int) -> Dict[str, Any]:
        """Get recovery operation metrics."""
        return {
            "recovery_attempts": 0,
            "successful_recoveries": 0,
            "recovery_rate": 0.0
        }
    
    def _get_performance_indicators(self, hours: int) -> Dict[str, Any]:
        """Get key performance indicators."""
        return {
            "throughput_per_hour": 0.0,
            "avg_processing_time": 0.0,
            "pipeline_efficiency": 0.0
        }
    
    def _get_alert_trends(self, hours: int) -> Dict[str, List[int]]:
        """Get alert trends over time."""
        return {
            "hourly_counts": [],
            "severity_breakdown": {}
        }
    
    def _get_escalation_status(self) -> Dict[str, Any]:
        """Get current escalation status."""
        return {
            "critical_alerts": 0,
            "escalated_items": 0,
            "pending_escalations": 0
        }
    
    def _get_recovery_action_stats(self) -> Dict[str, int]:
        """Get recovery action statistics."""
        return {
            "retries": 0,
            "resets": 0,
            "manual_reviews": 0
        }
    
    def _get_recovery_success_metrics(self) -> Dict[str, Any]:
        """Get recovery success metrics."""
        return {
            "success_rate": 0.0,
            "avg_recovery_time": 0.0
        }
    
    def _prioritize_recovery_actions(self, recovery_report: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Prioritize recovery actions based on impact."""
        return []
    
    def _get_recovery_report(self) -> Optional[Dict[str, Any]]:
        """Get recovery report."""
        try:
            from src.orchestrator.recovery_service import RecoveryService
            recovery_service = RecoveryService(self.sheets, None)
            return recovery_service.get_recovery_queue_report()
        except Exception as e:
            return None
    
    def _calculate_overall_health(self, pipeline_data: Dict, sla_data: Dict, alerts_data: Dict) -> Dict[str, Any]:
        """Calculate overall system health score."""
        health_score = 100.0
        
        # Deduct points for issues
        if pipeline_data["metrics"]["execution"]["success_rate"] < 90:
            health_score -= 10
        
        if sla_data["compliance_scores"]["overall"] < 90:
            health_score -= 15
        
        if len(alerts_data["active_alerts"]) > 5:
            health_score -= 10
        
        return {
            "overall_score": max(0, health_score),
            "status": "healthy" if health_score >= 80 else "degraded" if health_score >= 60 else "critical",
            "key_factors": self._identify_health_factors(pipeline_data, sla_data, alerts_data)
        }
    
    def _identify_health_factors(self, pipeline_data: Dict, sla_data: Dict, alerts_data: Dict) -> List[str]:
        """Identify factors affecting system health."""
        factors = []
        
        if pipeline_data["metrics"]["execution"]["success_rate"] < 90:
            factors.append("Low execution success rate")
        
        if sla_data["compliance_scores"]["overall"] < 90:
            factors.append("SLA compliance issues")
        
        if len(alerts_data["active_alerts"]) > 5:
            factors.append("High number of active alerts")
        
        return factors
    
    def _identify_attention_items(self, pipeline_data: Dict, sla_data: Dict, alerts_data: Dict) -> List[Dict[str, Any]]:
        """Identify items requiring attention."""
        items = []
        
        # Add bottlenecks
        items.extend(pipeline_data.get("bottlenecks", []))
        
        # Add critical alerts
        critical_alerts = [a for a in alerts_data.get("active_alerts", []) if a["severity"] == "critical"]
        for alert in critical_alerts[:3]:  # Limit to top 3
            items.append({
                "type": "critical_alert",
                "title": alert["title"],
                "description": alert["message"],
                "severity": "critical"
            })
        
        return items
    
    def _get_trend_highlights(self, pipeline_data: Dict, cost_data: Dict) -> List[str]:
        """Get key trend highlights."""
        highlights = []
        
        # Add trend analysis here
        return highlights
