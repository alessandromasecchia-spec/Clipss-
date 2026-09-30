import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import Home from "@/pages/Home";
import Workspace from "@/pages/Workspace";
import BatchQueue from "@/pages/BatchQueue";

function App() {
  return (
    <div className="App cf-grid-bg min-h-screen">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/project/:id" element={<Workspace />} />
          <Route path="/batch" element={<BatchQueue />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" richColors theme="dark" />
    </div>
  );
}

export default App;
