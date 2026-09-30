# ClipForge — PRD

## Problema originale
App web personale (no account, no pagamenti, no abbonamenti) alternativa a CapCut: trasforma video lunghi in clip verticali per TikTok/Reels/Shorts. Stack: React + Tailwind (frontend), FastAPI (backend), FFmpeg + OpenCV (video), Whisper locale (trascrizione). Elaborazione video **reale**, non mockup.

## Scelte utente
- Whisper: **locale** `faster-whisper` modello `base` (nessuna API a pagamento).
- Frontend: React + Tailwind (ambiente CRA), non Vite/TS.
- Face tracking: OpenCV Haar (crop centrato sul volto, fallback centrale) + zoom leggero.
- Auto-clip: euristica reale su trascrizione (no punteggio di viralità inventato).

## Architettura
- FastAPI con job asincroni (asyncio.create_task), stato queued/processing/completed/failed + **progress reale** parsato da `ffmpeg -progress`.
- Storage: object storage gestito da Emergent per video/clip/thumb/zip; MongoDB come indice; elaborazione ffmpeg/whisper/opencv su file temporanei locali scaricati al volo e ripuliti. Serving via backend con supporto HTTP Range (seeking video).
- Pipeline per clip: crop (face-aware) → scale/pad al target → auto-zoom opz. → sottotitoli ASS burn-in → loudnorm → H.264/AAC 1080x1920.
- FFmpeg via subprocess con lista argomenti (no shell → no injection). Validazione estensione/MIME/size, sanitize filename, controllo disco.

## Persona
Creator/editor singolo che vuole generare rapidamente clip verticali dai propri video, in locale, senza costi.

## Requisiti core (statici)
- Upload multi-formato (MP4/MOV/MKV/WEBM/AVI) con metadati + anteprima.
- Impostazioni clip: formato 9:16/16:9/1:1, durata 15/30/45/60/custom, n. clip 1/3/5/10, toggle sottotitoli/zoom/crop/face/audio-norm, modalità auto-find.
- Auto-clip via trascrizione con confini a frase.
- Sottotitoli Whisper impressi realmente (preset Classico/Bold/Gaming/Minimal + editing).
- Crop verticale intelligente (face detection, fallback centro), no deformazione.
- Editor: preview + trim START/END + timeline + play/pause/seek/volume/mute/velocità/zoom.
- Export MP4 H.264/AAC 1080x1920, progress reale, batch queue, ZIP "scarica tutte".
- Progetti recenti (thumbnail/nome/data/n.clip, apri/elimina), metadati locali.
- Privacy: no account/analytics, storage temporaneo/locale.

## Implementato (2026-06 / iter 1)
- ✅ Backend completo: upload+validazione, ffprobe, thumbnail, job asincroni con progress reale, selezione auto-clip euristica, split uniforme, face-crop OpenCV, sottotitoli ASS burn-in, loudnorm, H.264/AAC, ZIP, cleanup temp, serving media con range.
- ✅ Frontend completo: Home (drag&drop, progetti recenti), Workspace stepper (Video→Impostazioni→Elaborazione→Clip), pannello impostazioni, editor stile sottotitoli con anteprima live, coda export, risultati con download/ZIP, Editor con timeline e trim + re-export.
- ✅ Test reali eseguiti: upload→process→2 clip 1080x1920 H.264 (verificato ffprobe); trascrizione Whisper + auto-clip a confini di frase + sottotitoli **verificati impressi** su frame estratto; ZIP generato; progress reale.
- ✅ README completo (requisiti, installazione, FFmpeg, Whisper, avvio, config, troubleshooting, limiti).

## Fase 6.5 — Fix caricamento clip + Caption Studio Pro (2026-06 / iter 3)
- ✅ FIX STALL (causa reale): I/O storage bloccante (`requests`) dentro handler async + `_range_response` che caricava l'intero file in RAM per ogni Range → event loop bloccato ad ogni seek. Fix: cache disco (download once via `asyncio.to_thread`) + serving Range 206 leggendo solo la fetta dal file locale + tutte le op storage su thread. Stati clip reali (processing→verifying(ffprobe)→uploading(retry+backoff)→completed) + timeout FFmpeg. Verificato 10/10 stabile, riapertura progetti OK.
- ✅ Caption Studio Pro: word-timing reale Whisper; 10 modalità (static/word_by_word/highlight/karaoke/pop/scale/box/glow/hormozi/minimal) rese via ASS+FFmpeg; 12 preset; animazioni (fade/pop/scale/word_pop/karaoke; slide/bounce/typewriter→fallback); word highlight (colore+scala+glow) sincronizzato; parole-per-riga; controlli stile estesi; export SRT/VTT/TXT (`GET /projects/{id}/captions`). Verificato con frame estratti (pop scala parola attiva, karaoke sweep cyan→bianco).
- ✅ Frontend: SubtitleStyleEditor esteso (mode/animation select + 12 preset + word-highlight + colori), stati coda Verifica/Caricamento, player reload-once, export caption in ClipResults.
- ⏸️ Rimandato: editor caption timeline (split/merge/drag, correzione testo per-parola, per-word style, auto-emoji, traduzione multilingua). Modello dati caption già strutturato.

## Fase 6 — Auto Edit Pro (2026-06 / iter 2)
- ✅ Backend reale: silence removal (silencedetect+trim/concat, taglio verificato 9.09s→6.0s / 20.84s gap-clip accorciato), smart zoom (normal/punch_in/punch_out via zoompan agganciato alle frasi), face tracking con smoothing (crop tempo-variante) + fallback centro, word-highlight sottotitoli con timestamp reali Whisper, parole-per-riga, export presets (social_hq/social_small/custom CRF), mix musica (amix + volume/offset/fade/loop), image overlay (posizione/scala/opacità/start-end), coda batch serializzata (asyncio.Semaphore(1)).
- ✅ Endpoint aggiunti: POST /audio, POST /overlay; /process esteso retro-compatibile.
- ✅ Frontend: pannello Auto Edit (template, silence, smart zoom+mode, export, musica, overlay, word-highlight, parole/riga), pulsante "Genera Auto Edit", pagina /batch multi-video, export preset nell'editor.
- ✅ Testing agent: backend 8/8 (+9/9 precedenti), frontend 100% (tutti i testid, flusso completo, template, editor, batch). Fix bug LOW: rimosso <button> annidato (Switch) in autofind-toggle.
- ⏸️ Rimandato (richiesta utente): editor avanzato Split/Delete/Undo/Redo timeline multi-segmento.

## Backlog / prossimi
- P1: Tracking volto per-frame (crop tempo-variante) invece del centro medio.
- P1: Sottotitoli parola-per-parola (karaoke) con evidenziazione.
- P2: Onset audio per zoom "a battuta".
- P2: Storage a oggetti opzionale per deploy cloud multi-istanza.
- P2: Anteprima crop/9:16 in tempo reale nell'editor.
