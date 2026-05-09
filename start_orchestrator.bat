@echo off
echo Starting AutoApply Orchestrator Daemon...
echo Time: %TIME%
echo Trigger: 9:00 AM IST

REM Check for virtual environment
if exist venv\Scripts\activate (
    call venv\Scripts\activate
) else (
    echo WARNING: Virtual environment not found. Running with global python.
)

REM Run the orchestrator in daemon mode
python -m src.orchestrator.main --daemon

pause
