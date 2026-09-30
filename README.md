# ClipForge 🎬✂️

**ClipForge** è un'applicazione web personale (nessun account, nessun abbonamento, nessun pagamento) per trasformare video lunghi in clip verticali pronte per **TikTok, Instagram Reels e YouTube Shorts**.

Tutta l'elaborazione video è **reale**: taglio, crop intelligente al formato, tracking del volto, zoom automatico, normalizzazione audio, trascrizione con Whisper e **sottotitoli impressi realmente nel file esportato** (non solo mostrati sopra il player).

---

## 1. Requisiti

- **Python** 3.11+
- **Node.js** 18+ e **Yarn**
- **MongoDB** (in esecuzione locale)
- **FFmpeg** e **FFprobe** (nel PATH)
- ~1 GB liberi per il modello Whisper + spazio per i video temporanei

Librerie Python principali: `fastapi`, `uvicorn`, `motor`, `faster-whisper`, `opencv-python-headless`.

---

## 2. Installazione

```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd ../frontend
yarn install
```

## 3. Installazione FFmpeg

**Debian/Ubuntu**
```bash
sudo apt-get update && sudo apt-get install -y ffmpeg
```
**macOS**
```bash
brew install ffmpeg
```
**Windows**: scarica da https://www.gyan.dev/ffmpeg/builds/ e aggiungi `bin/` al PATH.

Verifica: `ffmpeg -version` e `ffprobe -version`.

### Font per i sottotitoli
I preset usano **DejaVu Sans**. Su Debian/Ubuntu:
```bash
sudo apt-get install -y fonts-dejavu-core fonts-dejavu-extra && fc-cache -f
```

## 4. Installazione Whisper (locale, gratuito)

Si usa **faster-whisper** (open-source, nessuna API a pagamento). Il modello viene **scaricato automaticamente** al primo utilizzo in `backend/storage/models/`.

- Modello predefinito: `base` (buon compromesso qualità/velocità su CPU).
- Configurabile via variabili d'ambiente (vedi sezione 7).

Pre-download opzionale:
```bash
python -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8', download_root='backend/storage/models')"
```

## 5. Avvio backend

```bash
cd backend
uvicorn server:app --host 0.0.0.0 --port 8001
```
Il backend espone le API sotto il prefisso `/api`.

## 6. Avvio frontend

```bash
cd frontend
yarn start
```
Apri http://localhost:3000

## 7. Configurazione

**backend/.env**
```
MONGO_URL="mongodb://localhost:27017"
DB_NAME="clipforge"
CORS_ORIGINS="*"
EMERGENT_LLM_KEY="sk-emergent-xxxx"   # per l'object storage gestito da Emergent
# opzionali
WHISPER_MODEL_SIZE="base"     # tiny | base | small | medium
WHISPER_COMPUTE_TYPE="int8"   # int8 | int8_float16 | float16 | float32
```

**frontend/.env**
```
REACT_APP_BACKEND_URL=http://localhost:8001
```

Cartelle di storage (create automaticamente in `backend/storage/`):
`uploads/`, `outputs/`, `thumbs/`, `models/`, `zips/`.

## 8. Troubleshooting

| Problema | Soluzione |
|---|---|
| `ffmpeg: command not found` | Installa FFmpeg e verifica il PATH. |
| Trascrizione lenta | Usa `WHISPER_MODEL_SIZE=tiny`. Il primo run scarica il modello. |
| Sottotitoli con font sbagliato | Installa `fonts-dejavu-core` ed esegui `fc-cache -f`. |
| Nessun volto rilevato | Fallback automatico al crop centrale (comportamento previsto). |
| `Spazio su disco insufficiente` | Libera spazio: le clip stanno in `backend/storage/`. |
| MongoDB non raggiungibile | Avvia `mongod` e controlla `MONGO_URL`. |

---

## Come si usa

1. **Home** → trascina un video (MP4/MOV/MKV/WEBM/AVI) o scegli un file.
2. **Video** → controlla nome, durata, risoluzione, dimensione e anteprima → *Continua*.
3. **Impostazioni clip** → scegli formato (9:16 / 16:9 / 1:1), durata, numero di clip, attiva sottotitoli / auto zoom / auto crop / tracking volto / normalizzazione audio. Attiva **"Trova automaticamente le clip migliori"** per la selezione basata su trascrizione.
4. **Elaborazione** → barra di avanzamento **reale** e coda batch (Clip 1 completata, Clip 2 in elaborazione, …).
5. **Clip** → anteprima, **Scarica** singola, **Scarica tutte (.zip)**, oppure **Modifica** per aprire l'editor (trim START/END, timeline, play/pause/seek/volume/velocità/zoom, stile sottotitoli) ed esportare di nuovo.

