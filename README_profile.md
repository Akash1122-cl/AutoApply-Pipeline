# 🚀 AutoApply: Autonomous APM Job Application Pipeline

> **A production-grade, multi-agent AI pipeline that automates the job application lifecycle. Built to treat my career hunt as my most important product.**

## 📖 The Story

### 1️⃣ The Problem: The "Black Hole" of Job Applications
Like many aspiring Product Managers, I found myself stuck in a repetitive and exhausting cycle: scouring multiple job boards, manually copying Job Descriptions, and spending 45+ minutes tailoring a single CV. Despite the effort, most applications disappeared into an ATS "black hole," resulting in a high-effort, low-yield process that drained energy away from actual interview preparation.

### 2️⃣ The Root Cause: Human Bandwidth as a Bottleneck
I realized this wasn't just a job search problem—it was a workflow and scalability problem. Generic applications get ignored by recruiters, but hyper-personalizing every application is physically impossible for a single human at scale. The root cause was treating job hunting as a manual chore rather than an automated, data-driven system. I needed to remove the human bandwidth bottleneck while maintaining the quality of a highly tailored application.

### 3️⃣ The Solution: An AI-Powered Orchestrator
To solve this, I built **AutoApply**, a multi-agent AI pipeline that acts as my personal research and drafting department. 
- **The System:** A state-machine orchestrator governing specialized AI agents that interact through a Google Sheets State Layer.
- **The Process:** It autonomously scrapes high-value roles across India, Europe, and SEA. It then leverages LLMs (Llama-3.3 and Gemini 2.0) to extract the core requirements from the Job Description and dynamically tailors my Master PDF Resume into a role-specific story.
- **Human-in-the-Loop:** It ends at a centralized dashboard, ensuring I am always the "Gatekeeper" who makes the final decision to hit "Send" while preventing AI hallucinations.

### 4️⃣ Impact on My Job Hunt: Speed Meets Precision
AutoApply completely transformed my job hunt from a manual grind into a scalable operation. 
- **10x Velocity:** When I wake up, the system has already analyzed 30+ global MNC roles.
- **Quality at Scale:** By 9:00 AM, my dashboard is filled with highly tailored CVs and drafted emails. 
- **Result:** It drastically increased my application velocity while improving the personalization of each CV, allowing me to focus 100% of my time on networking and interview prep rather than data entry.

---
### 🛠️ Core Tech Stack
*   **LLMs:** Groq (Llama-3.3-70B), Google Gemini 2.0 Flash
*   **Backend:** Python 3.12, AsyncIO
*   **Storage/State:** Google Sheets API, Google Drive API, Local .docx generation
*   **Automation:** Playwright, BeautifulSoup
