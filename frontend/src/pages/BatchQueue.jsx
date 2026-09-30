import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import Header from "@/components/Header";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, mediaUrl } from "@/lib/api";
import { formatDuration } from "@/lib/format";
import { UploadCloud, Loader2, CheckCircle2, Clock3, XCircle, Download, Play, Layers } from "lucide-react";

const TEMPLATE_PATCH = {
  podcast: { face_tracking: true, smart_zoom: "low", zoom_mode: "normal", silence_removal: "low", subtitle_preset: "bold" },
  talking_head: { face_tracking: true, smart_zoom: "medium", zoom_mode: "punch_in", silence_removal: "medium", subtitle_preset: "bold" },
  gaming: { face_tracking: false, smart_zoom: "high", zoom_mode: "punch_in", silence_removal: "low", subtitle_preset: "gaming" },
  minimal: { face_tracking: true, smart_zoom: "off", zoom_mode: "normal", silence_removal: "off", subtitle_preset: "minimal" },
};

const buildSettings = (template, aspect, numClips) => {
  const p = TEMPLATE_PATCH[template];
  return {
    aspect_ratio: aspect, clip_duration: 30, num_clips: numClips,
    subtitles: true, auto_crop: true, face_tracking: p.face_tracking, audio_normalize: true,
    auto_find: true, template,
    silence_removal: p.silence_removal, smart_zoom: p.smart_zoom, zoom_mode: p.zoom_mode,
    export_preset: "social_hq",
    subtitle_style: {
      preset: p.subtitle_preset, font: "DejaVu Sans", size: 66, color: "#FFFFFF",
      highlight_color: "#FFE600", background: false, bg_color: "#000000", shadow: true,
      outline: 4, bold: p.subtitle_preset !== "minimal", position: "bottom", alignment: "center",
      max_words_per_line: 4, word_highlight: template === "gaming",
    },
  };
};

const STATUS = {
  idle: { icon: Clock3, cls: "text-slate-500", label: "In attesa" },
  uploading: { icon: Loader2, cls: "text-cyan-400 animate-spin", label: "Caricamento" },
  queued: { icon: Clock3, cls: "text-slate-400", label: "In coda" },
  processing: { icon: Loader2, cls: "text-cyan-400 animate-spin", label: "Elaborazione" },
  completed: { icon: CheckCircle2, cls: "text-emerald-400", label: "Completato" },
  failed: { icon: XCircle, cls: "text-rose-400", label: "Errore" },
};