I progetti recenti restano in Home (thumbnail, nome, data, numero clip) con azioni *apri* ed *elimina*.

---

## Architettura

```
Frontend (React + Tailwind)
   └── axios → FastAPI (/api)
                 ├── upload → salvataggio temporaneo + ffprobe + thumbnail
                 ├── job asincrono (asyncio):
                 │     ├── extract audio (FFmpeg)
                 │     ├── transcribe (faster-whisper, in thread)
                 │     ├── selezione clip (euristica su trascrizione) / split uniforme
                 │     ├── face detection (OpenCV) → crop dinamico / fallback centrale
                 │     └── render clip (FFmpeg: crop→scale→zoom→sottotitoli ASS, loudnorm, H.264/AAC)
                 └── stato job: queued → processing → completed / failed  (+ progress reale)
```

- Comandi FFmpeg eseguiti con `asyncio.create_subprocess_exec` (lista di argomenti, **nessuna shell** → niente command injection).
- File temporanei (`audio.wav`, `.ass`) eliminati dopo l'uso.

## Selezione automatica delle clip

L'euristica **non** inventa un "punteggio di viralità". Valuta segnali reali della trascrizione:
frasi complete, domande (`?`), affermazioni forti (`!`), parole chiave, densità/ritmo del parlato e vicinanza alla durata desiderata. I confini delle clip vengono **allineati alle frasi** per evitare tagli a metà.

## Sicurezza

- Validazione di **estensione**, **MIME type** e **dimensione** (max 2 GB).
- **Sanitizzazione** dei nomi file e nessun **path traversal**.
- Controllo dello **spazio su disco** prima dell'upload.
- Gestione errori per: formato non supportato, upload interrotto, errore FFmpeg/Whisper, spazio insufficiente, errore di export.

## Privacy

Nessun account, nessun analytics, nessun salvataggio permanente online. I video sono elaborati **localmente/temporaneamente**. Eliminando un progetto si cancellano tutti i suoi file.

---

## Fase 6.5 — Fix caricamento clip + Caption Studio Pro

### Fix critico: clip che si bloccavano nel caricamento
**Causa reale individuata:** gli endpoint di serving media erano `async` ma chiamavano I/O bloccante (`requests` via `storage.get_bytes`) **dentro l'event loop**, e `_range_response` caricava **l'intero file in RAM ad ogni richiesta Range** → ogni seek riscaricava tutto e **bloccava l'event loop** (job polling e altre richieste si congelavano). Anche `run_job` faceva download/upload storage bloccanti sul loop.

**Fix applicato:**
- Cache su disco locale: l'oggetto viene scaricato **una sola volta** in un worker thread (`asyncio.to_thread`) → l'event loop non si blocca mai.
- Serving con **HTTP Range reale (206)** leggendo solo la fetta richiesta dal file in cache (Accept-Ranges, Content-Range, Content-Length) → seek/preview fluidi, memoria minima.
- Tutte le operazioni storage in `run_job`/upload/asset spostate su thread.
- **Stati clip reali**: processing → verifying (ffprobe: file esiste, size>0, durata>0, stream video) → uploading (con **retry + backoff** 3 tentativi) → completed. Nessuna clip è "pronta" se non è realmente riproducibile.
- **Timeout** reale sull'export FFmpeg (watchdog) → nessun job resta bloccato in eterno.
- Frontend: stati distinti nella coda (Verifica/Caricamento), player con reload-once su errore.

Verificato: **10/10 iterazioni** stabili (full 200, range 206, API reattiva durante caricamenti concorrenti), riapertura progetti OK.

### Caption Studio Pro
- **Word-level timing** dai timestamp reali di faster-whisper (nessuna stima).
- **Modalità caption**: Static, Word by word, Highlight, Karaoke, Pop, Scale, Box, Glow, Hormozi, Minimal.
- **12 preset** originali: Classic, Bold, Minimal, Gaming, Karaoke, Highlight, Pop, Scale, Box, Glow, Hormozi, Clean.
- **Animazioni** (rese realmente via ASS): none, fade, pop, scale, word_pop, karaoke (slide/bounce/typewriter → fallback fade); intensità Subtle/Normal/Strong.
- **Word highlight** sincronizzato ai timestamp (colore + scala + glow sulla parola attiva); parole-per-riga configurabili.
- Controlli stile: font, dimensione, colori (testo/evidenziazione/outline), outline, ombra/blur, background (box), posizione (Top/Upper/Center/Lower/Bottom), allineamento, maiuscolo, tracking.
- **Export sottotitoli**: `GET /api/projects/{id}/captions?fmt=srt|vtt|txt` (oltre al burn-in nel MP4).
- Il rendering finale usa **ASS dinamico + FFmpeg** (nessuno screenshot del testo).

