import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { api } from "@/lib/api";
import SubtitleStyleEditor from "@/components/SubtitleStyleEditor";
import {
  Smartphone, Monitor, Square, Wand2, Captions, ZoomIn, Crop, ScanFace,
  AudioLines, ArrowRight, Clapperboard, Layers, Scissors, Music2, Image as ImageIcon,
  Mic, User, Gamepad2, Minus, Check as CheckIcon,
} from "lucide-react";

const TEMPLATES = [
  { key: "podcast", label: "Podcast", icon: Mic,
    patch: { aspect_ratio: "9:16", face_tracking: true, auto_crop: true, smart_zoom: "low", zoom_mode: "normal", silence_removal: "low", subtitles: true }, preset: "bold" },
  { key: "talking_head", label: "Talking Head", icon: User,
    patch: { aspect_ratio: "9:16", face_tracking: true, auto_crop: true, smart_zoom: "medium", zoom_mode: "punch_in", silence_removal: "medium", subtitles: true }, preset: "bold" },
  { key: "gaming", label: "Gaming", icon: Gamepad2,
    patch: { aspect_ratio: "9:16", face_tracking: false, auto_crop: true, smart_zoom: "high", zoom_mode: "punch_in", silence_removal: "low", audio_normalize: true, subtitles: true }, preset: "gaming" },
  { key: "minimal", label: "Minimal", icon: Minus,
    patch: { aspect_ratio: "9:16", face_tracking: true, auto_crop: true, smart_zoom: "off", zoom_mode: "normal", silence_removal: "off", subtitles: true }, preset: "minimal" },
];

const Segmented = ({ options, value, onChange, testidPrefix }) => (
  <div className="flex flex-wrap gap-2">
    {options.map((o) => (
      <button key={o.value} onClick={() => onChange(o.value)}
        data-testid={`${testidPrefix}-${o.value}`}
        className={`px-3.5 py-1.5 rounded-lg border text-xs font-semibold transition-all
          ${value === o.value ? "border-cyan-400 bg-cyan-500/10 text-cyan-300" : "border-white/10 bg-[#1A1D26] text-slate-300 hover:border-white/25"}`}>
        {o.label}
      </button>
    ))}
  </div>
);

const ASPECTS = [
  { key: "9:16", icon: Smartphone, title: "9:16", sub: "TikTok · Reels · Shorts" },
  { key: "16:9", icon: Monitor, title: "16:9", sub: "YouTube" },
  { key: "1:1", icon: Square, title: "1:1", sub: "Instagram" },
];
const DURATIONS = [15, 30, 45, 60];
const COUNTS = [1, 3, 5, 10];

const TOGGLES = [
  { key: "subtitles", icon: Captions, label: "Sottotitoli", desc: "Trascrizione Whisper impressa nel video" },
  { key: "auto_crop", icon: Crop, label: "Auto crop", desc: "Ritaglio intelligente al formato scelto" },
  { key: "face_tracking", icon: ScanFace, label: "Tracking volto", desc: "Centra il crop sul volto (OpenCV)" },
  { key: "audio_normalize", icon: AudioLines, label: "Normalizzazione audio", desc: "Volume uniforme (loudnorm)" },
];

const Section = ({ title, children }) => (
  <div>
    <h3 className="text-xs uppercase tracking-wide text-slate-500 font-mono mb-2.5">{title}</h3>
    {children}
  </div>
);

