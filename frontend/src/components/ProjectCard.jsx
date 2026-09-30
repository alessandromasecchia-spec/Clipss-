import { mediaUrl } from "@/lib/api";
import { formatDuration, formatDate } from "@/lib/format";
import { Play, Trash2, Clapperboard, Clock } from "lucide-react";
import { motion } from "framer-motion";

export const ProjectCard = ({ project, onOpen, onDelete, index = 0 }) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      data-testid={`project-card-${project.id}`}
      className="group relative bg-[#1A1D26] border border-white/10 rounded-xl overflow-hidden hover:border-cyan-500/40 transition-all shadow-xl shadow-black/40"
    >
      <button onClick={() => onOpen(project)} className="block w-full text-left" data-testid={`project-open-${project.id}`}>
        <div className="relative aspect-video bg-black overflow-hidden">
          <img
            src={mediaUrl(`/media/thumb/${project.id}`)}
            alt={project.name}
            className="w-full h-full object-cover opacity-90 group-hover:opacity-100 group-hover:scale-105 transition-all duration-300"
            onError={(e) => { e.currentTarget.style.display = "none"; }}
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent" />
          <div className="absolute top-2 right-2 flex items-center gap-1 bg-black/70 backdrop-blur rounded-md px-2 py-0.5 text-[11px] font-mono text-slate-200">
            <Clock size={11} /> {formatDuration(project.duration)}
          </div>
          <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
            <div className="w-12 h-12 rounded-full bg-cyan-500 flex items-center justify-center shadow-lg shadow-cyan-500/30">
              <Play className="w-5 h-5 text-slate-950 fill-slate-950 ml-0.5" />
            </div>
          </div>
        </div>
        <div className="p-3.5">
          <p className="font-semibold text-slate-100 truncate text-sm">{project.name}</p>
          <div className="flex items-center justify-between mt-1.5 text-xs text-slate-400">
            <span>{formatDate(project.created_at)}</span>
            <span className="inline-flex items-center gap-1 text-cyan-400/90 font-mono">
              <Clapperboard size={12} /> {project.clip_count} clip
            </span>
          </div>
        </div>
      </button>
      <button
        onClick={(e) => { e.stopPropagation(); onDelete(project); }}
        data-testid={`project-delete-${project.id}`}
        className="absolute top-2 left-2 w-8 h-8 rounded-lg bg-black/60 backdrop-blur border border-white/10 flex items-center justify-center text-slate-300 hover:text-rose-400 hover:border-rose-500/40 opacity-0 group-hover:opacity-100 transition-all"
        title="Elimina progetto"
      >
        <Trash2 size={15} />
      </button>
    </motion.div>
  );
};

export default ProjectCard;
