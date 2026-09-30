import { mediaUrl, API } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Download, Pencil, CheckCircle2, XCircle, Archive, PartyPopper, FileText } from "lucide-react";
import { formatDuration } from "@/lib/format";
import { motion } from "framer-motion";

export const ClipResults = ({ project, job, onEdit }) => {
  const clips = (job.clips || []).filter((c) => c.status === "completed");
  const failed = (job.clips || []).filter((c) => c.status === "failed");

  const download = (c) => {
    const a = document.createElement("a");
    a.href = mediaUrl(`/media/clip/${project.id}/${c.filename}?dl=1`);
    a.download = c.filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  const downloadAll = () => {
    const a = document.createElement("a");
    a.href = mediaUrl(`/media/zip/${project.id}`);
    document.body.appendChild(a); a.click(); a.remove();
  };

  const exportCaptions = (fmt) => {
    const a = document.createElement("a");
    a.href = `${API}/projects/${project.id}/captions?fmt=${fmt}&words=${job.settings?.subtitle_style?.max_words_per_line || 5}`;
    document.body.appendChild(a); a.click(); a.remove();
  };

  const onVideoError = (e) => {
    const v = e.currentTarget;
    if (v.dataset.retried) return;
    v.dataset.retried = "1";
    const base = v.src.split("?")[0];
    setTimeout(() => { v.src = `${base}?r=${Date.now()}`; v.load(); }, 800);
  };

  return (
    <div>
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center">
            <PartyPopper className="text-emerald-400" size={22} />
          </div>
          <div>
            <h2 className="font-display text-2xl font-bold text-slate-100" data-testid="results-title">
              {clips.length > 0 ? `${clips.length} clip pronte` : "Nessuna clip generata"}
            </h2>
            <p className="text-sm text-slate-400">Formato {job.settings.aspect_ratio} · MP4 / H.264 / AAC</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1.5 bg-[#1A1D26] border border-white/10 rounded-lg px-2 py-1.5">
            <FileText size={14} className="text-cyan-400" />
            <span className="text-xs text-slate-400 mr-1">Sottotitoli:</span>
            {["srt", "vtt", "txt"].map((f) => (
              <button key={f} onClick={() => exportCaptions(f)} data-testid={`caption-export-${f}`}
                className="text-xs font-semibold uppercase text-slate-200 hover:text-cyan-300 px-1.5">{f}</button>
            ))}
          </div>
          {clips.length > 1 && (
            <Button onClick={downloadAll} data-testid="download-all-btn"
              className="bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold shadow-lg shadow-cyan-500/20">
              <Archive size={17} className="mr-1.5" /> Scarica tutte le clip (.zip)
            </Button>
          )}
        </div>
      </div>

      {failed.length > 0 && (
        <div className="mb-5 flex items-start gap-2 bg-rose-500/10 border border-rose-500/20 rounded-lg px-4 py-3 text-sm text-rose-300">
          <XCircle size={16} className="mt-0.5 shrink-0" />
          <span>{failed.length} clip non sono state generate. {failed[0]?.error}</span>
        </div>
      )}

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
        {clips.map((c, i) => (
          <motion.div key={c.index}
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}
            data-testid={`result-clip-${c.index}`}
            className="bg-[#1A1D26] border border-white/10 rounded-xl overflow-hidden shadow-xl shadow-black/40">
            <div className="bg-black flex items-center justify-center max-h-80">
              <video src={mediaUrl(`/media/clip/${project.id}/${c.filename}`)} controls preload="metadata"
                onError={onVideoError}
                className={`w-full ${job.settings.aspect_ratio === "9:16" ? "max-h-80 object-contain" : ""}`}
                data-testid={`result-video-${c.index}`} />
            </div>
            <div className="p-3.5">
              <div className="flex items-center gap-2 mb-1">
                <CheckCircle2 size={15} className="text-emerald-400" />
                <p className="font-semibold text-slate-100 text-sm">Clip {c.index + 1}</p>
                <span className="ml-auto font-mono text-xs text-slate-500">{formatDuration(c.end - c.start)}</span>
              </div>
              {c.title && <p className="text-xs text-slate-500 truncate mb-3">{c.title}</p>}
              <div className="flex gap-2">
                <Button onClick={() => download(c)} data-testid={`download-clip-${c.index}`}
                  className="flex-1 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold h-9">
                  <Download size={15} className="mr-1.5" /> Scarica
                </Button>
                <Button onClick={() => onEdit(c)} variant="secondary" data-testid={`edit-clip-${c.index}`}
                  className="bg-slate-800 hover:bg-slate-700 border border-white/10 h-9">
                  <Pencil size={15} className="mr-1.5" /> Modifica
                </Button>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
};

export default ClipResults;
