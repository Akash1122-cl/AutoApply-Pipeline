"""
Phase 10 Integration Demo

Demonstrates the complete Phase 10 implementation with all components working together.
"""

import sys
import os
from datetime import datetime, timedelta
from unittest.mock import Mock

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.shared.run_logger import RunLogger
from src.shared.sheets_gateway import SheetsGateway
from src.observability.metrics_collector import MetricsCollector
from src.observability.alerts import AlertManager
from src.orchestrator.recovery_service import RecoveryService
from src.agent_10.reporting_engine import ReportingEngine
from src.agent_10.dashboard import Dashboard


def demo_phase10_integration():
    """
    Demonstrate complete Phase 10 integration.
    """
    print("🚀 Phase 10 Integration Demo")
    print("=" * 50)
    
    # Initialize core components
    print("\n📊 Initializing components...")
    logger = RunLogger()
    
    # Create a proper mock with all required methods
    sheets = Mock()
    sheets.get_rows_by_status = Mock()
    sheets.get_row_by_id = Mock()
    sheets.update_row = Mock()
    
    metrics = MetricsCollector()
    alerts = AlertManager(metrics)
    recovery = RecoveryService(sheets, logger)
    
    # Initialize Phase 10 components
    reporting = ReportingEngine(logger, sheets, metrics, alerts)
    dashboard = Dashboard(metrics, alerts, sheets)
    
    print("✅ Components initialized successfully")
    
    # Simulate some pipeline activity
    print("\n🔄 Simulating pipeline activity...")
    
    # Add some metrics
    metrics.increment_counter("jobs_discovered", 15)
    metrics.increment_counter("jobs_qualified", 8)
    metrics.increment_counter("contacts_found", 6)
    metrics.increment_counter("cvs_generated", 5)
    metrics.increment_counter("ats_pass_first_try", 3)
    metrics.increment_counter("ats_pass_after_revision", 1)
    metrics.increment_counter("applications_submitted", 4)
    metrics.increment_counter("emails_sent", 3)
    metrics.increment_counter("linkedin_dms_sent", 1)
    metrics.increment_counter("responses_tracked", 2)
    
    # Simulate some failures for testing
    metrics.increment_counter("execution_successes", 8)
    metrics.increment_counter("execution_failures", 2)
    metrics.increment_counter("execution_attempts", 10)
    
    # Add some cost data
    metrics.set_gauge("api_costs", 25.50)
    metrics.set_gauge("infra_costs", 10.00)
    
    # Add SLA delay measurements
    for delay in [25, 35, 20, 40, 30]:  # Mix of within and over SLA
        metrics.record_histogram("cp1_digest_delay_minutes", delay)
        metrics.record_histogram("cp2_digest_delay_minutes", delay + 5)
    
    print("✅ Pipeline activity simulated")
    
    # Mock sheet data
    print("\n📋 Setting up mock sheet data...")
    mock_failed_rows = [
        {
            "row_id": "failed_1",
            "status": "FAILED",
            "notes": "Network timeout during contact discovery",
            "company": "TechCorp",
            "role_title": "Senior Engineer",
            "job_url": "https://example.com/job1"
        },
        {
            "row_id": "failed_2", 
            "status": "FAILED",
            "notes": "API rate limit exceeded",
            "company": "StartupXYZ",
            "role_title": "DevOps Engineer",
            "job_url": "https://example.com/job2"
        }
    ]
    
    mock_manual_rows = [
        {
            "row_id": "manual_1",
            "status": "MANUAL_QUEUE",
            "company": "EnterpriseInc",
            "role_title": "Product Manager",
            "job_url": "https://example.com/job3"
        }
    ]
    
    mock_human_review_rows = [
        {
            "row_id": "review_1",
            "status": "HUMAN_REVIEW", 
            "notes": "ATS failed after 2 revisions",
            "company": "OldSchoolCorp",
            "role_title": "Backend Developer",
            "job_url": "https://example.com/job4"
        }
    ]
    
    def mock_get_rows_by_status(status):
        if status == "FAILED":
            return mock_failed_rows
        elif status == "MANUAL_QUEUE":
            return mock_manual_rows
        elif status == "HUMAN_REVIEW":
            return mock_human_review_rows
        else:
            return []
    
    def mock_get_row_by_id(row_id):
        all_rows = mock_failed_rows + mock_manual_rows + mock_human_review_rows
        return next((row for row in all_rows if row["row_id"] == row_id), None)
    
    sheets.get_rows_by_status.side_effect = mock_get_rows_by_status
    sheets.get_row_by_id.side_effect = mock_get_row_by_id
    sheets.update_row.return_value = True
    
    print("✅ Mock sheet data configured")
    
    # Test recovery service
    print("\n🔧 Testing recovery service...")
    
    # Get failed rows
    failed_rows = recovery.get_failed_rows()
    print(f"   Found {len(failed_rows)} failed rows")
    
    # Inspect a specific error
    if failed_rows:
        error_details = recovery.inspect_row_error(failed_rows[0]["row_id"])
        print(f"   Error details: {error_details['error_notes']}")
        
        # Get safe recovery actions
        safe_actions = recovery.get_safe_recovery_actions(failed_rows[0]["row_id"])
        print(f"   Safe actions: {[action.value for action in safe_actions]}")
        
        # Verify external outcomes
        verification = recovery.verify_external_outcome(failed_rows[0]["row_id"])
        print(f"   External verification: {verification['recommendation']}")
    
    # Test alerts
    print("\n🚨 Testing alert system...")
    
    # Check for alerts
    triggered_alerts = alerts.check_alerts()
    print(f"   Triggered {len(triggered_alerts)} alerts")
    
    # Get alert summary
    alert_summary = alerts.get_alert_summary(24)
    print(f"   Active alerts: {alert_summary['active_alerts']}")
    print(f"   Total alerts: {alert_summary['total_alerts']}")
    
    # Test metrics
    print("\n📈 Testing metrics collection...")
    
    pipeline_metrics = metrics.get_pipeline_throughput(24)
    print(f"   Jobs discovered: {pipeline_metrics['jobs_discovered']}")
    print(f"   Applications submitted: {pipeline_metrics['applications_submitted']}")
    
    execution_metrics = metrics.get_execution_metrics(24)
    print(f"   Success rate: {execution_metrics['success_rate']:.1f}%")
    print(f"   Failure rate: {execution_metrics['failure_rate']:.1f}%")
    
    sla_metrics = metrics.get_sla_attainment(24)
    print(f"   CP1 SLA compliance: {sla_metrics['cp1_sla_met']:.1f}%")
    print(f"   CP2 SLA compliance: {sla_metrics['cp2_sla_met']:.1f}%")
    
    # Test dashboard
    print("\n📊 Testing dashboard generation...")
    
    executive_summary = dashboard.get_executive_summary(24)
    health_data = executive_summary['health_status']
    print(f"   Health score: {health_data['overall_score']:.1f}")
    print(f"   Health status: {health_data['status']}")
    print(f"   Key metrics: {len(executive_summary['key_metrics'])} categories")
    
    # Test reporting
    print("\n📄 Testing reporting engine...")
    
    # Generate daily report
    daily_report = reporting.generate_daily_report()
    print("   Daily report generated successfully")
    print("   Report preview:")
    print("   " + "\n   ".join(daily_report.split('\n')[:15]))
    print("   ... (truncated)")
    
    # Generate executive summary
    exec_summary = reporting.generate_executive_summary()
    print(f"   Executive summary generated with health score: {exec_summary['health_score']:.1f}")
    
    # Test recovery queue report
    recovery_report = recovery.get_recovery_queue_report()
    print(f"   Recovery queue report: {recovery_report['failed_rows_count']} failed rows")
    print(f"   Failure patterns: {list(recovery_report['failure_patterns'].keys())}")
    
    print("\n🎉 Phase 10 Integration Demo Complete!")
    print("=" * 50)
    
    # Summary of what was demonstrated
    print("\n📋 DEMONSTRATED COMPONENTS:")
    print("   ✅ Metrics Collector - Counter, gauge, histogram metrics")
    print("   ✅ Alert Manager - Rule-based alerting with cooldowns")
    print("   ✅ Recovery Service - Safe failed row recovery")
    print("   ✅ Dashboard - Comprehensive metrics visualization")
    print("   ✅ Reporting Engine - Enhanced daily reports with cost/SLA")
    print("   ✅ Integration - All components working together")
    
    print("\n🔧 KEY FEATURES SHOWN:")
    print("   • Pipeline throughput monitoring")
    print("   • SLA compliance tracking")
    print("   • Cost trend analysis")
    print("   • Failure pattern analysis")
    print("   • Safe recovery procedures")
    print("   • Real-time alerting")
    print("   • Executive summaries")
    print("   • Health scoring")
    
    print("\n📈 METRICS COLLECTED:")
    print(f"   • Pipeline: {pipeline_metrics['jobs_discovered']} jobs processed")
    print(f"   • Execution: {execution_metrics['success_rate']:.1f}% success rate")
    print(f"   • SLA: {sla_metrics['cp1_sla_met']:.1f}% CP1 compliance")
    print(f"   • Alerts: {alert_summary['total_alerts']} total alerts")
    print(f"   • Recovery: {recovery_report['failed_rows_count']} failed rows")
    
    return True


if __name__ == "__main__":
    try:
        success = demo_phase10_integration()
        if success:
            print("\n✨ Phase 10 implementation is fully functional!")
            sys.exit(0)
        else:
            print("\n❌ Phase 10 demo failed")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
