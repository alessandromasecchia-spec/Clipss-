import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { Sparkles, FolderClock, ShieldCheck, Zap } from "lucide-react";
import Header from "@/components/Header";
import DropZone from "@/components/DropZone";
import ProjectCard from "@/components/ProjectCard";
import { Logo } from "@/components/Logo";
import { api } from "@/lib/api";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";

export default function Home() {
  const navigate = useNavigate();
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [projects, setProjects] = useState([]);
  const [toDelete, setToDelete] = useState(null);

  const loadProjects = async () => {
    try {
      const { data } = await api.listProjects();
      setProjects(data);
    } catch (e) { /* ignore */ }
  };

  useEffect(() => { loadProjects(); }, []);

  const handleFile = async (file, err) => {
    if (err) { toast.error(err); return; }
    if (!file) return;
    setUploading(true);
    setProgress(0);
    try {
      const { data } = await api.upload(file, setProgress);
      toast.success("Video caricato con successo");
      navigate(`/project/${data.id}`);
    } catch (e) {
      const msg = e?.response?.data?.detail || "Errore durante il caricamento";
      toast.error(msg);
      setUploading(false);
    }
  };

  const confirmDelete = async () => {
    if (!toDelete) return;
    try {
      await api.deleteProject(toDelete.id);
      toast.success("Progetto eliminato");
      setProjects((p) => p.filter((x) => x.id !== toDelete.id));
    } catch (e) {
      toast.error("Impossibile eliminare il progetto");
    }
    setToDelete(null);
  };

  const features = [
    { icon: Zap, label: "Elaborazione reale con FFmpeg" },
    { icon: Sparkles, label: "Auto-clip con trascrizione Whisper" },
    { icon: ShieldCheck, label: "Nessun account · nessun pagamento" },
  ];

  return (
    <div>
      <Header />
      <main className="max-w-7xl mx-auto px-5 md:px-8 py-10 md:py-16">
        <section className="text-center max-w-3xl mx-auto">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex justify-center mb-6">
            <Logo size={64} withText={false} testId="hero-logo" />
          </motion.div>
          <motion.h1
            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}
            className="font-display text-4xl md:text-6xl font-extrabold tracking-tight text-slate-50"
          >
            Clip<span className="text-cyan-400">Forge</span>
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
            className="mt-4 text-base md:text-lg text-slate-400"
          >
            Trasforma i tuoi video in clip pronte per Shorts, Reels e TikTok.
          </motion.p>

          <div className="flex flex-wrap items-center justify-center gap-2 mt-6">
            {features.map((f) => (
              <span key={f.label} className="inline-flex items-center gap-1.5 text-xs text-slate-300 bg-white/5 border border-white/10 rounded-full px-3 py-1.5">
                <f.icon size={13} className="text-cyan-400" /> {f.label}
              </span>
            ))}
          </div>
        </section>

        <motion.section
          initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}
          className="mt-10 md:mt-12 max-w-3xl mx-auto"
        >
          <DropZone onFile={handleFile} uploading={uploading} progress={progress} />
        </motion.section>

        {projects.length > 0 && (
          <section className="mt-16">
            <div className="flex items-center gap-2 mb-5">
              <FolderClock className="text-cyan-400" size={20} />
              <h2 className="font-display text-xl md:text-2xl font-bold text-slate-100">Progetti recenti</h2>
              <span className="text-xs font-mono text-slate-500">({projects.length})</span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {projects.map((p, i) => (
                <ProjectCard
                  key={p.id} project={p} index={i}
                  onOpen={(pr) => navigate(`/project/${pr.id}`)}
                  onDelete={(pr) => setToDelete(pr)}
                />
              ))}
            </div>
          </section>
        )}
      </main>

      <AlertDialog open={!!toDelete} onOpenChange={(o) => !o && setToDelete(null)}>
        <AlertDialogContent data-testid="delete-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Eliminare il progetto?</AlertDialogTitle>
            <AlertDialogDescription>
              "{toDelete?.name}" e tutte le sue clip verranno eliminate definitivamente. Questa azione non è reversibile.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="delete-cancel">Annulla</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete} data-testid="delete-confirm" className="bg-rose-600 hover:bg-rose-500">
              Elimina
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
