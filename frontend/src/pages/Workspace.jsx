import { useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import Header from "@/components/Header";
import VideoInfoPanel from "@/components/VideoInfoPanel";
import ClipSettingsPanel from "@/components/ClipSettingsPanel";
import ExportQueue from "@/components/ExportQueue";
import ClipResults from "@/components/ClipResults";
import Editor from "@/components/Editor";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Loader2, ChevronLeft, Check } from "lucide-react";

const DEFAULT_SETTINGS = {
  aspect_ratio: "9:16", clip_duration: 30, num_clips: 3,
  subtitles: true, auto_zoom: false, auto_crop: true, face_tracking: true,
  audio_normalize: true, auto_find: true,
  template: null,
  silence_removal: "off",
  smart_zoom: "off",
  zoom_mode: "normal",
  export_preset: "social_hq",
  export_crf: 20,
  video_volume: 1.0,
  fade_in: 0.0,
  fade_out: 0.0,
  music: null,
  overlay: null,
  subtitle_style: {
    preset: "bold", mode: "highlight", animation: "fade", font: "DejaVu Sans", size: 68,
    color: "#FFFFFF", highlight_color: "#FFE600", background: false, bg_color: "#000000",
    shadow: true, outline: 4, bold: true, position: "lower", alignment: "center",
    max_words_per_line: 4, word_highlight: false,
  },
};

const STEPS = [
  { key: "info", label: "Video" },
  { key: "settings", label: "Impostazioni" },
  { key: "processing", label: "Elaborazione" },
  { key: "result", label: "Clip" },
];

export default function Workspace() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [step, setStep] = useState("info");
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [submitting, setSubmitting] = useState(false);
  const [job, setJob] = useState(null);
  const [editClip, setEditClip] = useState(null);
  const [editJobId, setEditJobId] = useState(null);
  const [rendering, setRendering] = useState(false);
  const pollRef = useRef(null);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.getProject(id);
        setProject(data);
      } catch (e) {
        toast.error("Progetto non trovato");
        navigate("/");
      } finally {
        setLoading(false);
      }
    })();
  }, [id, navigate]);

  // poll main job
  useEffect(() => {
    if (step !== "processing" || !job?.id) return;
    pollRef.current = setInterval(async () => {
      try {
        const { data } = await api.getJob(job.id);
        setJob(data);
        if (data.status === "completed") {
          clearInterval(pollRef.current);
          setStep("result");
          toast.success("Clip pronte!");
        } else if (data.status === "failed") {
          clearInterval(pollRef.current);
          setStep("result");
          toast.error(data.error || "Elaborazione fallita");
        }
      } catch (e) { /* keep polling */ }
    }, 1200);
    return () => clearInterval(pollRef.current);
  }, [step, job?.id]);

  // poll editor render job
  useEffect(() => {
    if (!editJobId) return;
    const iv = setInterval(async () => {
      try {
        const { data } = await api.getJob(editJobId);
        if (data.status === "completed") {
          clearInterval(iv);
          setRendering(false);
          setEditJobId(null);
          const newClips = (data.clips || []).filter((c) => c.status === "completed");
          setJob((prev) => prev ? { ...prev, clips: [...prev.clips, ...newClips] } : data);
          toast.success("Clip modificata esportata");
        } else if (data.status === "failed") {
          clearInterval(iv);
          setRendering(false);
          setEditJobId(null);
          toast.error(data.error || "Export fallito");
        }
      } catch (e) { /* keep polling */ }
    }, 1200);
    return () => clearInterval(iv);
  }, [editJobId]);

  const handleGenerate = async () => {
    setSubmitting(true);
    try {
      const { data } = await api.process(id, settings);
      setJob(data);
      setStep("processing");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Impossibile avviare l'elaborazione");
    } finally {
      setSubmitting(false);
    }
  };

  const handleEditRender = async (payload) => {
    setRendering(true);
    try {
      const { data } = await api.renderClip(id, payload);
      setEditJobId(data.id);
      setEditClip(null);
      toast.info("Export della clip modificata avviato…");
    } catch (e) {
      setRendering(false);
      toast.error(e?.response?.data?.detail || "Impossibile avviare l'export");
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
      </div>
    );
  }
  if (!project) return null;

  const activeIdx = STEPS.findIndex((s) => s.key === step);

  return (
    <div>
      <Header />
      <main className="max-w-7xl mx-auto px-5 md:px-8 py-8">
        {/* stepper */}
        <div className="flex items-center justify-between mb-8">
          <Button variant="ghost" onClick={() => navigate("/")} data-testid="back-btn" className="text-slate-400 hover:text-slate-100">
            <ChevronLeft size={18} className="mr-1" /> Home
          </Button>
          <div className="flex items-center gap-1.5 md:gap-3">
            {STEPS.map((s, i) => (
              <div key={s.key} className="flex items-center gap-1.5 md:gap-3">
                <div className={`flex items-center gap-2 px-2.5 md:px-3 py-1.5 rounded-full text-xs md:text-sm font-medium transition-all
                  ${i === activeIdx ? "bg-cyan-500/15 text-cyan-300 border border-cyan-500/30"
                    : i < activeIdx ? "text-emerald-400" : "text-slate-500"}`}>
                  <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold
                    ${i === activeIdx ? "bg-cyan-500 text-slate-950" : i < activeIdx ? "bg-emerald-500/20 text-emerald-400" : "bg-white/10"}`}>
                    {i < activeIdx ? <Check size={12} /> : i + 1}
                  </span>
                  <span className="hidden sm:inline">{s.label}</span>
                </div>
                {i < STEPS.length - 1 && <div className="w-4 md:w-8 h-px bg-white/10" />}
              </div>
            ))}
          </div>
          <div className="w-16" />
        </div>

        <AnimatePresence mode="wait">
          <motion.div key={step} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.2 }}>
            {step === "info" && (
              <VideoInfoPanel project={project} onContinue={() => setStep("settings")} />
            )}
            {step === "settings" && (
              <ClipSettingsPanel
                project={project} settings={settings} onChange={setSettings}
                onGenerate={handleGenerate} submitting={submitting}
              />
            )}
            {step === "processing" && <ExportQueue job={job} />}
            {step === "result" && job && (
              <ClipResults project={project} job={job} onEdit={(c) => setEditClip(c)} />
            )}
          </motion.div>
        </AnimatePresence>
      </main>

      {rendering && (
        <div className="fixed bottom-5 right-5 z-50 bg-[#1A1D26] border border-cyan-500/30 rounded-xl px-4 py-3 flex items-center gap-3 shadow-xl" data-testid="edit-rendering-toast">
          <Loader2 className="w-4 h-4 text-cyan-400 animate-spin" />
          <span className="text-sm text-slate-200">Export clip modificata in corso…</span>
        </div>
      )}

      <Editor
        project={project} open={!!editClip} clip={editClip}
        baseSettings={{ ...settings, ...(job?.settings || {}) }}
        onClose={() => setEditClip(null)} onRender={handleEditRender}
      />
    </div>
  );
}
