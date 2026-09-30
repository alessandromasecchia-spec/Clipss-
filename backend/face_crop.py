import logging
from pathlib import Path

import cv2

logger = logging.getLogger(__name__)

_cascade = None


def _get_cascade():
    global _cascade
    if _cascade is None:
        _cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
    return _cascade


def detect_face_center_x(video_path: Path, start: float, end: float, samples: int = 8):
    """Sample frames in [start,end], detect faces, return median face center x
    in source pixels, or None if no faces detected."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None
    cascade = _get_cascade()
    centers = []
    duration = max(0.1, end - start)
    try:
        for i in range(samples):
            t = start + duration * (i + 0.5) / samples
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
            if len(faces) == 0:
                continue
            # pick the largest face
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            centers.append(x + w / 2.0)
    finally:
        cap.release()

    if not centers:
        return None
    centers.sort()
    return centers[len(centers) // 2]


def detect_face_track(video_path: Path, start: float, dur: float, samples: int = 12):
    """Sample faces across [start, start+dur]. Returns (points, median_center)
    where points is a smoothed list of (t_rel, center_x) with t_rel 0-based over
    the clip. Empty points -> caller uses center fallback."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return [], None
    cascade = _get_cascade()
    raw = []
    dur = max(0.1, dur)
    try:
        for i in range(samples):
            t_rel = dur * (i + 0.5) / samples
            cap.set(cv2.CAP_PROP_POS_MSEC, (start + t_rel) * 1000.0)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
            if len(faces) == 0:
                continue
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            raw.append((round(t_rel, 3), x + w / 2.0))
    finally:
        cap.release()

    if not raw:
        return [], None
    # moving-average smoothing on center_x
    xs = [c for _, c in raw]
    smooth = []
    win = 2
    for i in range(len(raw)):
        lo = max(0, i - win)
        hi = min(len(raw), i + win + 1)
        avg = sum(xs[lo:hi]) / (hi - lo)
        smooth.append((raw[i][0], avg))
    med = sorted(xs)[len(xs) // 2]
    return smooth, med


def compute_crop(src_w: int, src_h: int, aspect: str, face_center_x=None):
    """Return (crop_w, crop_h, x, y) to crop src to target aspect without distortion,
    centered on face_center_x horizontally when provided."""
    ar_map = {"9:16": (9, 16), "16:9": (16, 9), "1:1": (1, 1)}
    tw, th = ar_map.get(aspect, (9, 16))
    target_ratio = tw / th
    src_ratio = src_w / src_h

    if src_ratio > target_ratio:
        # source too wide -> crop width (horizontal crop)
        crop_h = src_h
        crop_w = int(round(src_h * target_ratio))
        crop_w -= crop_w % 2
        if face_center_x is not None:
            x = int(round(face_center_x - crop_w / 2))
        else:
            x = (src_w - crop_w) // 2
        x = max(0, min(x, src_w - crop_w))
        y = 0
    else:
        # source too tall/narrow -> crop height (vertical crop, center)
        crop_w = src_w
        crop_h = int(round(src_w / target_ratio))
        crop_h -= crop_h % 2
        x = 0
        y = max(0, (src_h - crop_h) // 2)
    return crop_w, crop_h, x, y
