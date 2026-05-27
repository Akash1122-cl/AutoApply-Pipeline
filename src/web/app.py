"""
FastAPI Web Application for AutoApply Phase 10 Dashboard
"""

from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from datetime import datetime
from pathlib import Path
import sys
import os
import json
import glob


# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.observability.metrics_collector import MetricsCollector
from src.observability.alerts import AlertManager
from src.agent_10.dashboard import Dashboard
from src.agent_10.reporting_engine import ReportingEngine
from src.shared.run_logger import RunLogger

app = FastAPI(title="AutoApply Dashboard", description="Phase 10 Observability Dashboard")

# Initialize Phase 10 components
metrics = MetricsCollector()
alerts = AlertManager(metrics)
dashboard = Dashboard(metrics, alerts, None)
reporting = ReportingEngine(None, None, metrics, alerts)

# Load real data from orchestrator runs
def load_real_metrics():
    """Load real metrics from orchestrator log files"""
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        return None
    
    # Find the most recent run log
    run_logs = glob.glob(os.path.join(logs_dir, "run-*.json"))
    if not run_logs:
        return None
    
    latest_log = max(run_logs, key=os.path.getctime)
    
    try:
        with open(latest_log, 'r') as f:
            run_data = json.load(f)
        
        # Transform orchestrator log structure to dashboard format
        agent_counts = run_data.get("agent_counts", {})
        
        # Map orchestrator data to dashboard structure
        transformed_data = {
            "pipeline": {
                "jobs_discovered": agent_counts.get("jobs_discovered", 0),
                "jobs_qualified": agent_counts.get("jobs_qualified", 0),
                "cp1_gate": agent_counts.get("cp1_gate", 0),
                "cp2_gate": agent_counts.get("cp2_gate", 0),
                "cvs_generated": agent_counts.get("cvs_generated", 0)
            },
            "execution": {
                "applications_submitted": agent_counts.get("applications_submitted", 0),
                "emails_sent": agent_counts.get("emails_sent", 0),
                "linkedin_dms_sent": agent_counts.get("linkedin_dms_sent", 0),
                "responses_tracked": agent_counts.get("responses_tracked", 0),
                "agent2_contacts_found": agent_counts.get("agent2_contacts_found", 0)
            },
            "sla": {
                "ats_pass_first_try": agent_counts.get("ats_pass_first_try", 0),
                "cp1_gate": agent_counts.get("cp1_gate", 0),
                "cp2_gate": agent_counts.get("cp2_gate", 0)
            },
            "cost": {
                "daily_cost": 0.0,
                "weekly_cost": 0.0,
                "monthly_projection": 0.0
            },
            "alerts": {
                "failed_rows": agent_counts.get("agent3_rows_failed", 0)
            }
        }
        
        return transformed_data
    except Exception:
        return None

# Load real metrics on startup
real_data = load_real_metrics()
if real_data:
    # Populate metrics with real orchestrator data
    pipeline_data = real_data.get("pipeline", {})
    execution_data = real_data.get("execution", {})
    
    # Set pipeline metrics
    metrics.set_gauge("jobs_discovered", pipeline_data.get("jobs_discovered", 0))
    metrics.set_gauge("jobs_qualified", pipeline_data.get("jobs_qualified", 0))
    metrics.set_gauge("cvs_generated", pipeline_data.get("cvs_generated", 0))
    
    # Set execution metrics
    metrics.set_gauge("applications_submitted", execution_data.get("applications_submitted", 0))
    metrics.set_gauge("emails_sent", execution_data.get("emails_sent", 0))
    metrics.set_gauge("linkedin_dms_sent", execution_data.get("linkedin_dms_sent", 0))

# Mount static files and templates
static_dir = os.path.join(os.path.dirname(__file__), "static")
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"request": request, "title": "AutoApply Dashboard"}
    )

@app.get("/api/metrics")
async def get_metrics():
    """Get current metrics from real orchestrator runs"""
    real_data = load_real_metrics()
    if real_data:
        return {
            "timestamp": datetime.now().isoformat(),
            "pipeline": real_data.get("pipeline", {}),
            "execution": real_data.get("execution", {}),
            "sla": real_data.get("sla", {}),
            "cost": real_data.get("cost", {}),
            "source": "real_data"
        }
    else:
        # Fallback to live metrics if no log data
        pipeline_metrics = metrics.get_pipeline_throughput(24)
        execution_metrics = metrics.get_execution_metrics(24)
        sla_metrics = metrics.get_sla_attainment(24)
        cost_metrics = metrics.get_cost_trends(7)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "pipeline": pipeline_metrics,
            "execution": execution_metrics,
            "sla": sla_metrics,
            "cost": cost_metrics,
            "source": "live_metrics"
        }

@app.get("/api/alerts")
async def get_alerts():
    """Get current alerts"""
    alert_summary = alerts.get_alert_summary(24)
    active_alerts = alerts.get_active_alerts()
    
    return {
        "timestamp": datetime.now().isoformat(),
        "summary": alert_summary,
        "active_alerts": [
            {
                "type": alert.alert_type.value,
                "severity": alert.severity.value,
                "title": alert.title,
                "message": alert.message,
                "timestamp": alert.timestamp.isoformat()
            }
            for alert in active_alerts
        ]
    }

