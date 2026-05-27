"use client";
import { motion } from "framer-motion";
import { ExternalLink, Github } from "lucide-react";

interface ProjectCardProps {
  title: string;
  description: string;
  tech: string[];
  link?: string;
  github?: string;
  index: number;
}

export default function ProjectCard({ title, description, tech, link, github, index }: ProjectCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: index * 0.1 }}
      viewport={{ once: true }}
      className="glass rounded-2xl p-6 hover:border-blue-500/50 transition-colors group relative overflow-hidden"
    >
      <div className="absolute top-0 right-0 p-4 flex gap-3">
        {github && (
          <a href={github} target="_blank" rel="noopener noreferrer" className="text-slate-400 hover:text-white transition-colors">
            <Github size={20} />
          </a>
        )}
        {link && (
          <a href={link} target="_blank" rel="noopener noreferrer" className="text-slate-400 hover:text-white transition-colors">
            <ExternalLink size={20} />
          </a>
        )}
      </div>
      
      <h3 className="text-xl font-bold font-display mb-3 text-blue-400 group-hover:text-blue-300 transition-colors">
        {title}
      </h3>
      <p className="text-slate-400 text-sm mb-6 leading-relaxed">
        {description}
      </p>
      
      <div className="flex flex-wrap gap-2">
        {tech.map((t) => (
          <span key={t} className="px-3 py-1 bg-blue-500/10 text-blue-300 text-xs rounded-full border border-blue-500/20">
            {t}
          </span>
        ))}
      </div>
    </motion.div>
  );
}