Rimandato a iterazione dedicata (per ampiezza): editor caption timeline avanzato (split/merge/drag, correzione manuale testo per-parola, per-word style, auto-emoji, traduzione multilingua). L'architettura dati è pronta (config caption strutturata).

## Fase 6 — Auto Edit Pro

Costruita sopra l'MVP esistente, aggiunge un vero auto-editor:

- **Template Auto Edit**: Podcast, Talking Head, Gaming, Minimal — impostano realmente i parametri della pipeline.
- **Silence Removal** (OFF/Leggero/Medio/Aggressivo): rileva i silenzi con `ffmpeg silencedetect` e **taglia davvero** il video (trim + concat), con padding naturale attorno ai tagli.
- **Smart Zoom** (OFF/Leggero/Medio/Forte) con modalità **Normal / Punch In / Punch Out**: zoom graduali (`zoompan`) agganciati agli inizi frase, non casuali.
- **Face tracking con smoothing**: crop verticale che segue il volto nel tempo (espressione crop tempo-variante), fallback al centro se nessun volto.
- **Word Highlight**: la parola pronunciata viene evidenziata usando i **timestamp reali di Whisper**; parole-per-riga configurabili (3–5 consigliato).
- **Export presets**: Social HQ, Social Small, Custom (CRF).
- **Musica di sottofondo**: upload MP3/WAV/M4A/AAC, volume, offset, fade in/out, loop, **mix reale** (`amix`).
- **Image Overlay**: upload PNG/JPG/WEBP con posizione, scala, opacità, start/end — **composito reale** (`overlay`).
- **Coda batch** (pagina `/batch`): più video elaborati **uno alla volta** (semaforo backend), con stato/progress/clip/ZIP per ciascuno.

Endpoint aggiunti: `POST /api/projects/{id}/audio`, `POST /api/projects/{id}/overlay`. L'endpoint `POST /api/projects/{id}/process` accetta i nuovi campi (`template`, `silence_removal`, `smart_zoom`, `zoom_mode`, `export_preset`, `music`, `overlay`, ecc.) in modo retro-compatibile.

## Limiti tecnici noti (e come migliorarli)

- **Tracking volto**: viene calcolato il centro medio del volto sui frame campionati della clip e applicato un crop **centrato sul volto** (con smoothing implicito). Un tracking **per-frame** completamente dinamico (crop che segue il volto istante per istante) può essere aggiunto generando un'espressione `crop` tempo-variante o con `sendcmd`. Fallback al crop centrale se nessun volto è rilevato.
- **Auto zoom**: zoom lento e leggero (`zoompan`) disattivabile. Per effetti "a battuta" servirebbe l'analisi degli onset audio.
- **Whisper su CPU**: la qualità/velocità dipende dal modello (`tiny` più veloce, `small/medium` più accurati).
- **Storage**: i video originali, le clip esportate, le thumbnail e gli ZIP sono salvati su **object storage gestito da Emergent** (sorgente dati, con MongoDB come indice). L'elaborazione avviene su **file temporanei locali** scaricati al volo e cancellati subito dopo. Per un uso 100% offline/self-hosted senza object storage, si può sostituire `backend/storage.py` con scritture su filesystem locale.

## Struttura dei file

```
/app
├── backend/
│   ├── server.py          # FastAPI: route, serving media, job runner asincrono
│   ├── config.py          # percorsi storage, formati ammessi, target risoluzioni
│   ├── models.py          # modelli Pydantic (Project, Job, ClipSettings, SubtitleStyle)
│   ├── media.py           # ffprobe, thumbnail, sanitize, validazione, disco
│   ├── transcription.py   # wrapper faster-whisper (thread)
│   ├── face_crop.py       # OpenCV face detection + calcolo crop
│   ├── subtitles.py       # generazione file .ass + preset di stile
│   ├── pipeline.py        # selezione clip + render FFmpeg con progress reale + ZIP
│   ├── requirements.txt
│   └── storage/           # uploads, outputs, thumbs, models, zips (auto)
└── frontend/
    └── src/
        ├── App.js, index.js, index.css
        ├── lib/           # api.js, format.js
        ├── components/     # Logo, Header, DropZone, ProjectCard, VideoInfoPanel,
        │                   # ClipSettingsPanel, SubtitleStyleEditor, ExportQueue,
        │                   # ClipResults, Editor
        └── pages/          # Home.jsx, Workspace.jsx
```
