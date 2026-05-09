# 🚀 AutoApply: Autonomous APM Job Application Pipeline

> **AutoApply is a production-grade, multi-agent AI pipeline automating the APM job application lifecycle. It leverages Llama 3.3 and Gemini to scrape global roles, extract JDs, and generate ATS-optimized CVs from a master PDF. Features a human-in-the-loop orchestrator for high-intent, scalable applications across India, Europe, and SEA.**

---

## 📖 The Story: Turning the Job Hunt into a Product

### 📍 The Problem: The "Black Hole" of Job Applications
Like every aspiring Product Manager, I found myself stuck in the same repetitive cycle: Scouring five different job boards, manually copying Job Descriptions, and spending 45 minutes tailoring a single CV, only to send it into a "black hole" and never hear back. 

As a PM, I realized: **This wasn't a job search problem; it was a workflow problem.** The manual effort was a bottleneck to my reach, and the "generic" nature of applications was a bottleneck to my success. 

### 💡 The Inspiration: "What if I was the Orchestrator?"
I decided to treat my career as my most important product. I didn't want a "bot" that would spam recruiters; I wanted a **team of specialized AI agents** that would act as my personal research and drafting department. 

I sat down and mapped out the "Ideal Workflow":
1.  **The Scout**: Finds high-value roles across India, Europe, and SEA.
2.  **The Researcher**: Extracts the raw truth from the Job Description.
3.  **The Writer**: Tailors my master experience into a role-specific story.
4.  **The Gatekeeper**: Ensures I am always the one to hit "Send."

### 🛠️ The Build: Challenges and Pivots
The journey wasn't easy. I hit the "Great Wall of LinkedIn" (their anti-scraping system) and had to pivot to an **AI-powered search layer** that could "think" like a human researcher. I ran into **API rate limits** that threatened to stall my progress, so I engineered a multi-provider system that could flip between **Llama 3.3 and Gemini 2.0** on the fly. 

I even faced a moment where my Google Drive quota was maxed out—so I built a **Local Failover System** that ensured my work was never lost, saving every tailored CV to a synced local archive instead.

### 🚀 The Result: Speed Meets Precision
Today, **AutoApply** isn't just a script; it’s a living ecosystem. 
*   When I wake up, the system has already analyzed **30+ global MNC roles**.
*   While I drink my coffee, it has read a **Google APM** job description and matched it against my **Master PDF Resume**.
*   By 9:00 AM, I have a **Dashboard (Google Sheet)** filled with tailored CVs and drafted emails, waiting for my final "Human Action."

---

## 🧠 Core Logic & Architecture
The system is built on a **State-Machine Orchestrator** pattern, governing 5 specialized agents that interact through a shared **Google Sheets State Layer**.

### 1. The Orchestrator (The "Brain")
*   **Logic**: Enforces deterministic state transitions (e.g., a job cannot be "Applied" until the CV is "Approved").
*   **Safety**: Implemented exponential backoff for API rate limits and incremental commits.

### 2. Multi-Region Discovery Agent
*   **Logic**: Uses a hybrid of RSS Scraping and AI-Powered Web Search to target **India, Europe, and SEA**.

### 3. LLM-Powered Personalization
*   **Logic**: Dynamically tailors CVs using **Llama 3.3 (Groq)** and **Gemini 2.0**, with a custom "Fabrication Guard" to prevent hallucinations.

---

## 🛠️ Tech Stack
*   **LLMs**: Groq (Llama-3.3-70B), Google Gemini 2.0 Flash
*   **Backend**: Python 3.12, AsyncIO
*   **Storage**: Google Sheets API, Google Drive API, Local .docx generation
*   **Automation**: Playwright, BeautifulSoup
