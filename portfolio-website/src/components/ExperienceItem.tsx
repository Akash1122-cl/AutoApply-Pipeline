"use client";
import { motion } from "framer-motion";

interface ExperienceItemProps {
  role: string;
  company: string;
  period: string;
  points: string[];
  index: number;
}

export default function ExperienceItem({ role, company, period, points, index }: ExperienceItemProps) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      whileInView={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.5, delay: index * 0.1 }}
      viewport={{ once: true }}
      className="relative pl-8 pb-12 border-l border-slate-800 last:pb-0"
    >
      <div className="absolute left-[-5px] top-1.5 w-2.5 h-2.5 rounded-full bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.5)]" />
      
      <div className="flex flex-col md:flex-row md:justify-between md:items-baseline gap-1 mb-4">
        <h3 className="text-lg font-bold font-display text-slate-100">{role}</h3>
        <span className="text-sm font-medium text-blue-400">{period}</span>
      </div>
      
      <p className="text-slate-300 font-medium mb-3">{company}</p>
      
      <ul className="space-y-2">
        {points.map((point, i) => (
          <li key={i} className="text-slate-400 text-sm leading-relaxed flex gap-2">
            <span className="text-blue-500 mt-1.5 shrink-0 w-1 h-1 rounded-full bg-blue-500" />
            {point}
          </li>
        ))}
      </ul>
    </motion.div>
  );
}
