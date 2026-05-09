# 🚀 AutoApply Dashboard: Deployment Guide

Your premium observability dashboard is ready! It provides a real-time, high-end visual interface to monitor your AI agents, track costs, and view daily success reports.

## 💻 Local Deployment (Quick Start)

To run the dashboard on your local machine:

1. **Run the Script**: Double-click `start_dashboard.bat` in the root directory.
2. **Access UI**: Open your browser and navigate to:
   [http://localhost:8000](http://localhost:8000)

---

## ☁️ Cloud Deployment (Live on Web)

If you want to access your dashboard from anywhere, I recommend using **Render** (for the FastAPI backend) or **Vercel**.

### 1. Deploying on Render (Recommended for FastAPI)
1. **Connect GitHub**: Push your code to a GitHub repository.
2. **Create Web Service**:
   - **Environment**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn src.web.app:app --host 0.0.0.0 --port $PORT`
3. **Environment Variables**: Add all variables from your `.env` file to the Render Dashboard (under "Environment").

### 2. Deploying on Vercel
1. Install the Vercel CLI: `npm i -g vercel`
2. Run `vercel` in the root directory.
3. Vercel will automatically detect the FastAPI app (ensure you have a `vercel.json` if needed, but modern Vercel handles it via Python Runtimes).

---

## 🎨 Dashboard Features

- **Glassmorphism Design**: High-end translucent UI with smooth gradients.
- **Real-time Metrics**: Fetches data from the most recent `logs/run-*.json` file.
- **Alert Monitoring**: Visual indicators for pipeline failures or rate limits.
- **Executive Reports**: View the full text of your daily AI-generated summaries directly in the browser.
- **Auto-Refresh**: Syncs data every 30 seconds to keep you updated.

---

## 🛠️ Troubleshooting

- **"ModuleNotFoundError: fastapi"**: Run `pip install -r requirements.txt` to ensure all web dependencies are installed.
- **"Port 8000 already in use"**: You can change the port in `src/web/app.py` line 291 or via the `--port` flag in the start command.
- **Empty Dashboard**: The dashboard reads from `logs/run-*.json`. Ensure the orchestrator has completed at least one run (`python -m src.orchestrator.main --once`) to generate data.
