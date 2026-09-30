import { Scissors, Play } from "lucide-react";

export const Logo = ({ size = 36, withText = true, testId = "clipforge-logo" }) => {
  return (
    <div className="flex items-center gap-2.5 select-none" data-testid={testId}>
      <div
        className="relative flex items-center justify-center rounded-xl bg-cyan-500/10 border border-cyan-500/30"
        style={{ width: size, height: size }}
      >
        <Scissors size={size * 0.42} className="text-cyan-400 absolute -translate-x-[3px] -translate-y-[1px]" strokeWidth={2.4} />
        <Play size={size * 0.34} className="text-cyan-300 absolute translate-x-[6px] translate-y-[4px] fill-cyan-300" strokeWidth={0} />
      </div>
      {withText && (
        <span className="font-display font-extrabold tracking-tight text-slate-50" style={{ fontSize: size * 0.58 }}>
          Clip<span className="text-cyan-400">Forge</span>
        </span>
      )}
    </div>
  );
};

export default Logo;
