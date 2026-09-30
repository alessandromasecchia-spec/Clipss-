import { useRef, useState } from "react";
import { mediaUrl } from "@/lib/api";
import { formatDuration, formatBytes } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Play, Pause, ArrowRight, Clock, Maximize2, HardDrive, Gauge, Volume2, VolumeX } from "lucide-react";

const Stat = ({ icon: Icon, label, value }) => (
  <div className="flex items-center gap-3 bg-[#13161C] border border-white/10 rounded-lg px-3.5 py-2.5">
    <Icon size={16} className="text-cyan-400 shrink-0" />
    <div className="min-w-0">
      <p className="text-[11px] uppercase tracking-wide text-slate-500 font-mono">{label}</p>
      <p className="text-sm text-slate-100 font-medium truncate">{value}</p>
    </div>
  </div>
);

export const VideoInfoPanel = ({ project, onContinue }) => {
  const videoRef = useRef(null);
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(false);

  const toggle = () => {
    const v = videoRef.current;
    if (!v) return;
    if (v.paused) { v.play(); setPlaying(true); } else { v.pause(); setPlaying(false); }
  };

  return (
    <div className="grid lg:grid-cols-2 gap-6">
      <div className="bg-[#1A1D26] border border-white/10 rounded-xl overflow-hidden shadow-xl shadow-black/40">
        <div className="relative bg-black aspect-video flex items-center justify-center">
          <video
            ref={videoRef}
            src={mediaUrl(`/media/original/${project.id}`)}
            className="w-full h-full object-contain"
            data-testid="info-video"
            muted={muted}
            onClick={toggle}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
          />
          <button
            onClick={toggle} data-testid="info-play-btn"
            className="absolute inset-0 flex items-center justify-center group"
          >
            {!playing && (
              <span className="w-16 h-16 rounded-full bg-cyan-500/90 flex items-center justify-center shadow-lg shadow-cyan-500/30 group-hover:scale-105 transition-transform">
                <Play className="w-7 h-7 text-slate-950 fill-slate-950 ml-1" />
              </span>
            )}
          </button>
          <button
            onClick={() => setMuted((m) => !m)} data-testid="info-mute-btn"
            className="absolute bottom-3 right-3 w-9 h-9 rounded-lg bg-black/60 backdrop-blur border border-white/10 flex items-center justify-center text-slate-200 hover:text-cyan-400"
          >
            {muted ? <VolumeX size={16} /> : <Volume2 size={16} />}
          </button>
        </div>
      </div>

      <div className="flex flex-col">
        <h2 className="font-display text-2xl font-bold text-slate-100">Video caricato</h2>
        <p className="text-slate-400 text-sm mt-1 truncate" data-testid="info-filename">{project.original_filename}</p>

        <div className="grid grid-cols-2 gap-3 mt-5">
          <Stat icon={Clock} label="Durata" value={formatDuration(project.duration)} />
          <Stat icon={Maximize2} label="Risoluzione" value={`${project.width}×${project.height}`} />
          <Stat icon={HardDrive} label="Dimensione" value={formatBytes(project.size_bytes)} />
          <Stat icon={Gauge} label="FPS" value={project.fps ? `${project.fps}` : "—"} />
        </div>

        <div className="mt-3 flex items-center gap-2 text-xs text-slate-400">
          {project.has_audio
            ? <span className="inline-flex items-center gap-1.5 text-emerald-400"><Volume2 size={13} /> Traccia audio rilevata</span>
            : <span className="inline-flex items-center gap-1.5 text-amber-400"><VolumeX size={13} /> Nessun audio (sottotitoli/auto-clip non disponibili)</span>}
        </div>

        <div className="mt-auto pt-6">
          <Button
            onClick={onContinue} data-testid="continue-btn"
            className="w-full h-12 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold text-base shadow-lg shadow-cyan-500/20"
          >
            Continua <ArrowRight className="ml-1" size={18} />
          </Button>
        </div>
      </div>
    </div>
  );
};

export default VideoInfoPanel;
