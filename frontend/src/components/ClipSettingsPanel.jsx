import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import SubtitleStyleEditor from "@/components/SubtitleStyleEditor";
import {
  Smartphone, Monitor, Square, Wand2, Captions, ZoomIn, Crop, ScanFace,
  AudioLines, ArrowRight, Clapperboard,
} from "lucide-react";

const ASPECTS = [
  { key: "9:16", icon: Smartphone, title: "9:16", sub: "TikTok · Reels · Shorts" },
  { key: "16:9", icon: Monitor, title: "16:9", sub: "YouTube" },
  { key: "1:1", icon: Square, title: "1:1", sub: "Instagram" },
];
const DURATIONS = [15, 30, 45, 60];
const COUNTS = [1, 3, 5, 10];

const TOGGLES = [
  { key: "subtitles", icon: Captions, label: "Sottotitoli", desc: "Trascrizione Whisper impressa nel video" },
  { key: "auto_zoom", icon: ZoomIn, label: "Zoom automatico", desc: "Leggero zoom dinamico durante il parlato" },
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

  return (
    <div className="grid lg:grid-cols-[1fr_400px] gap-6 items-start">
      <div className="space-y-7">
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
          <div className="flex items-center gap-2 text-sm text-slate-300 mb-3">
            <Clapperboard size={16} className="text-cyan-400" />
            <span>Verranno generate <b className="text-slate-100">{settings.num_clips}</b> clip in formato <b className="text-slate-100">{settings.aspect_ratio}</b></span>
          </div>
          <Button
            onClick={onGenerate} disabled={submitting}
            data-testid="generate-btn"
            className="w-full h-12 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold text-base shadow-lg shadow-cyan-500/20">
            {submitting ? "Avvio…" : <>Genera clip <ArrowRight className="ml-1" size={18} /></>}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default ClipSettingsPanel;