export const ClipSettingsPanel = ({ settings, onChange, onGenerate, project, submitting }) => {
  const set = (patch) => onChange({ ...settings, ...patch });
  const custom = ![15, 30, 45, 60].includes(settings.clip_duration);
  const noAudio = !project.has_audio;
  const [uploadingAsset, setUploadingAsset] = useState(null);

  const applyTemplate = (tpl) => {
    set({
      template: tpl.key,
      ...tpl.patch,
      subtitle_style: { ...settings.subtitle_style, preset: tpl.preset },
    });
    toast.success(`Template "${tpl.label}" applicato`);
  };

  const handleAsset = async (kind, file) => {
    if (!file) return;
    setUploadingAsset(kind);
    try {
      if (kind === "music") {
        const { data } = await api.uploadAudio(project.id, file);
        set({ music: { name: data.name, volume: 0.25, start_offset: 0, fade_in: 0.5, fade_out: 0.5, loop: true } });
        toast.success("Musica caricata");
      } else {
        const { data } = await api.uploadOverlay(project.id, file);
        set({ overlay: { name: data.name, x: 0.5, y: 0.06, scale: 0.28, opacity: 1.0, start: 0, end: 0 } });
        toast.success("Overlay caricato");
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Upload non riuscito");
    } finally {
      setUploadingAsset(null);
    }
  };

  return (
    <div className="grid lg:grid-cols-[1fr_400px] gap-6 items-start">
      <div className="space-y-7">
        <Section title="Template Auto Edit">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {TEMPLATES.map((t) => (
              <button key={t.key} onClick={() => applyTemplate(t)}
                data-testid={`template-${t.key}`}
                className={`relative rounded-xl border p-4 flex flex-col items-center gap-2 transition-all
                  ${settings.template === t.key ? "border-cyan-400 bg-cyan-500/10" : "border-white/10 bg-[#1A1D26] hover:border-white/25"}`}>
                {settings.template === t.key && <CheckIcon size={13} className="absolute top-2 right-2 text-cyan-400" />}
                <t.icon size={22} className={settings.template === t.key ? "text-cyan-400" : "text-slate-400"} />
                <span className="text-xs font-semibold text-slate-100">{t.label}</span>
              </button>
            ))}
          </div>
        </Section>

        {/* AUTO CLIP hero */}
        <button
          onClick={() => set({ auto_find: !settings.auto_find })}
          disabled={noAudio}
          data-testid="autofind-toggle"
          className={`w-full text-left rounded-xl border p-4 flex items-start gap-3.5 transition-all
            ${settings.auto_find && !noAudio ? "border-cyan-400 bg-cyan-500/10" : "border-white/10 bg-[#1A1D26] hover:border-white/25"}
            ${noAudio ? "opacity-50 cursor-not-allowed" : ""}`}
        >
          <div className="w-10 h-10 rounded-lg bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center shrink-0">
            <Wand2 className="text-cyan-400" size={20} />
          </div>
          <div className="flex-1">
            <div className="flex items-center justify-between">
              <p className="font-semibold text-slate-100">Trova automaticamente le clip migliori</p>
              <Switch checked={settings.auto_find && !noAudio} disabled={noAudio} onCheckedChange={(v) => set({ auto_find: v })} />
            </div>
            <p className="text-xs text-slate-400 mt-1 leading-relaxed">
              Analizza la trascrizione (frasi complete, domande, ritmo del parlato, parole chiave) per selezionare
              i segmenti più interessanti. {noAudio && "Non disponibile: il video non ha audio."}
            </p>
          </div>
        </button>

        <Section title="Formato">
          <div className="grid grid-cols-3 gap-3">
            {ASPECTS.map((a) => (
              <button key={a.key} onClick={() => set({ aspect_ratio: a.key })}
                data-testid={`aspect-${a.key.replace(":", "-")}`}
                className={`rounded-xl border p-4 flex flex-col items-center gap-2 transition-all
                  ${settings.aspect_ratio === a.key ? "border-cyan-400 bg-cyan-500/10" : "border-white/10 bg-[#1A1D26] hover:border-white/25"}`}>
                <a.icon size={26} className={settings.aspect_ratio === a.key ? "text-cyan-400" : "text-slate-400"} />
                <span className="font-display font-bold text-slate-100">{a.title}</span>
                <span className="text-[10px] text-slate-500 text-center leading-tight">{a.sub}</span>
              </button>
            ))}
          </div>
        </Section>

        <Section title="Durata clip">
          <div className="flex flex-wrap gap-2">
            {DURATIONS.map((d) => (
              <button key={d} onClick={() => set({ clip_duration: d })}
                data-testid={`duration-${d}`}
                className={`px-4 py-2 rounded-lg border text-sm font-semibold transition-all
                  ${!custom && settings.clip_duration === d ? "border-cyan-400 bg-cyan-500/10 text-cyan-300" : "border-white/10 bg-[#1A1D26] text-slate-300 hover:border-white/25"}`}>
                {d}s
              </button>
            ))}
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border ${custom ? "border-cyan-400 bg-cyan-500/10" : "border-white/10 bg-[#1A1D26]"}`}>
              <span className="text-xs text-slate-400">Personalizzata</span>
              <Input type="number" min={3} max={600} value={custom ? settings.clip_duration : ""} placeholder="s"
                data-testid="duration-custom"
                onChange={(e) => set({ clip_duration: Math.max(3, parseInt(e.target.value || "0", 10)) })}
                className="w-16 h-8 bg-[#0B0D11] border-white/10 text-center" />
            </div>
          </div>
        </Section>

        <Section title="Numero di clip">
          <div className="flex flex-wrap gap-2">
            {COUNTS.map((c) => (
              <button key={c} onClick={() => set({ num_clips: c })}
                data-testid={`count-${c}`}
                className={`w-14 py-2 rounded-lg border text-sm font-bold transition-all
                  ${settings.num_clips === c ? "border-cyan-400 bg-cyan-500/10 text-cyan-300" : "border-white/10 bg-[#1A1D26] text-slate-300 hover:border-white/25"}`}>
                {c}
              </button>
            ))}
          </div>
        </Section>

        <Section title="Silence Removal — rimozione pause">
          <Segmented testidPrefix="silence"
            value={settings.silence_removal}
            onChange={(v) => set({ silence_removal: v })}
            options={[{ value: "off", label: "OFF" }, { value: "low", label: "Leggero" }, { value: "medium", label: "Medio" }, { value: "high", label: "Aggressivo" }]} />
          {noAudio && <p className="text-xs text-amber-400 mt-2">Non disponibile: il video non ha audio.</p>}
        </Section>

        <Section title="Smart Zoom">
          <Segmented testidPrefix="zoom"
            value={settings.smart_zoom}
            onChange={(v) => set({ smart_zoom: v })}
            options={[{ value: "off", label: "OFF" }, { value: "low", label: "Leggero" }, { value: "medium", label: "Medio" }, { value: "high", label: "Forte" }]} />
          {settings.smart_zoom !== "off" && (
            <div className="mt-3">
              <Label className="text-xs uppercase tracking-wide text-slate-500 font-mono mb-2 block">Modalità zoom</Label>
              <Segmented testidPrefix="zoommode"
                value={settings.zoom_mode}
                onChange={(v) => set({ zoom_mode: v })}
                options={[{ value: "normal", label: "Normal" }, { value: "punch_in", label: "Punch In" }, { value: "punch_out", label: "Punch Out" }]} />
            </div>
          )}
        </Section>

        <Section title="Opzioni di elaborazione">
          <div className="space-y-2.5">
            {TOGGLES.map((t) => {
              const disabled = t.key === "subtitles" && noAudio;
              return (
                <div key={t.key} className={`flex items-center gap-3 bg-[#1A1D26] border border-white/10 rounded-lg px-3.5 py-3 ${disabled ? "opacity-50" : ""}`}>
                  <t.icon size={18} className="text-cyan-400 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-slate-100 font-medium">{t.label}</p>
                    <p className="text-xs text-slate-500 truncate">{t.desc}</p>
                  </div>
                  <Switch
                    checked={!!settings[t.key] && !disabled} disabled={disabled}
                    onCheckedChange={(v) => set({ [t.key]: v })}
                    data-testid={`toggle-${t.key}`}
                  />
                </div>
              );
            })}
          </div>
        </Section>
      </div>

      {/* right column */}
      <div className="lg:sticky lg:top-24 space-y-4">
        {settings.subtitles && !noAudio && (
          <div className="bg-[#1A1D26] border border-white/10 rounded-xl p-4">
            <h3 className="font-display font-bold text-slate-100 mb-3 flex items-center gap-2"><Captions size={16} className="text-cyan-400" /> Stile sottotitoli</h3>
            <SubtitleStyleEditor style={settings.subtitle_style} onChange={(s) => set({ subtitle_style: s })} />
          </div>
        )}

        <div className="bg-[#1A1D26] border border-white/10 rounded-xl p-4">
          <h3 className="font-display font-bold text-slate-100 mb-3 flex items-center gap-2"><Layers size={16} className="text-cyan-400" /> Qualità export</h3>
          <Segmented testidPrefix="export"
            value={settings.export_preset}
            onChange={(v) => set({ export_preset: v })}
            options={[{ value: "social_hq", label: "Social HQ" }, { value: "social_small", label: "Small" }, { value: "custom", label: "Custom" }]} />
          {settings.export_preset === "custom" && (
            <div className="mt-3">
              <Label className="text-xs uppercase text-slate-500 font-mono">CRF (qualità) · {settings.export_crf}</Label>
              <Input type="number" min={14} max={40} value={settings.export_crf}
                onChange={(e) => set({ export_crf: parseInt(e.target.value || "20", 10) })}
                className="mt-1.5 h-9 bg-[#0B0D11] border-white/10 w-24 font-mono" data-testid="export-crf" />
            </div>
          )}
        </div>

        <div className="bg-[#1A1D26] border border-white/10 rounded-xl p-4">
          <h3 className="font-display font-bold text-slate-100 mb-3 flex items-center gap-2"><Music2 size={16} className="text-cyan-400" /> Musica di sottofondo</h3>
          {settings.music ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-300 truncate">{settings.music.name}</span>
                <button onClick={() => set({ music: null })} data-testid="music-remove" className="text-rose-400 text-xs hover:underline">Rimuovi</button>
              </div>
              <div>
                <Label className="text-xs uppercase text-slate-500 font-mono">Volume musica · {Math.round(settings.music.volume * 100)}%</Label>
                <input type="range" min="0" max="100" value={settings.music.volume * 100} data-testid="music-volume"
                  onChange={(e) => set({ music: { ...settings.music, volume: parseInt(e.target.value, 10) / 100 } })}
                  className="w-full mt-2 accent-cyan-400" />
              </div>
              <label className="flex items-center gap-2 text-xs text-slate-400">
                <input type="checkbox" checked={settings.music.loop} onChange={(e) => set({ music: { ...settings.music, loop: e.target.checked } })} className="accent-cyan-400" />
                Ripeti in loop se più corta del video
              </label>
            </div>
          ) : (
            <label className="block">
              <span className="cursor-pointer inline-flex items-center gap-2 text-sm text-cyan-300 border border-cyan-500/30 bg-cyan-500/5 rounded-lg px-3 py-2 hover:bg-cyan-500/10" data-testid="music-upload-label">
                <Music2 size={15} /> {uploadingAsset === "music" ? "Caricamento…" : "Carica MP3 / WAV / M4A"}
              </span>
              <input type="file" accept=".mp3,.wav,.m4a,.aac" className="hidden" data-testid="music-input"
                onChange={(e) => handleAsset("music", e.target.files?.[0])} />
            </label>
          )}
        </div>

        <div className="bg-[#1A1D26] border border-white/10 rounded-xl p-4">
          <h3 className="font-display font-bold text-slate-100 mb-3 flex items-center gap-2"><ImageIcon size={16} className="text-cyan-400" /> Image Overlay</h3>
          {settings.overlay ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-300 truncate">{settings.overlay.name}</span>
                <button onClick={() => set({ overlay: null })} data-testid="overlay-remove" className="text-rose-400 text-xs hover:underline">Rimuovi</button>
              </div>
              <div>
                <Label className="text-xs uppercase text-slate-500 font-mono">Dimensione · {Math.round(settings.overlay.scale * 100)}%</Label>
                <input type="range" min="5" max="80" value={settings.overlay.scale * 100} data-testid="overlay-scale"
                  onChange={(e) => set({ overlay: { ...settings.overlay, scale: parseInt(e.target.value, 10) / 100 } })}
                  className="w-full mt-2 accent-cyan-400" />
              </div>
              <div>
                <Label className="text-xs uppercase text-slate-500 font-mono">Opacità · {Math.round(settings.overlay.opacity * 100)}%</Label>
                <input type="range" min="10" max="100" value={settings.overlay.opacity * 100} data-testid="overlay-opacity"
                  onChange={(e) => set({ overlay: { ...settings.overlay, opacity: parseInt(e.target.value, 10) / 100 } })}
                  className="w-full mt-2 accent-cyan-400" />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <Label className="text-xs uppercase text-slate-500 font-mono">Pos X</Label>
                  <input type="range" min="0" max="100" value={settings.overlay.x * 100} data-testid="overlay-x"
                    onChange={(e) => set({ overlay: { ...settings.overlay, x: parseInt(e.target.value, 10) / 100 } })}
                    className="w-full mt-2 accent-cyan-400" />
                </div>
                <div>
                  <Label className="text-xs uppercase text-slate-500 font-mono">Pos Y</Label>
                  <input type="range" min="0" max="100" value={settings.overlay.y * 100} data-testid="overlay-y"
                    onChange={(e) => set({ overlay: { ...settings.overlay, y: parseInt(e.target.value, 10) / 100 } })}
                    className="w-full mt-2 accent-cyan-400" />
                </div>
              </div>
            </div>
          ) : (
            <label className="block">
              <span className="cursor-pointer inline-flex items-center gap-2 text-sm text-cyan-300 border border-cyan-500/30 bg-cyan-500/5 rounded-lg px-3 py-2 hover:bg-cyan-500/10" data-testid="overlay-upload-label">
                <ImageIcon size={15} /> {uploadingAsset === "overlay" ? "Caricamento…" : "Carica PNG / JPG / WEBP"}
              </span>
              <input type="file" accept=".png,.jpg,.jpeg,.webp" className="hidden" data-testid="overlay-input"
                onChange={(e) => handleAsset("overlay", e.target.files?.[0])} />
            </label>
          )}
        </div>

        <div className="bg-[#1A1D26] border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 text-sm text-slate-300 mb-3">
            <Clapperboard size={16} className="text-cyan-400" />
            <span>Verranno generate <b className="text-slate-100">{settings.num_clips}</b> clip in formato <b className="text-slate-100">{settings.aspect_ratio}</b></span>
          </div>
          <Button
            onClick={onGenerate} disabled={submitting}
            data-testid="generate-btn"
            className="w-full h-12 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold text-base shadow-lg shadow-cyan-500/20">
            {submitting ? "Avvio…" : <>Genera Auto Edit <ArrowRight className="ml-1" size={18} /></>}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default ClipSettingsPanel;
