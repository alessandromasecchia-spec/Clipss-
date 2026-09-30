import { useRef, useState } from "react";
import { UploadCloud, Film, Loader2 } from "lucide-react";
import { Progress } from "@/components/ui/progress";

const ACCEPT = ".mp4,.mov,.mkv,.webm,.avi";
const ALLOWED = ["mp4", "mov", "mkv", "webm", "avi"];

export const DropZone = ({ onFile, uploading, progress }) => {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  const handleFiles = (files) => {
    if (!files || !files.length) return;
    const f = files[0];
    const ext = f.name.split(".").pop().toLowerCase();
    if (!ALLOWED.includes(ext)) {
      onFile(null, `Formato non supportato: .${ext}`);
      return;
    }
    onFile(f);
  };

  return (
    <div
      data-testid="dropzone"
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => { e.preventDefault(); setDragging(false); if (!uploading) handleFiles(e.dataTransfer.files); }}
      onClick={() => !uploading && inputRef.current?.click()}
      className={`relative rounded-2xl border-2 border-dashed p-10 md:p-16 text-center cursor-pointer transition-all group
        ${dragging ? "border-cyan-400 bg-cyan-500/5" : "border-cyan-500/25 bg-[#13161C]/60 hover:border-cyan-400/70 hover:bg-[#1A1D26]"}`}
    >
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        className="hidden"
        data-testid="file-input"
        onChange={(e) => handleFiles(e.target.files)}
      />
      {uploading ? (
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-12 h-12 text-cyan-400 animate-spin" />
          <p className="text-slate-200 font-medium">Caricamento in corso… {progress}%</p>
          <div className="w-full max-w-sm">
            <Progress value={progress} data-testid="upload-progress" className="h-2" />
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center group-hover:scale-105 transition-transform">
            <UploadCloud className="w-8 h-8 text-cyan-400" />
          </div>
          <div>
            <p className="font-display text-xl md:text-2xl font-bold text-slate-100">Trascina qui il tuo video</p>
            <p className="text-slate-400 mt-1 text-sm">oppure <span className="text-cyan-400 font-semibold underline underline-offset-4">scegli un file</span></p>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-2 mt-2">
            {ALLOWED.map((x) => (
              <span key={x} className="inline-flex items-center gap-1 text-[11px] font-mono uppercase text-slate-400 bg-white/5 border border-white/10 rounded-md px-2 py-0.5">
                <Film size={11} /> {x}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default DropZone;
