import { Progress } from "@/components/ui/progress";
import { Loader2, CheckCircle2, Clock3, XCircle, Cpu } from "lucide-react";
import { formatDuration } from "@/lib/format";

const STATUS = {
  queued: { icon: Clock3, cls: "text-slate-400", label: "In coda" },
  processing: { icon: Loader2, cls: "text-cyan-400 animate-spin", label: "Elaborazione" },
  verifying: { icon: Loader2, cls: "text-amber-400 animate-spin", label: "Verifica" },
  uploading: { icon: Loader2, cls: "text-sky-400 animate-spin", label: "Caricamento" },
  ready: { icon: CheckCircle2, cls: "text-emerald-400", label: "Pronta" },
  completed: { icon: CheckCircle2, cls: "text-emerald-400", label: "Completata" },
  failed: { icon: XCircle, cls: "text-rose-400", label: "Errore" },
};

export const ExportQueue = ({ job }) => {
  if (!job) return null;
  const clips = job.clips || [];

  return (
    <div className="max-w-2xl mx-auto">
      <div className="bg-[#1A1D26] border border-white/10 rounded-xl p-6 shadow-xl shadow-black/40">
        <div className="flex items-center gap-3 mb-1">
          <Cpu className="text-cyan-400" size={20} />
          <h2 className="font-display text-xl font-bold text-slate-100">Elaborazione in corso</h2>
        </div>
        <p className="text-sm text-slate-400 mb-5" data-testid="job-stage">{job.stage}</p>

        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-slate-300 font-medium">Elaborazione</span>
          <span className="font-mono text-cyan-400 font-semibold" data-testid="job-progress-text">{job.progress}%</span>
        </div>
        <Progress value={job.progress} className="h-2.5" data-testid="job-progress-bar" />

        <div className="mt-6 space-y-2.5">
          {clips.length === 0 && (
            <p className="text-sm text-slate-500 text-center py-4">Preparazione delle clip…</p>
          )}
          {clips.map((c) => {
            const s = STATUS[c.status] || STATUS.queued;
            return (
              <div key={c.index} data-testid={`queue-clip-${c.index}`}
                className="flex items-center gap-3 bg-[#13161C] border border-white/10 rounded-lg px-3.5 py-3">
                <s.icon size={18} className={s.cls} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-slate-100 font-medium truncate">Clip {c.index + 1}
                    <span className="text-slate-500 font-mono text-xs ml-2">{formatDuration(c.start)}–{formatDuration(c.end)}</span>
                  </p>
                  {c.title && <p className="text-xs text-slate-500 truncate">{c.title}</p>}
                  {c.status === "failed" && c.error && <p className="text-xs text-rose-400 truncate">{c.error}</p>}
                </div>
                <div className="text-right shrink-0">
                  <span className={`text-xs font-medium ${s.cls.replace("animate-spin", "")}`}>{s.label}</span>
                  {c.status === "processing" && <p className="font-mono text-xs text-cyan-400">{c.progress}%</p>}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default ExportQueue;
