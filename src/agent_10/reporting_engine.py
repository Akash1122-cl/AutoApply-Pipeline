"""
Reporting Engine — Phase 10

Generates the Daily Summary Report with integrated observability data.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from src.shared.run_logger import RunLogger
from src.observability.metrics_collector import MetricsCollector
from src.observability.alerts import AlertManager
from src.orchestrator.recovery_service import RecoveryService


class ReportingEngine:
    def __init__(self, logger: RunLogger, sheets: Any, 
                 metrics_collector: Optional[MetricsCollector] = None,
                 alert_manager: Optional[AlertManager] = None):
        self.logger = logger
        self.sheets = sheets
        self.metrics = metrics_collector or MetricsCollector()
        self.alerts = alert_manager or AlertManager(self.metrics)
        self.recovery_service = RecoveryService(sheets, logger)

    def generate_daily_report(self) -> str:
        """
        Creates an enhanced daily report with cost, SLA, and recovery metrics.
        """
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # 1. Aggregate Discovery Metrics
        new_jobs = self.logger.get_count("jobs_discovered")
        qualified = self.logger.get_count("jobs_qualified")
        
        # 2. Aggregate Pipeline Metrics
        contacts = self.logger.get_count("contacts_found") # Needs adding to agents
        cvs = self.logger.get_count("cvs_generated")
        ats_pass_1 = self.logger.get_count("ats_pass_first_try")
        ats_pass_rev = self.logger.get_count("ats_pass_after_revision")
        
        # 3. Aggregate Execution Metrics
        apps = self.logger.get_count("applications_submitted")
        emails = self.logger.get_count("emails_sent")
        linkedin = self.logger.get_count("linkedin_dms_sent")
        
        # 4. Fetch Manual Queues
        manual_rows = self.sheets.get_rows_by_status("MANUAL_QUEUE")
        human_review_rows = self.sheets.get_rows_by_status("HUMAN_REVIEW")
        
        # 5. Aggregate Responses
        replies = self.logger.get_count("responses_tracked")
        
        # 6. Get Cost and SLA Metrics
        cost_data = self._get_daily_cost_summary()
        sla_data = self.metrics.get_sla_attainment(24)
        recovery_data = self.recovery_service.get_recovery_queue_report()
        alert_summary = self.alerts.get_alert_summary(24)
        
        # 7. Get Performance Metrics
        execution_metrics = self.metrics.get_execution_metrics(24)
        pipeline_throughput = self.metrics.get_pipeline_throughput(24)

        # 8. Build the enhanced report
        lines = [
            f"AutoApply Daily Report — {now_str}",
            "================================",
            "",
            "DISCOVERY",
            f"  New jobs found:               {new_jobs}",
            f"  In shortlist (score >= 60):   {qualified}   <- awaiting your review at CP1",
            "",
            "PIPELINE",
            f"  Contacts found:               {contacts}",
            f"  CVs tailored:                 {cvs}",
            f"  ATS passed (1st attempt):     {ats_pass_1}",
            f"  ATS passed (after revision):  {ats_pass_rev}",
            f"  Success rate:                 {execution_metrics['success_rate']:.1f}%",
            "",
            "EXECUTION",
            f"  Applications submitted:       {apps}",
            f"  Cold emails sent:             {emails}",
            f"  LinkedIn DMs sent:            {linkedin}",
            f"  Manual queue (needs you):     {len(manual_rows)}",
            "",
            "RESPONSES",
            f"  New replies in inbox:         {replies}   <- details in tracker",
            "",
            "COST & BUDGET",
            f"  Today's cost:                 ${cost_data['daily_total']:.2f}",
            f"  Weekly cost:                  ${cost_data['weekly_total']:.2f}",
            f"  Monthly projection:           ${cost_data['monthly_projection']:.2f}",
            "",
            "SLA COMPLIANCE",
            f"  CP1 digest on-time:           {sla_data['cp1_sla_met']:.1f}%",
            f"  CP2 digest on-time:           {sla_data['cp2_sla_met']:.1f}%",
            f"  Human decision SLA:           {sla_data['human_decision_sla_met']:.1f}%",
            f"  Gmail cap violations:         {sla_data['gmail_cap_violations']}",
            "",
            "SYSTEM HEALTH",
            f"  Active alerts:                {alert_summary['active_alerts']}",
            f"  Failed rows:                  {recovery_data['failed_rows_count']}",
            f"  Human review queue:           {recovery_data['human_review_count']}",
            "",
            "ATTENTION NEEDED",
            f"  Human review queue:           {len(human_review_rows)}   <- ATS failed 2x or errors",
            "",
        ]

        # Add failure patterns if any
        if recovery_data['failure_patterns']:
            lines.append("FAILURE PATTERNS")
            for pattern, count in recovery_data['failure_patterns'].items():
                lines.append(f"  {pattern}: {count}")
            lines.append("")
        
        # Add manual queue details
        if manual_rows:
            lines.append("MANUAL QUEUE")
            for row in manual_rows[:5]: # Cap at 5
                lines.append(f"  {row.get('company')} — {row.get('role_title')} — {row.get('job_url')}")
            if len(manual_rows) > 5:
                lines.append(f"  ... and {len(manual_rows)-5} more")
            lines.append("")
        
        # Add critical alerts
        critical_alerts = self.alerts.get_active_alerts()
        if critical_alerts:
            lines.append("CRITICAL ALERTS")
            for alert in critical_alerts[:3]: # Cap at 3
                lines.append(f"  {alert.title}: {alert.message}")
            if len(critical_alerts) > 3:
                lines.append(f"  ... and {len(critical_alerts)-3} more")
            lines.append("")
        
        lines.append("================================")
        
        return "\n".join(lines)
    
    def generate_executive_summary(self) -> Dict[str, Any]:
        """
        Generate JSON-formatted executive summary for dashboards.
        """
        now = datetime.now()
        
        # Get all metrics
        pipeline_data = self.metrics.get_pipeline_throughput(24)
        execution_data = self.metrics.get_execution_metrics(24)
        sla_data = self.metrics.get_sla_attainment(24)
        cost_data = self._get_daily_cost_summary()
        recovery_data = self.recovery_service.get_recovery_queue_report()
        alert_summary = self.alerts.get_alert_summary(24)
        
        # Calculate health score
        health_score = 100.0
        if execution_data['success_rate'] < 90:
            health_score -= 10
        if sla_data['cp1_sla_met'] < 90:
            health_score -= 15
        if alert_summary['active_alerts'] > 5:
            health_score -= 10
        
        health_status = "healthy" if health_score >= 80 else "degraded" if health_score >= 60 else "critical"
        
        return {
            "timestamp": now.isoformat(),
            "summary_period": "24h",
            "health_score": max(0, health_score),
            "health_status": health_status,
            "key_metrics": {
                "jobs_processed": pipeline_data.get("jobs_discovered", 0),
                "applications_submitted": pipeline_data.get("applications_submitted", 0),
                "success_rate": execution_data.get("success_rate", 0),
                "daily_cost": cost_data["daily_total"],
                "active_alerts": alert_summary["active_alerts"],
                "failed_rows": recovery_data["failed_rows_count"]
            },
            "sla_compliance": {
                "cp1": sla_data.get("cp1_sla_met", 0),
                "cp2": sla_data.get("cp2_sla_met", 0),
                "human_decisions": sla_data.get("human_decision_sla_met", 0)
            },
            "attention_items": {
                "manual_queue": len(self.sheets.get_rows_by_status("MANUAL_QUEUE")),
                "human_review": recovery_data["human_review_count"],
                "critical_alerts": len([a for a in self.alerts.get_active_alerts() if a.severity.value == "critical"])
            }
        }
    
    def _get_daily_cost_summary(self) -> Dict[str, float]:
        """
        Get cost summary for reporting.
        """
        cost_trends = self.metrics.get_cost_trends(7)
        
        daily_total = 0.0
        weekly_total = 0.0
        
        # Calculate daily total
        for metric_data in cost_trends.values():
            if metric_data:
                today_data = [item for item in metric_data if item['date'] == datetime.now().strftime('%Y-%m-%d')]
                daily_total += sum(item['cost'] for item in today_data)
                weekly_total += sum(item['cost'] for item in metric_data)
        
        # Simple monthly projection (weekly average * 4.3)
        monthly_projection = weekly_total * 4.3 if weekly_total > 0 else daily_total * 30
        
        return {
            "daily_total": daily_total,
            "weekly_total": weekly_total,
            "monthly_projection": monthly_projection
        }
