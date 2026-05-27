# 🚀 AutoApply Dashboard: Deployment Guide

Your premium observability dashboard is ready! It provides a real-time, high-end visual interface to monitor your AI agents, track costs, and view daily success reports.

## 💻 Local Deployment (Quick Start)

To run the dashboard on your local machine:

1. **Run the Script**: Double-click `start_dashboard.bat` in the root directory.
2. **Access UI**: Open your browser and navigate to:
   [http://localhost:8000](http://localhost:8000)

---

## ☁️ Cloud Deployment (Live on Web)

Depending on your budget, choose one of the following deployment paths:

---

### Option A: Free Tier Deployment (FastAPI Web Service + External Cron Ping) ⭐ (Recommended for $0/mo)

Render's Free tier does not support persistent disks and spins down web services after 15 minutes of inactivity (killing background daemon loops). To run the scheduler daily for free:

1. **Deploy to Render (Web Service)**:
   - Go to [Render Dashboard](https://dashboard.render.com) and click **New +** > **Web Service**.
   - Connect your GitHub repository.
   - **Name**: `autoapply-pipeline`
   - **Environment**: `Python`
   - **Build Command**: `bash ./build.sh`
   - **Start Command**: `uvicorn src.web.app:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: Free ($0/mo)

2. **Add Environment Variables**:
   Under the **Environment** tab on Render, add all keys and values from your local `.env` file.
   - **Security Key**: Add a custom variable `PIPELINE_TRIGGER_TOKEN` with a strong random string (e.g. `my-super-secret-key`) to prevent unauthorized triggers.

3. **Set Up the Free Cron Trigger**:
   - Go to [cron-job.org](https://cron-job.org/) (a completely free cron scheduling service).
   - Create a new cron job:
     * **Title**: `AutoApply Daily Trigger`
     * **URL**: `https://YOUR_RENDER_SERVICE_URL.onrender.com/api/run-pipeline`
     * **Request Method**: `POST`
     * **Schedule**: Once a day (e.g. 9:00 AM IST / 03:30 AM UTC).
     * **Request Headers**: Add `Authorization` with value `Bearer YOUR_PIPELINE_TRIGGER_TOKEN_VALUE`
   - *Result*: The cron job will ping your webhook daily. This boots up the free Render container, triggers the orchestrator in the background, runs the full job discovery/apply pipeline, and spins down automatically.

---

### Option B: Paid Tier Deployment (Render Blueprint Setup - $7+/mo)

If you have a paid plan, you can use the automated Blueprint configuration with a persistent disk.

1. Go to [Render Dashboard](https://dashboard.render.com) and click **New +** > **Blueprint**.
2. Connect your GitHub repository.
3. Render will read the `render.yaml` file to configure the unified service (`autoapply-pipeline`), the start command (`bash ./start.sh`), and the persistent disk (`pipeline-data`) automatically.
4. Copy all keys and values from your local `.env` file to the Render environment dashboard.

---

### Option C: Deploying on Vercel (Dashboard Only)
1. Install the Vercel CLI: `npm i -g vercel`
2. Run `vercel` in the root directory.
3. Vercel will automatically detect the FastAPI app using the `vercel.json` runtime configuration. (Note: The background scheduler will *not* run on Vercel; Vercel is only for the web dashboard interface).


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
