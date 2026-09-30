// Real, config-driven caption preview.
// Mirrors the backend ASS engine (subtitles.py build_ass) so what you see here
// matches what FFmpeg burns into the exported MP4. Single source of truth = `style`.

const PER_WORD = ["highlight", "hormozi", "pop", "scale", "glow"];

// Which words are "spoken so far" is driven by activeIndex (a stand-in for the
// real Whisper timestamp at the current video time). Same concept as export.
export const CaptionPreview = ({
  style,
  words = ["TO", "GET", "STARTED"],
  activeIndex = 1,
  baseFont = 30,
  className = "",
}) => {
  const s = style || {};
  const mode = s.mode || "highlight";
  const upper = s.uppercase || mode === "hormozi";
  const bold = s.bold || (s.font_weight || 0) >= 700;
  const outline = Math.max(0, s.outline ?? 3);
  const hl = s.highlight_color || "#FFE600";
  const baseColor = s.color || "#FFFFFF";

  // font size relative to the ASS size, clamped so big presets still fit the box
  const fontSize = Math.max(14, Math.min(baseFont * 1.9, (s.size || 60) * (baseFont / 60)));

  const strokeW = outline > 0 ? Math.max(0.5, Math.min(3, outline * 0.45)) : 0;
  const textShadow =
    s.shadow ? "2px 3px 5px rgba(0,0,0,0.85)" : "none";

  const lineGlow = mode === "glow" ? `0 0 ${fontSize * 0.35}px ${hl}` : "";

  // box modes render the whole line inside a rounded background (matches export)
  const wholeBox = mode === "box" || s.background || s.bg_mode === "box" || s.bg_mode === "full";

  const renderWords = mode === "word_by_word" ? [words[activeIndex] || words[0]] : words;
  const activeReal = mode === "word_by_word" ? 0 : activeIndex;

  const wordStyle = (i) => {
    const st = {
      color: baseColor,
      display: "inline-block",
      transition: "transform .18s ease, color .18s ease",
      WebkitTextStroke: strokeW ? `${strokeW}px #000` : undefined,
      paintOrder: "stroke fill",
      textShadow,
    };
    if (mode === "karaoke") {
      st.color = i <= activeReal ? hl : baseColor;
      return st;
    }
    if (!PER_WORD.includes(mode)) return st;
    if (i !== activeReal) return st;
    // active word treatment per mode (same as _decorate in subtitles.py)
    st.color = hl;
    if (mode === "pop" || mode === "scale") st.transform = "scale(1.18)";
    if (mode === "glow") st.textShadow = `0 0 ${fontSize * 0.5}px ${hl}, ${textShadow}`;
    return st;
  };

  return (
    <div
      className={`relative flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-center leading-tight ${className}`}
      style={{
        fontFamily: s.font || "DejaVu Sans, sans-serif",
        fontWeight: bold ? 800 : 500,
        fontSize,
        letterSpacing: (s.tracking || 0) * 0.4,
        textShadow: lineGlow || undefined,
        ...(wholeBox
          ? {
              backgroundColor: hexA(s.bg_color || "#111111", s.bg_opacity ?? 0.75),
              borderRadius: fontSize * 0.22,
              padding: `${fontSize * 0.12}px ${fontSize * 0.28}px`,
            }
          : {}),
      }}
    >
      {renderWords.map((w, i) => (
        <span key={i} style={wordStyle(i)}>
          {upper ? String(w).toUpperCase() : w}
        </span>
      ))}
    </div>
  );
};

function hexA(hex, op) {
  const h = (hex || "#111111").replace("#", "");
  const r = parseInt(h.slice(0, 2) || "11", 16);
  const g = parseInt(h.slice(2, 4) || "11", 16);
  const b = parseInt(h.slice(4, 6) || "11", 16);
  return `rgba(${r},${g},${b},${Math.max(0, Math.min(1, op))})`;
}

export default CaptionPreview;
