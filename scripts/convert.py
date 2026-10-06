"""Normalize any downloaded file into WAV, MP3 or MP4 using ffmpeg."""
import json
import os
import subprocess


def probe(path: str) -> dict:
    """Return {'duration': float|None, 'width': int|None, 'height': int|None} via ffprobe."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=width,height", "-of", "json", path],
        check=True, capture_output=True, text=True,
    ).stdout
    data = json.loads(out or "{}")
    dur = data.get("format", {}).get("duration")
    w = h = None
    for s in data.get("streams", []):
        if s.get("width"):
            w, h = s["width"], s["height"]
            break
    return {"duration": float(dur) if dur else None, "width": w, "height": h}


def normalize(src_path: str, out_dir: str, target_kind: str) -> str:
    """target_kind: 'audio_wav', 'audio_mp3', or 'video_mp4'.
    Returns the final output path. Re-encodes only if the source
    isn't already in the target format.
    """
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(src_path))[0]
    ext = os.path.splitext(src_path)[1].lower()

    if target_kind == "audio_wav":
        out_path = os.path.join(out_dir, base + ".wav")
        if ext == ".wav":
            os.replace(src_path, out_path)
            return out_path
        cmd = ["ffmpeg", "-y", "-i", src_path, "-vn", "-ar", "44100", out_path]
    elif target_kind == "audio_mp3":
        out_path = os.path.join(out_dir, base + ".mp3")
        if ext == ".mp3":
            os.replace(src_path, out_path)
            return out_path
        cmd = ["ffmpeg", "-y", "-i", src_path, "-vn", "-codec:a", "libmp3lame",
               "-qscale:a", "2", out_path]
    elif target_kind == "video_mp4":
        out_path = os.path.join(out_dir, base + ".mp4")
        if ext == ".mp4":
            os.replace(src_path, out_path)
            return out_path
        cmd = ["ffmpeg", "-y", "-i", src_path,
               "-vf", "scale='min(1920,iw)':-2",
               "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
               "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart",
               out_path]
    else:
        raise ValueError(f"Unknown target_kind: {target_kind}")

    subprocess.run(cmd, check=True, capture_output=True)
    if os.path.exists(src_path) and src_path != out_path:
        os.remove(src_path)
    return out_path