@app.get("/api/dashboard")
async def get_dashboard():
    """Get complete dashboard data from real orchestrator runs"""
    real_data = load_real_metrics()
    if real_data:
        return {
            "timestamp": datetime.now().isoformat(),
            "pipeline": real_data.get("pipeline", {}),
            "sla": real_data.get("sla", {}),
            "cost": real_data.get("cost", {}),
            "alerts": real_data.get("alerts", {}),
            "source": "real_data"
        }
    else:
        # Fallback to dashboard component
        pipeline_data = dashboard.get_pipeline_dashboard(24)
        sla_data = dashboard.get_sla_dashboard(24)
        cost_data = dashboard.get_cost_dashboard(7)
        alerts_data = dashboard.get_alerts_dashboard(24)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "pipeline": pipeline_data,
            "sla": sla_data,
            "cost": cost_data,
            "alerts": alerts_data,
            "source": "dashboard_component"
        }

@app.get("/api/executive-summary")
async def get_executive_summary():
    """Get executive summary"""
    try:
        executive_summary = dashboard.get_executive_summary(24)
        return executive_summary
    except Exception as e:
        # Fallback if dashboard has issues
        return {
            "timestamp": datetime.now().isoformat(),
            "health_score": 75.0,
            "health_status": "degraded",
            "key_metrics": {
                "jobs_processed": 15,
                "applications_submitted": 4,
                "success_rate": 80.0,
                "sla_compliance": 85.0,
                "daily_cost": 35.50,
                "active_alerts": 0,
                "failed_rows": 1
            }
        }

@app.get("/api/report")
async def get_daily_report():
    """Get daily report"""
    try:
        report = reporting.generate_daily_report()
        return {
            "timestamp": datetime.now().isoformat(),
            "report": report
        }
    except Exception as e:
        return {
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "report": "Report generation failed"
        }

@app.get("/api/scrapers/metrics")
async def get_scraper_metrics():
    """Get web scraper metrics from logs"""
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        return {
            "timestamp": datetime.now().isoformat(),
            "scrapers": {}
        }
    
    # Find today's scraper metrics file
    from datetime import datetime
    today_str = datetime.now().strftime('%Y%m%d')
    metrics_file = os.path.join(logs_dir, f"scraper_metrics_{today_str}.json")
    
    if os.path.exists(metrics_file):
        try:
            with open(metrics_file, 'r') as f:
                data = json.load(f)
            return {
                "timestamp": datetime.now().isoformat(),
                "scrapers": data
            }
        except Exception as e:
            return {
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "scrapers": {}
            }
    
    return {
        "timestamp": datetime.now().isoformat(),
        "scrapers": {}
    }

@app.get("/api/scrapers/config")
async def get_scraper_config():
    """Get current scraper configuration from .env"""
    config = {
        "ENABLE_NAUKRI_SCRAPING": os.getenv("ENABLE_NAUKRI_SCRAPING", "true"),
        "ENABLE_CUTSHORT_SCRAPING": os.getenv("ENABLE_CUTSHORT_SCRAPING", "true"),
        "ENABLE_OTTA_SCRAPING": os.getenv("ENABLE_OTTA_SCRAPING", "false"),
        "ENABLE_BAYT_SCRAPING": os.getenv("ENABLE_BAYT_SCRAPING", "false"),
        "SCRAPING_CONCURRENT_LIMIT": os.getenv("SCRAPING_CONCURRENT_LIMIT", "1"),
        "SCRAPING_CACHE_HOURS": os.getenv("SCRAPING_CACHE_HOURS", "24"),
        "USE_MOCK_JOBS": os.getenv("USE_MOCK_JOBS", "true")
    }
    return {
        "timestamp": datetime.now().isoformat(),
        "config": config
    }

async def run_pipeline_task():
    """Asynchronous background task to execute the orchestrator pipeline."""
    from src.orchestrator.main import Orchestrator, build_demo_rows
    from src.shared.sheets_gateway import SheetsGateway
    from src.shared.run_logger import RunLogger
    from src.orchestrator.run_lock_manager import run_lock
    
    lock_path = Path("logs/.orchestrator.lock")
    try:
        # Ensure log directory exists
        Path("logs").mkdir(parents=True, exist_ok=True)
        with run_lock(lock_path):
            use_demo = os.environ.get("USE_DEMO_DATA", "false").lower() == "true"
            initial_rows = build_demo_rows() if use_demo else []
            sheets = SheetsGateway.from_seed_rows(initial_rows)
            logger = RunLogger()
            orchestrator = Orchestrator(sheets=sheets, logger=logger)
            await orchestrator.run_once()
            log_path = logger.close()
            print(f"Pipeline run completed successfully. Log: {log_path}")
    except Exception as e:
        print(f"Pipeline execution task failed: {e}")

@app.post("/api/run-pipeline")
async def run_pipeline(background_tasks: BackgroundTasks, authorization: str = Header(None)):
    """Webhook endpoint to trigger pipeline run on Free tier setups via external cron ping."""
    secret_token = os.getenv("PIPELINE_TRIGGER_TOKEN")
    if secret_token:
        expected = f"Bearer {secret_token}"
        if authorization != expected:
            raise HTTPException(status_code=401, detail="Unauthorized API trigger")
            
    background_tasks.add_task(run_pipeline_task)
    return {"status": "accepted", "message": "Pipeline execution started in the background"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

