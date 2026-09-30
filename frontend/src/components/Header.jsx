import { useNavigate } from "react-router-dom";
import { Logo } from "@/components/Logo";
import { Github } from "lucide-react";

export const Header = ({ right }) => {
  const navigate = useNavigate();
  return (
    <header className="sticky top-0 z-50 backdrop-blur-xl bg-[#0B0D11]/80 border-b border-white/10">
      <div className="max-w-7xl mx-auto px-5 md:px-8 h-16 flex items-center justify-between">
        <button onClick={() => navigate("/")} data-testid="header-home-btn" className="active:scale-95 transition-transform">
          <Logo size={34} />
        </button>
        <div className="flex items-center gap-3">
          {right}
          <span className="hidden md:inline-flex items-center gap-1.5 text-xs font-mono text-slate-500 border border-white/10 rounded-full px-3 py-1">
            <Github size={13} /> uso personale · locale
          </span>
        </div>
      </div>
    </header>
  );
};

export default Header;