export default function BatchQueue() {
  const navigate = useNavigate();
  const inputRef = useRef(null);
  const [items, setItems] = useState([]); // {key, name, projectId, status, jobId, progress, clipCount}
  const [template, setTemplate] = useState("talking_head");
  const [aspect, setAspect] = useState("9:16");
  const [numClips, setNumClips] = useState(3);
  const [running, setRunning] = useState(false);
  const pollRef = useRef(null);

  const addFiles = async (files) => {
    const arr = Array.from(files || []);
    for (const file of arr) {
      const key = `${file.name}-${Date.now()}-${Math.random()}`;
      setItems((prev) => [...prev, { key, name: file.name, status: "uploading", progress: 0, projectId: null, jobId: null, clipCount: 0 }]);
      try {
        const { data } = await api.upload(file);
        setItems((prev) => prev.map((it) => it.key === key ? { ...it, projectId: data.id, status: "idle", duration: data.duration } : it));
      } catch (e) {
        setItems((prev) => prev.map((it) => it.key === key ? { ...it, status: "failed" } : it));
        toast.error(`${file.name}: ${e?.response?.data?.detail || "upload fallito"}`);
      }
    }
  };

  const startQueue = async () => {
    const ready = items.filter((it) => it.projectId && (it.status === "idle" || it.status === "failed"));
    if (!ready.length) { toast.error("Nessun video pronto in coda"); return; }
    setRunning(true);
    const settings = buildSettings(template, aspect, numClips);
    for (const it of ready) {
      try {
        const { data } = await api.process(it.projectId, settings);
        setItems((prev) => prev.map((x) => x.key === it.key ? { ...x, jobId: data.id, status: "queued", progress: 0 } : x));
      } catch (e) {
        setItems((prev) => prev.map((x) => x.key === it.key ? { ...x, status: "failed" } : x));
      }
    }
    toast.info("Coda avviata — i video vengono elaborati uno alla volta");
  };

  useEffect(() => {
    pollRef.current = setInterval(async () => {
      const active = items.filter((it) => it.jobId && (it.status === "queued" || it.status === "processing"));
      if (!active.length) return;
      for (const it of active) {
        try {
          const { data } = await api.getJob(it.jobId);
          const clipCount = (data.clips || []).filter((c) => c.status === "completed").length;
          setItems((prev) => prev.map((x) => x.key === it.key
            ? { ...x, status: data.status, progress: data.progress, clipCount } : x));
        } catch (e) { /* keep */ }
      }
    }, 1500);
    return () => clearInterval(pollRef.current);
  }, [items]);

  useEffect(() => {
    if (running && items.length && items.every((it) => ["completed", "failed", "idle"].includes(it.status)) &&
        items.some((it) => it.status === "completed")) {
      // nothing else running
    }
  }, [items, running]);

  const downloadZip = (projectId) => {
    const a = document.createElement("a");
    a.href = mediaUrl(`/media/zip/${projectId}`);
    document.body.appendChild(a); a.click(); a.remove();
  };

  return (
    <div>
      <Header />
      <main className="max-w-5xl mx-auto px-5 md:px-8 py-8">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-11 h-11 rounded-xl bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center">
            <Layers className="text-cyan-400" size={22} />
          </div>
          <div>
            <h1 className="font-display text-2xl md:text-3xl font-bold text-slate-100">Coda batch</h1>
            <p className="text-sm text-slate-400">Elabora più video uno dopo l'altro con lo stesso template</p>
          </div>
        </div>

        {/* settings bar */}
        <div className="grid sm:grid-cols-3 gap-3 mb-5">
          <div>
            <label className="text-xs uppercase text-slate-500 font-mono">Template</label>
            <Select value={template} onValueChange={setTemplate}>
              <SelectTrigger className="mt-1.5 bg-[#13161C] border-white/10" data-testid="batch-template"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="podcast">Podcast</SelectItem>
                <SelectItem value="talking_head">Talking Head</SelectItem>
                <SelectItem value="gaming">Gaming</SelectItem>
                <SelectItem value="minimal">Minimal</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-xs uppercase text-slate-500 font-mono">Formato</label>
            <Select value={aspect} onValueChange={setAspect}>
              <SelectTrigger className="mt-1.5 bg-[#13161C] border-white/10" data-testid="batch-aspect"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="9:16">9:16</SelectItem>
                <SelectItem value="16:9">16:9</SelectItem>
                <SelectItem value="1:1">1:1</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-xs uppercase text-slate-500 font-mono">Clip per video</label>
            <Select value={String(numClips)} onValueChange={(v) => setNumClips(Number(v))}>
              <SelectTrigger className="mt-1.5 bg-[#13161C] border-white/10" data-testid="batch-numclips"><SelectValue /></SelectTrigger>
              <SelectContent>
                {[1, 3, 5, 10].map((n) => <SelectItem key={n} value={String(n)}>{n}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); addFiles(e.dataTransfer.files); }}
          data-testid="batch-dropzone"
          className="rounded-xl border-2 border-dashed border-cyan-500/25 bg-[#13161C]/60 hover:border-cyan-400/70 p-8 text-center cursor-pointer transition-all mb-5">
          <UploadCloud className="w-9 h-9 text-cyan-400 mx-auto mb-2" />
          <p className="text-slate-200 font-medium">Aggiungi più video alla coda</p>
          <p className="text-xs text-slate-500 mt-1">MP4, MOV, MKV, WEBM, AVI</p>
          <input ref={inputRef} type="file" multiple accept=".mp4,.mov,.mkv,.webm,.avi" className="hidden"
            data-testid="batch-input" onChange={(e) => addFiles(e.target.files)} />
        </div>

        {items.length > 0 && (
          <div className="space-y-2.5 mb-6">
            {items.map((it, i) => {
              const s = STATUS[it.status] || STATUS.idle;
              return (
                <div key={it.key} data-testid={`batch-item-${i}`}
                  className="flex items-center gap-3 bg-[#1A1D26] border border-white/10 rounded-lg px-4 py-3">
                  <s.icon size={18} className={s.cls} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-slate-100 font-medium truncate">{it.name}</p>
                    <p className="text-xs text-slate-500">
                      {s.label}{it.status === "processing" ? ` · ${it.progress}%` : ""}
                      {it.status === "completed" ? ` · ${it.clipCount} clip` : ""}
                    </p>
                  </div>
                  {it.status === "completed" && (
                    <>
                      <Button size="sm" variant="secondary" onClick={() => navigate(`/project/${it.projectId}`)} className="bg-slate-800 border border-white/10 h-8" data-testid={`batch-open-${i}`}>
                        <Play size={14} className="mr-1" /> Apri
                      </Button>
                      <Button size="sm" onClick={() => downloadZip(it.projectId)} className="bg-cyan-500 hover:bg-cyan-400 text-slate-950 h-8" data-testid={`batch-zip-${i}`}>
                        <Download size={14} className="mr-1" /> ZIP
                      </Button>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        )}

        <div className="flex justify-end">
          <Button onClick={startQueue} disabled={!items.some((it) => it.projectId)} data-testid="batch-start"
            className="h-12 px-6 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold shadow-lg shadow-cyan-500/20">
            <Play size={18} className="mr-1.5" /> Avvia coda ({items.filter((it) => it.projectId).length})
          </Button>
        </div>
      </main>
    </div>
  );
}
