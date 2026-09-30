import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Type, Check } from "lucide-react";

const PRESETS = {
  classico: { label: "Classico", font: "DejaVu Sans", size: 58, color: "#FFFFFF", bold: false, outline: 3, shadow: true, background: false },
  bold: { label: "Bold", font: "DejaVu Sans", size: 68, color: "#FFFFFF", bold: true, outline: 4, shadow: true, background: false },
  gaming: { label: "Gaming", font: "DejaVu Sans", size: 66, color: "#00E5FF", bold: true, outline: 5, shadow: true, background: false },
  minimal: { label: "Minimal", font: "DejaVu Sans", size: 52, color: "#FFFFFF", bold: false, outline: 1, shadow: false, background: true, bg_color: "#000000" },
};

const FONTS = ["DejaVu Sans", "Liberation Sans", "Liberation Serif", "DejaVu Sans Mono"];
const COLORS = ["#FFFFFF", "#FFE600", "#00E5FF", "#10B981", "#F43F5E", "#FF7A00", "#000000"];

export const SubtitleStyleEditor = ({ style, onChange }) => {
  const set = (patch) => onChange({ ...style, ...patch });
  const applyPreset = (key) => set({ preset: key, ...PRESETS[key] });

  const previewJustify = style.alignment === "left" ? "flex-start" : style.alignment === "right" ? "flex-end" : "center";
  const previewAlign = style.position === "top" ? "flex-start" : style.position === "center" ? "center" : "flex-end";

  return (
    <div className="space-y-5" data-testid="subtitle-style-editor">
      {/* live preview */}
      <div className="relative rounded-lg overflow-hidden border border-white/10 bg-black h-40 flex p-3"
           style={{ justifyContent: previewJustify, alignItems: previewAlign }}>
        <div className="absolute inset-0 opacity-30 bg-gradient-to-br from-slate-700 to-slate-900" />
        <span
          className="relative px-2 py-0.5 leading-tight text-center max-w-[90%]"
          style={{
            fontFamily: style.font,
            fontWeight: style.bold ? 800 : 500,
            fontSize: Math.max(14, style.size * 0.32),
            color: style.color,
            backgroundColor: style.background ? style.bg_color : "transparent",
            textShadow: style.shadow ? "2px 2px 4px rgba(0,0,0,0.9)" : "none",
            WebkitTextStroke: style.outline > 0 ? `${Math.min(2, style.outline * 0.4)}px #000` : "none",
          }}
        >
          Esempio di sottotitolo
        </span>
      </div>

      {/* presets */}
      <div>
        <Label className="text-xs uppercase tracking-wide text-slate-500 font-mono">Stile predefinito</Label>
        <div className="grid grid-cols-4 gap-2 mt-2">
          {Object.entries(PRESETS).map(([key, p]) => (
            <button
              key={key} onClick={() => applyPreset(key)}
              data-testid={`subtitle-preset-${key}`}
              className={`relative rounded-lg border px-2 py-2.5 text-xs font-semibold transition-all
                ${style.preset === key ? "border-cyan-400 bg-cyan-500/10 text-cyan-300" : "border-white/10 bg-white/5 text-slate-300 hover:border-white/25"}`}
            >
              {style.preset === key && <Check size={12} className="absolute top-1 right-1 text-cyan-400" />}
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label className="text-xs uppercase tracking-wide text-slate-500 font-mono flex items-center gap-1"><Type size={12} /> Font</Label>
          <Select value={style.font} onValueChange={(v) => set({ font: v })}>
            <SelectTrigger className="mt-1.5 bg-[#13161C] border-white/10" data-testid="subtitle-font"><SelectValue /></SelectTrigger>
            <SelectContent>{FONTS.map((f) => <SelectItem key={f} value={f}>{f}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-xs uppercase tracking-wide text-slate-500 font-mono">Dimensione · {style.size}</Label>
          <Slider min={28} max={110} step={2} value={[style.size]} onValueChange={([v]) => set({ size: v })} className="mt-3" data-testid="subtitle-size" />
        </div>
      </div>

      <div>
        <Label className="text-xs uppercase tracking-wide text-slate-500 font-mono">Colore testo</Label>
        <div className="flex flex-wrap gap-2 mt-2">
          {COLORS.map((c) => (
            <button key={c} onClick={() => set({ color: c })}
              data-testid={`subtitle-color-${c}`}
              className={`w-7 h-7 rounded-full border-2 transition-all ${style.color === c ? "border-cyan-400 scale-110" : "border-white/20"}`}
              style={{ backgroundColor: c }} />
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label className="text-xs uppercase tracking-wide text-slate-500 font-mono">Posizione</Label>
          <Select value={style.position} onValueChange={(v) => set({ position: v })}>
            <SelectTrigger className="mt-1.5 bg-[#13161C] border-white/10" data-testid="subtitle-position"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="bottom">In basso</SelectItem>
              <SelectItem value="center">Centro</SelectItem>
              <SelectItem value="top">In alto</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-xs uppercase tracking-wide text-slate-500 font-mono">Allineamento</Label>
          <Select value={style.alignment} onValueChange={(v) => set({ alignment: v })}>
            <SelectTrigger className="mt-1.5 bg-[#13161C] border-white/10" data-testid="subtitle-align"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="left">Sinistra</SelectItem>
              <SelectItem value="center">Centro</SelectItem>
              <SelectItem value="right">Destra</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3">
        <ToggleRow label="Grassetto" checked={style.bold} onChange={(v) => set({ bold: v })} testid="subtitle-bold" />
        <ToggleRow label="Ombra" checked={style.shadow} onChange={(v) => set({ shadow: v })} testid="subtitle-shadow" />
        <ToggleRow label="Sfondo dietro il testo" checked={style.background} onChange={(v) => set({ background: v })} testid="subtitle-bg" />
      </div>
    </div>
  );
};

const ToggleRow = ({ label, checked, onChange, testid }) => (
  <div className="flex items-center justify-between bg-[#13161C] border border-white/10 rounded-lg px-3.5 py-2.5">
    <span className="text-sm text-slate-200">{label}</span>
    <Switch checked={checked} onCheckedChange={onChange} data-testid={testid} />
  </div>
);

export default SubtitleStyleEditor;
