import { useEffect, useRef, useState, useCallback } from "react";
import { mediaUrl } from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import SubtitleStyleEditor from "@/components/SubtitleStyleEditor";
import { formatDuration } from "@/lib/format";
import { Play, Pause, Volume2, VolumeX, ZoomIn, Scissors, Save, FlagTriangleRight, FlagTriangleLeft, Rewind } from "lucide-react";

const fmt = (t) => {
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  const cs = Math.floor((t % 1) * 100);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}.${String(cs).padStart(2, "0")}`;
};

export const Editor = ({ project, open, clip, baseSettings, onClose, onRender }) => {
  const videoRef = useRef(null);
  const trackRef = useRef(null);
  const duration = project.duration || 0;

  const [start, setStart] = useState(0);
  const [end, setEnd] = useState(Math.min(30, duration));
  const [cur, setCur] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [volume, setVolume] = useState(1);
  const [muted, setMuted] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [settings, setSettings] = useState(baseSettings);

  useEffect(() => {
    if (open && clip) {
      setStart(clip.start);
      setEnd(clip.end);
      setCur(clip.start);
      setSettings(baseSettings);
      const v = videoRef.current;
      if (v) { v.currentTime = clip.start; }
    }
  }, [open, clip, baseSettings]);

  useEffect(() => {
    const v = videoRef.current;
    if (v) { v.volume = volume; v.muted = muted; v.playbackRate = speed; }
  }, [volume, muted, speed]);

  const onTimeUpdate = () => {
    const v = videoRef.current;
    if (!v) return;
    setCur(v.currentTime);
    if (v.currentTime >= end) { v.pause(); v.currentTime = start; setPlaying(false); }
  };

  const togglePlay = () => {
    const v = videoRef.current;
    if (!v) return;
    if (v.paused) { if (v.currentTime < start || v.currentTime >= end) v.currentTime = start; v.play(); setPlaying(true); }
    else { v.pause(); setPlaying(false); }
  };

  const seekTo = (t) => {
    const v = videoRef.current;
    t = Math.max(0, Math.min(duration, t));
    if (v) v.currentTime = t;
    setCur(t);
  };

  const timeFromClientX = useCallback((clientX) => {
    const el = trackRef.current;
    if (!el) return 0;
    const rect = el.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    return ratio * duration;
  }, [duration]);

  const startDrag = (which) => (e) => {
    e.preventDefault();
    const move = (ev) => {
      const t = timeFromClientX(ev.clientX ?? ev.touches?.[0]?.clientX);
      if (which === "start") setStart((s) => Math.min(t, end - 0.5));
      else if (which === "end") setEnd((en) => Math.max(t, start + 0.5));
      else { seekTo(t); }
    };
    const up = () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  };

  const pct = (t) => `${(t / duration) * 100}%`;
  const clipLen = Math.max(0, end - start);

  const handleRender = () => {
    onRender({
      start: Number(start.toFixed(2)),
      end: Number(end.toFixed(2)),
      settings: { ...settings, num_clips: 1 },
    });
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-6xl w-[95vw] bg-[#0F1116] border-white/10 p-0 gap-0 max-h-[92vh] overflow-hidden flex flex-col" data-testid="editor-dialog">
        <DialogHeader className="px-5 py-3.5 border-b border-white/10">
          <DialogTitle className="flex items-center gap-2 font-display"><Scissors size={18} className="text-cyan-400" /> Editor clip</DialogTitle>
        </DialogHeader>

        <div className="grid lg:grid-cols-[1fr_360px] gap-0 flex-1 min-h-0 overflow-auto">
          {/* left: preview */}
          <div className="p-5 flex flex-col min-h-0">
            <div className="bg-black rounded-xl overflow-hidden flex items-center justify-center flex-1 min-h-[240px]">
              <video
                ref={videoRef}
                src={mediaUrl(`/media/original/${project.id}`)}
                className="max-h-[46vh] w-auto"
                data-testid="editor-video"
                onTimeUpdate={onTimeUpdate}
                onLoadedMetadata={() => seekTo(start)}
              />
            </div>

            {/* controls */}
            <div className="flex items-center gap-3 mt-3">
              <Button size="icon" onClick={togglePlay} data-testid="editor-play" className="bg-cyan-500 hover:bg-cyan-400 text-slate-950 rounded-full h-10 w-10">
                {playing ? <Pause size={18} /> : <Play size={18} className="ml-0.5" />}
              </Button>
              <Button size="icon" variant="secondary" onClick={() => seekTo(start)} data-testid="editor-restart" className="bg-slate-800 border border-white/10 h-9 w-9">
                <Rewind size={16} />
              </Button>
              <span className="font-mono text-xs text-slate-300">{fmt(cur)} / {fmt(duration)}</span>

              <div className="flex items-center gap-2 ml-auto">
                <button onClick={() => setMuted((m) => !m)} data-testid="editor-mute" className="text-slate-300 hover:text-cyan-400">
                  {muted ? <VolumeX size={17} /> : <Volume2 size={17} />}
                </button>
                <Slider value={[muted ? 0 : volume * 100]} max={100} onValueChange={([v]) => { setVolume(v / 100); setMuted(v === 0); }} className="w-24" data-testid="editor-volume" />
                <Select value={String(speed)} onValueChange={(v) => setSpeed(Number(v))}>
                  <SelectTrigger className="w-20 h-8 bg-[#13161C] border-white/10" data-testid="editor-speed"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {[0.5, 1, 1.5, 2].map((s) => <SelectItem key={s} value={String(s)}>{s}x</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* timeline */}
            <div className="mt-4 bg-[#13161C] border border-white/10 rounded-xl p-3">
              <div className="flex items-center justify-between mb-2">
                <div className="flex gap-2">
                  <Button size="sm" variant="secondary" onClick={() => setStart(Math.min(cur, end - 0.5))} data-testid="set-start-here" className="bg-slate-800 border border-white/10 h-7 text-xs">
                    <FlagTriangleLeft size={13} className="mr-1 text-cyan-400" /> Inizio qui
                  </Button>
                  <Button size="sm" variant="secondary" onClick={() => setEnd(Math.max(cur, start + 0.5))} data-testid="set-end-here" className="bg-slate-800 border border-white/10 h-7 text-xs">
                    <FlagTriangleRight size={13} className="mr-1 text-cyan-400" /> Fine qui
                  </Button>
                </div>
                <div className="flex items-center gap-2 text-slate-400">
                  <ZoomIn size={14} />
                  <Slider value={[zoom]} min={1} max={5} step={0.5} onValueChange={([z]) => setZoom(z)} className="w-24" data-testid="timeline-zoom" />
                </div>
              </div>

              <div className="overflow-x-auto pb-1">
                <div ref={trackRef} style={{ width: `${zoom * 100}%` }}
                  className="relative h-14 rounded-lg bg-gradient-to-r from-slate-800/60 to-slate-700/40 border border-white/10 cursor-pointer select-none"
                  onMouseDown={(e) => { if (e.target === trackRef.current) seekTo(timeFromClientX(e.clientX)); }}
                  data-testid="timeline-track">
                  {/* selected region */}
                  <div className="absolute top-0 bottom-0 bg-cyan-500/20 border-x-2 border-cyan-400" style={{ left: pct(start), width: pct(clipLen) }} />
                  {/* start handle */}
                  <div onMouseDown={startDrag("start")} data-testid="handle-start"
                    className="absolute top-0 bottom-0 w-3 -ml-1.5 bg-cyan-400 rounded cursor-ew-resize hover:bg-cyan-300 z-10" style={{ left: pct(start) }} />
                  {/* end handle */}
                  <div onMouseDown={startDrag("end")} data-testid="handle-end"
                    className="absolute top-0 bottom-0 w-3 -ml-1.5 bg-cyan-400 rounded cursor-ew-resize hover:bg-cyan-300 z-10" style={{ left: pct(end) }} />
                  {/* playhead */}
                  <div className="absolute top-0 bottom-0 w-0.5 bg-rose-400 z-20 pointer-events-none" style={{ left: pct(cur) }} />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3 mt-3">
                <div>
                  <Label className="text-[10px] uppercase text-slate-500 font-mono">Start (s)</Label>
                  <Input type="number" step="0.1" min={0} max={duration} value={start.toFixed(1)}
                    onChange={(e) => setStart(Math.max(0, Math.min(parseFloat(e.target.value) || 0, end - 0.5)))}
                    className="h-8 bg-[#0B0D11] border-white/10 font-mono text-xs" data-testid="start-input" />
                </div>
                <div>
                  <Label className="text-[10px] uppercase text-slate-500 font-mono">End (s)</Label>
                  <Input type="number" step="0.1" min={0} max={duration} value={end.toFixed(1)}
                    onChange={(e) => setEnd(Math.min(duration, Math.max(parseFloat(e.target.value) || 0, start + 0.5)))}
                    className="h-8 bg-[#0B0D11] border-white/10 font-mono text-xs" data-testid="end-input" />
                </div>
                <div>
                  <Label className="text-[10px] uppercase text-slate-500 font-mono">Durata</Label>
                  <div className="h-8 flex items-center font-mono text-sm text-cyan-400" data-testid="clip-length">{formatDuration(clipLen)}</div>
                </div>
              </div>
            </div>
          </div>

          {/* right: settings */}
          <div className="border-l border-white/10 p-5 bg-[#0B0D11]/50 overflow-y-auto">
            <Tabs defaultValue="crop">
              <TabsList className="grid grid-cols-2 w-full bg-[#13161C]">
                <TabsTrigger value="crop" data-testid="tab-crop">Ritaglio</TabsTrigger>
                <TabsTrigger value="subs" data-testid="tab-subs">Sottotitoli</TabsTrigger>
              </TabsList>

              <TabsContent value="crop" className="space-y-4 mt-4">
                <div>
                  <Label className="text-xs uppercase tracking-wide text-slate-500 font-mono">Formato</Label>
                  <div className="grid grid-cols-3 gap-2 mt-2">
                    {["9:16", "16:9", "1:1"].map((a) => (
                      <button key={a} onClick={() => setSettings((s) => ({ ...s, aspect_ratio: a }))}
                        data-testid={`editor-aspect-${a.replace(":", "-")}`}
                        className={`py-2 rounded-lg border text-sm font-semibold ${settings.aspect_ratio === a ? "border-cyan-400 bg-cyan-500/10 text-cyan-300" : "border-white/10 bg-[#1A1D26] text-slate-300"}`}>{a}</button>
                    ))}
                  </div>
                </div>
                {[
                  { k: "auto_crop", l: "Auto crop" },
                  { k: "face_tracking", l: "Tracking volto" },
                  { k: "auto_zoom", l: "Zoom automatico" },
                  { k: "audio_normalize", l: "Normalizzazione audio" },
                ].map((t) => (
                  <div key={t.k} className="flex items-center justify-between bg-[#13161C] border border-white/10 rounded-lg px-3.5 py-2.5">
                    <span className="text-sm text-slate-200">{t.l}</span>
                    <Switch checked={!!settings[t.k]} onCheckedChange={(v) => setSettings((s) => ({ ...s, [t.k]: v }))} data-testid={`editor-toggle-${t.k}`} />
                  </div>
                ))}
              </TabsContent>

              <TabsContent value="subs" className="mt-4">
                <div className="flex items-center justify-between bg-[#13161C] border border-white/10 rounded-lg px-3.5 py-2.5 mb-4">
                  <span className="text-sm text-slate-200">Sottotitoli attivi</span>
                  <Switch checked={!!settings.subtitles && project.has_audio} disabled={!project.has_audio}
                    onCheckedChange={(v) => setSettings((s) => ({ ...s, subtitles: v }))} data-testid="editor-toggle-subtitles" />
                </div>
                {settings.subtitles && project.has_audio && (
                  <SubtitleStyleEditor style={settings.subtitle_style} onChange={(st) => setSettings((s) => ({ ...s, subtitle_style: st }))} />
                )}
              </TabsContent>
            </Tabs>
          </div>
        </div>

        <div className="px-5 py-3.5 border-t border-white/10 flex items-center justify-between">
          <span className="text-sm text-slate-400 font-mono">Clip: {fmt(start)} → {fmt(end)} · {formatDuration(clipLen)}</span>
          <div className="flex gap-2 items-center">
            <Select value={settings.export_preset || "social_hq"} onValueChange={(v) => setSettings((s) => ({ ...s, export_preset: v }))}>
              <SelectTrigger className="w-36 h-9 bg-[#13161C] border-white/10" data-testid="editor-export-preset"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="social_hq">Social HQ</SelectItem>
                <SelectItem value="social_small">Social Small</SelectItem>
                <SelectItem value="custom">Custom</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="secondary" onClick={onClose} className="bg-slate-800 border border-white/10" data-testid="editor-cancel">Annulla</Button>
            <Button onClick={handleRender} data-testid="editor-render" className="bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold">
              <Save size={16} className="mr-1.5" /> Esporta clip
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default Editor;
