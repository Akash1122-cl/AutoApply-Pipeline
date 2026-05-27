"use client";
import { motion } from "framer-motion";
import { Github, Linkedin, Mail, ArrowRight, Brain, Rocket, ChartBar, Layout } from "lucide-react";
import ProjectCard from "@/components/ProjectCard";
import ExperienceItem from "@/components/ExperienceItem";

export default function Home() {
  const projects = [
    {
      title: "AutoApply: Autonomous AI Job Pipeline",
      description: "A production-grade, multi-agent AI pipeline automating the APM job application lifecycle. Orchestrates Llama 3.3 and Gemini to scrape roles, extract JDs, and generate ATS-optimized CVs.",
      tech: ["Python", "Gemini 2.0", "Llama 3.3", "Playwright", "AsyncIO"],
      github: "https://github.com/Akash1122-cl/AutoApply-Pipeline"
    },
    {
      title: "Weekly Review Pulse",
      description: "Automated insight engine for fintech products. Clusters App Store/Google Play reviews using embeddings and generates stakeholder reports delivered via MCP-powered Google Workspace integrations.",
      tech: ["Clustering (HDBSCAN)", "LLM Summarization", "MCP", "Google APIs"],
    },
    {
      title: "Mutual Fund FAQ Assistant",
      description: "Trust-enforced RAG chatbot designed with PM constraint thinking. Refuses investment advice and strictly adheres to official source links (AMC, SEBI) with concise responses.",
      tech: ["RAG", "Vector Search", "Prompt Engineering", "FinTech"],
    }
  ];

  const experience = [
    {
      role: "Business & Product Coach",
      company: "Quantum Leap Learning Solutions",
      period: "Mar 2024 – Present",
      points: [
        "Owned end-to-end product discovery across 50+ client businesses.",
        "Drove ₹92 crore cumulative revenue improvement via funnel optimization (20–60% uplift).",
        "Improved top-of-funnel acquisition by 200–300% using Google Analytics and Meta Ads data.",
        "Designed KRAs, KPIs, and SOPs to reduce owner dependency and improve operational efficiency."
      ]
    },
    {
      role: "Revenue Growth Specialist",
      company: "GrowthSchool",
      period: "Jul 2022 – Mar 2024",
      points: [
        "Generated ₹1.4 Cr revenue and improved program outcomes by 30% through in-depth market research.",
        "Consulted 100+ early-stage founders on product-market fit validation and distribution strategy."
      ]
    },
    {
      role: "Founder & Product Leader",
      company: "Apnaaashiyana (PropTech)",
      period: "2019 – 2021",
      points: [
        "Built consumer-facing PropTech product from 0 to ₹40L revenue in 2 years.",
        "Optimized conversion by 110% by pivoting business model based on qualitative customer feedback."
      ]
    }
  ];

  const skillCategories = [
    { title: "Product", icon: <Rocket className="w-5 h-5" />, skills: ["Discovery", "GTM Strategy", "Roadmapping", "JTBD", "Funnel Optimization"] },
    { title: "AI & Engineering", icon: <Brain className="w-5 h-5" />, skills: ["Multi-Agent Systems", "LLMs", "RAG", "Python", "Prompt Engineering"] },
    { title: "Data", icon: <ChartBar className="w-5 h-5" />, skills: ["SQL", "Google Analytics", "Meta Ads", "Airtable"] },
    { title: "Design", icon: <Layout className="w-5 h-5" />, skills: ["Figma", "Wireframing", "Cross-functional Coordination"] }
  ];

  return (
    <main className="max-w-6xl mx-auto px-6 py-20">
      {/* Hero Section */}
      <section className="mb-32">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="max-w-3xl"
        >
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-sm font-medium mb-8">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
            </span>
            Available for AI-Product Roles
          </div>
          <h1 className="text-5xl md:text-7xl font-bold font-display tracking-tight mb-8">
            Akash <span className="text-gradient">Mishra</span>
          </h1>
          <p className="text-xl text-slate-400 leading-relaxed mb-10">
            Product-driven growth strategist with <span className="text-slate-100 font-medium">6+ years scaling 100+ businesses</span>. 
            Currently engineering AI-powered automation products to bridge the gap between business strategy and technical execution.
          </p>
          <div className="flex flex-wrap gap-4">
            <a href="mailto:akash.mishr44@gmail.com" className="px-8 py-4 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-bold transition-all flex items-center gap-2 glow">
              Get in Touch <ArrowRight size={18} />
            </a>
            <div className="flex gap-4">
              <a href="https://linkedin.com/in/akash-mishra00001" target="_blank" className="p-4 glass rounded-xl hover:text-blue-400 transition-colors">
                <Linkedin size={24} />
              </a>
              <a href="https://github.com/Akash1122-cl" target="_blank" className="p-4 glass rounded-xl hover:text-blue-400 transition-colors">
                <Github size={24} />
              </a>
            </div>
          </div>
        </motion.div>
      </section>

      {/* Stats Highlight */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-32">
        {[
          { label: "Experience", value: "6+ Years" },
          { label: "Revenue Impact", value: "₹92Cr+" },
          { label: "Businesses Scaled", value: "100+" }
        ].map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            viewport={{ once: true }}
            className="glass rounded-2xl p-8 text-center"
          >
            <div className="text-3xl font-bold font-display text-blue-400 mb-2">{stat.value}</div>
            <div className="text-slate-500 uppercase tracking-widest text-xs font-bold">{stat.label}</div>
          </motion.div>
        ))}
      </section>

      {/* Projects Section */}
      <section id="projects" className="mb-32">
        <div className="flex justify-between items-end mb-12">
          <div>
            <h2 className="text-3xl font-bold font-display mb-4">Project Spotlight</h2>
            <p className="text-slate-400">Innovative AI products built with a product-first mindset.</p>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {projects.map((p, i) => (
            <ProjectCard key={p.title} {...p} index={i} />
          ))}
        </div>
      </section>

      {/* Experience & Skills Section */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-16">
        <div className="lg:col-span-2">
          <h2 className="text-3xl font-bold font-display mb-12">Career Journey</h2>
          <div className="space-y-4">
            {experience.map((exp, i) => (
              <ExperienceItem key={exp.company} {...exp} index={i} />
            ))}
          </div>
        </div>
        
        <div>
          <h2 className="text-3xl font-bold font-display mb-12">Toolkit</h2>
          <div className="space-y-8">
            {skillCategories.map((cat, i) => (
              <motion.div
                key={cat.title}
                initial={{ opacity: 0, x: 20 }}
                whileInView={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.1 }}
                viewport={{ once: true }}
              >
                <div className="flex items-center gap-3 text-slate-100 font-bold mb-4">
                  <span className="p-2 bg-blue-500/10 rounded-lg text-blue-400">{cat.icon}</span>
                  {cat.title}
                </div>
                <div className="flex flex-wrap gap-2">
                  {cat.skills.map((skill) => (
                    <span key={skill} className="px-3 py-1 bg-slate-900 border border-slate-800 text-slate-400 text-sm rounded-lg">
                      {skill}
                    </span>
                  ))}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="mt-40 pt-12 border-t border-slate-900 flex flex-col md:flex-row justify-between items-center gap-8 text-slate-500 text-sm">
        <p>© {new Date().getFullYear()} Akash Mishra. Built with Next.js & Framer Motion.</p>
        <div className="flex gap-8">
          <a href="mailto:akash.mishr44@gmail.com" className="hover:text-blue-400 transition-colors flex items-center gap-2">
            <Mail size={16} /> Email
          </a>
          <a href="https://linkedin.com/in/akash-mishra00001" target="_blank" className="hover:text-blue-400 transition-colors flex items-center gap-2">
            <Linkedin size={16} /> LinkedIn
          </a>
        </div>
      </footer>
    </main>
  );
}
