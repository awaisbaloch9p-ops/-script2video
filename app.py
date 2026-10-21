import asyncio, json, os, re, tempfile
import requests, streamlit as st, edge_tts
from anthropic import Anthropic
from moviepy import VideoFileClip, AudioFileClip, concatenate_videoclips
from moviepy.video.fx import Loop

def secret(name):
    try:
        v = st.secrets.get(name)
    except Exception:
        v = None
    return v or os.environ.get(name, "")

MAX_LINES = 25

VOICES = {
    "Urdu (male)": "ur-PK-AsadNeural", "Urdu (female)": "ur-PK-UzmaNeural",
    "Hindi (male)": "hi-IN-MadhurNeural",
    "English (male)": "en-US-GuyNeural", "English (female)": "en-US-JennyNeural",
}

def split_lines(text):
    parts = []
    for p in re.split(r"\n+", text.replace("\r", "")):
        parts += re.split(r"(?<=[.!?۔؟])\s+", p)
    return [x.strip() for x in parts if len(x.strip()) > 1]

def plan_scenes(lines, niche):
    numbered = "\n".join(f"{i+1}. {l}" for i, l in enumerate(lines))
    prompt = f"""You are a video director for faceless YouTube videos in the "{niche}" niche.
The script below may be Urdu, Roman Urdu or English. For each numbered line, write stock-footage search
queries (English, 2-4 words, REAL people and real places when the line allows, e.g. "tired woman bed night",
"doctor talking patient", "ancient ruins aerial"). Give a main query and a simpler fallback query.
Return ONLY a JSON array of exactly {len(lines)} items: [{{"queries":["main","fallback"]}}, ...]

{numbered}"""
    r = Anthropic().messages.create(model="claude-sonnet-5-5", max_tokens=4000,
                                    messages=[{"role": "user", "content": prompt}])
    return json.loads(re.search(r"\[.*\]", r.content[0].text, re.S).group(0))

def find_clip(queries, orientation, used):
    h = {"Authorization": os.environ["PEXELS_API_KEY"]}
    tw = 1280 if orientation == "landscape" else 720
    for q in queries:
        r = requests.get("https://api.pexels.com/videos/search", headers=h, timeout=30,
                         params={"query": q, "orientation": orientation, "per_page": 8})
        r.raise_for_status()
        for v in r.json().get("videos", []):
            if v["id"] in used:
                continue
            fs = [f for f in v["video_files"] if f.get("file_type") == "video/mp4" and f.get("width")]
            if fs:
                used.add(v["id"])
                return min(fs, key=lambda f: abs(f["width"] - tw))["link"]
    return None

def download(url, path):
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for c in r.iter_content(1 << 20):
                f.write(c)

def ts(t):
    return f"{int(t//3600):02}:{int(t%3600//60):02}:{int(t%60):02},{int(t%1*1000):03}"

def build(lines, plans, voice, orientation, wd, on_step):
    W, H = (1280, 720) if orientation == "landscape" else (720, 1280)
    used, clips, srt, t = set(), [], [], 0.0
    for i, (line, plan) in enumerate(zip(lines, plans)):
        on_step(i, len(lines))
        ap = f"{wd}/a{i}.mp3"
        asyncio.run(edge_tts.Communicate(line, voice).save(ap))
        audio = AudioFileClip(ap)
        d = audio.duration + 0.25
        url = find_clip(plan["queries"], orientation, used) or find_clip(["people lifestyle"], orientation, used)
        vp = f"{wd}/v{i}.mp4"
        download(url, vp)
        v = VideoFileClip(vp).without_audio()
        v = v.with_effects([Loop(duration=d)]) if v.duration < d else v.subclipped(0, d)
        v = v.resized(max(W / v.w, H / v.h))
        v = v.cropped(x_center=v.w / 2, y_center=v.h / 2, width=W, height=H)
        clips.append(v.with_audio(audio))
        srt.append(f"{i+1}\n{ts(t)} --> {ts(t+d)}\n{line}\n")
        t += d
    out = f"{wd}/final.mp4"
    concatenate_videoclips(clips, method="compose").write_videofile(
        out, fps=30, codec="libx264", audio_codec="aac", logger=None)
    return open(out, "rb").read(), "\n".join(srt)

st.set_page_config(page_title="Script → Video", page_icon="🎬", layout="wide")
st.title("🎬 Script → Video")
# Optional access password so strangers can't spend your credits
APP_PASSWORD = secret("APP_PASSWORD")
if APP_PASSWORD:
    if st.session_state.get("ok") is not True:
        pw = st.text_input("Password", type="password")
        if pw:
            if pw == APP_PASSWORD:
                st.session_state["ok"] = True
                st.rerun()
            else:
                st.error("Galat password.")
        st.stop()

ak, pk = secret("ANTHROPIC_API_KEY"), secret("PEXELS_API_KEY")
with st.sidebar:
    if not (ak and pk):
        st.caption("Keys sirf is session mein use hoti hain")
        ak = st.text_input("Anthropic API key", type="password")
        pk = st.text_input("Pexels API key (free)", type="password")
    voice_name = st.selectbox("Voiceover", list(VOICES))
    orientation = st.radio("Format", ["landscape", "portrait"], format_func=lambda x: "16:9 YouTube" if x == "landscape" else "9:16 Shorts")
niche = st.selectbox("Niche", ["health", "psychology", "history", "general"])
script = st.text_area("Apni script yahan paste karo", height=260)

if st.button("🎥 Video banao", type="primary"):
    if not (ak and pk):
        st.error("API keys set nahi hain.")
    elif not script.strip():
        st.error("Pehle script paste karo.")
    elif len(split_lines(script)) > MAX_LINES:
        st.error(f"Script bohat lambi hai. Ek dafa mein maximum {MAX_LINES} lines rakho, baaki alag video mein banao.")
    else:
        os.environ["ANTHROPIC_API_KEY"], os.environ["PEXELS_API_KEY"] = ak, pk
        lines = split_lines(script)
        bar = st.progress(0, text="Scenes plan ho rahe hain...")
        try:
            plans = plan_scenes(lines, niche)
            with tempfile.TemporaryDirectory() as wd:
                video, srt = build(lines, plans, VOICES[voice_name], orientation, wd,
                                   lambda i, n: bar.progress(i / n, text=f"Scene {i+1}/{n}: voice + footage + edit..."))
            bar.progress(1.0, text="Ho gaya ✓")
            st.video(video)
            c1, c2 = st.columns(2)
            c1.download_button("⬇ MP4 download", video, "video.mp4", "video/mp4")
            c2.download_button("⬇ Subtitles (.srt)", srt, "subtitles.srt")
        except Exception as e:
            st.error(f"Error: {e}")
