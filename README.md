# Script → Video

Script paste karo: Claude har line ke liye scenes plan karta hai, Pexels se real footage (insaan, jagahen) aati hai,
edge-tts voiceover banata hai aur MP4 ban jati hai (saath mein .srt subtitles).

## Setup (ek baar)
1. Python 3.10+ aur FFmpeg install karo (ffmpeg.org).
2. `pip install -r requirements.txt`
3. Keys lo: Anthropic (console.anthropic.com) aur Pexels (pexels.com/api, free).
4. `streamlit run app.py`  (browser mein khul jayega, keys sidebar mein daalo)

## Notes
- Footage Pexels ki free stock hai (asli insaan), AI-generated nahi. Pexels ki license mein commercial use allowed hai.
- Lambi script mein time lagta hai (har scene download + render hota hai).
