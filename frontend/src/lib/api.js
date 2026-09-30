import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const http = axios.create({ baseURL: API });

export const mediaUrl = (path) => `${API}${path}`;

export const api = {
  upload: (file, onProgress) => {
    const form = new FormData();
    form.append("file", file);
    return http.post("/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (e) => {
        if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
      },
    });
  },
  listProjects: () => http.get("/projects"),
  getProject: (id) => http.get(`/projects/${id}`),
  deleteProject: (id) => http.delete(`/projects/${id}`),
  process: (id, settings) => http.post(`/projects/${id}/process`, settings),
  renderClip: (id, payload) => http.post(`/projects/${id}/render-clip`, payload),
  getJob: (jobId) => http.get(`/jobs/${jobId}`),
  uploadAudio: (id, file) => {
    const form = new FormData();
    form.append("file", file);
    return http.post(`/projects/${id}/audio`, form, { headers: { "Content-Type": "multipart/form-data" } });
  },
  uploadOverlay: (id, file) => {
    const form = new FormData();
    form.append("file", file);
    return http.post(`/projects/${id}/overlay`, form, { headers: { "Content-Type": "multipart/form-data" } });
  },
};
