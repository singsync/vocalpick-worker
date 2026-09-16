# =========================================================================
# 🎤 VocalPickPick RunPod GPU Worker Handler (Auto-Install & Safety Version)
# =========================================================================

import subprocess
import sys
import os

print("📦 RunPod GPU 필수 패키지 환경 확인 및 자동 설치 중...")
required_packages = ["audio-separator", "noisereduce", "pyloudnorm", "librosa", "soundfile", "runpod"]
for package in required_packages:
    pip_name = package
    import_name = package.replace("-", "_")
    try:
        __import__(import_name)
    except ImportError:
        print(f"📥 누락된 패키지 설치 중: {pip_name}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pip_name])

import gc
import json
import traceback
import requests
import torch
import numpy as np
import soundfile as sf
import pyloudnorm as pyln
import noisereduce as nr
import librosa
from audio_separator.separator import Separator
import runpod

def upload_result_to_host(file_path):
    """RunPod 서버는 IP 차단이 없으므로 0x0.st를 통해 결과를 안전하게 공인 URL로 변환"""
    try:
        with open(file_path, 'rb') as f:
            response = requests.post('https://0x0.st', files={'file': f}, timeout=60) 
            if response.status_code == 200: 
                link = response.text.strip() 
                if link.startswith('http'): 
                    return link 
    except Exception as e: 
        print(f"결과 업로드 실패: {e}") 
    return None 
 
def ensure_stereo(data): 
    data = np.asarray(data, dtype=np.float32) 
    if data.ndim == 1: 
        data = np.column_stack([data, data]) 
    elif data.ndim == 2: 
        if data.shape[1] == 1: 
            data = np.column_stack([data[:, 0], data[:, 0]]) 
        elif data.shape[1] > 2: 
            data = data[:, :2] 
    return data 
 
def run_mdx_separation(audio_path, output_dir="separated_output"): 
    os.makedirs(output_dir, exist_ok=True) 
    separator = Separator(output_dir=output_dir, use_cuda=torch.cuda.is_available()) 
    separator.load_model('UVR-MDX-NET-Inst_1.onnx') 
    output_files = separator.separate(audio_path) 
     
    vocal_file, mr_file = None, None 
    for f in output_files: 
        full_path = os.path.join(output_dir, f) 
        if "Vocals" in f: 
            vocal_file = full_path 
        elif "Instrumental" in f or "No Vocals" in f or "no_vocals" in f.lower(): 
            mr_file = full_path 
    return vocal_file, mr_file 
 
def extract_and_process_vocal(vocal_path, clean_output, tuned_output): 
    v_audio, sr = sf.read(vocal_path) 
    v_audio = ensure_stereo(v_audio) 
    mid = (v_audio[:, 0] + v_audio[:, 1]) * 0.5 
    side = (v_audio[:, 0] - v_audio[:, 1]) * 0.5 
    focused_vocal = np.stack([mid + side * 0.3, mid - side * 0.3], axis=1) 
    del v_audio, mid, side 
 
    reduced_vocal = nr.reduce_noise(y=focused_vocal.T, sr=sr, stationary=False, prop_decrease=0.50).T 
    del focused_vocal 
    reduced_vocal = ensure_stereo(reduced_vocal) 
    sf.write(clean_output, reduced_vocal, sr) 
    del reduced_vocal 
    gc.collect() 
 
    y_clean, sr = sf.read(clean_output) 
    y_clean = ensure_stereo(y_clean) 
    y_mono = (y_clean[:, 0] + y_clean[:, 1]) * 0.5 
    y_tuned = y_clean 
    try: 
        y_down = librosa.resample(y_mono, orig_sr=sr, target_sr=16000) 
        if len(y_down) > 1024: 
            f0 = librosa.yin(y_down, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'), sr=16000, hop_length=256) 
            valid_idx = np.isfinite(f0) 
            if np.any(valid_idx): 
                midi_values = librosa.hz_to_midi(f0[valid_idx]) 
                shift = float(np.median(np.round(midi_values) - midi_values) * 0.80) 
                yl = librosa.effects.pitch_shift(y_clean[:, 0], sr=sr, n_steps=shift) 
                yr = librosa.effects.pitch_shift(y_clean[:, 1], sr=sr, n_steps=shift) 
                min_len = min(len(yl), len(yr)) 
                y_tuned = np.stack([yl[:min_len], yr[:min_len]], axis=1) 
                del yl, yr 
            del f0 
        del y_down 
    except Exception: 
        y_tuned = y_clean 
    del y_mono 
 
    sf.write(tuned_output, y_tuned, sr) 
    del y_clean, y_tuned 
    gc.collect() 
    return tuned_output, sr 
 
def apply_vocal_master(tuned_file, output_file, reverb_ratio): 
    reverb_factor = float(reverb_ratio) / 100.0 
    headroom_gain = 1.0 / (1.0 + 0.35 * reverb_factor) 
    
    vocal_filter = ",".join([
        f"highpass=f=95",
        f"equalizer=f=3200:width_type=q:w=1.2:g=3.8",
        f"equalizer=f=11000:width_type=q:w=0.8:g=5.0",
        f"acompressor=threshold=-18dB:ratio=5.5:attack=15:release=140:makeup=2.8",
        f"aecho=0.82:0.72:65|100:{0.22*reverb_factor:.2f}|{0.13*reverb_factor:.2f}",
        f"aecho=0.8:0.81:250:{0.17*reverb_factor:.2f}",
        f"volume={headroom_gain:.2f}"
    ])
    
    cmd = ["ffmpeg", "-y", "-i", tuned_file, "-af", vocal_filter, output_file] 
    subprocess.run(cmd, check=True) 
    return output_file 
 
def apply_mr_master(input_file, output_file): 
    mr_filter = "equalizer=f=100:width_type=q:w=1.0:g=2.2,equalizer=f=8500:width_type=q:w=1.0:g=1.8,volume=1.20" 
    cmd = ["ffmpeg", "-y", "-i", input_file, "-af", mr_filter, output_file] 
    subprocess.run(cmd, check=True) 
    return output_file 
 
def smart_mix(vocal_file, mr_file, output_file): 
    v_data, v_sr = sf.read(vocal_file) 
    i_data, i_sr = sf.read(mr_file) 
    v_data = ensure_stereo(v_data) 
    i_data = ensure_stereo(i_data) 
    if i_sr != v_sr: 
        i_left = librosa.resample(i_data[:, 0], orig_sr=i_sr, target_sr=v_sr) 
        i_right = librosa.resample(i_data[:, 1], orig_sr=i_sr, target_sr=v_sr) 
        min_len = min(len(i_left), len(i_right)) 
        i_data = np.stack([i_left[:min_len], i_right[:min_len]], axis=1) 
        del i_left, i_right 
 
    meter = pyln.Meter(v_sr) 
    try: 
        v_loudness = meter.integrated_loudness(v_data) 
        i_loudness = meter.integrated_loudness(i_data) 
        v_norm = pyln.normalize.loudness(v_data, v_loudness, -9.5) if np.isfinite(v_loudness) else v_data 
        i_norm = pyln.normalize.loudness(i_data, i_loudness, -15.0) if np.isfinite(i_loudness) else i_data 
    except: 
        v_norm = v_data; i_norm = i_data 
    del v_data, i_data 
 
    max_len = max(len(v_norm), len(i_norm)) 
    v_pad = np.pad(v_norm, ((0, max_len - len(v_norm)), (0, 0)), mode="constant") 
    i_pad = np.pad(i_norm, ((0, max_len - len(i_norm)), (0, 0)), mode="constant") 
    del v_norm, i_norm 
 
    mixed = np.tanh((v_pad + i_pad) * 1.15) / 1.15 
    del v_pad, i_pad 
    mixed = np.clip(mixed, -1.0, 1.0) 
    sf.write(output_file, mixed, v_sr) 
    del mixed 
    gc.collect() 
    return output_file 
 
def handler(event): 
    try: 
        inp = event.get("input", {}) 
        media_url = inp.get("media_url") 
        mode = inp.get("mode", "video_full") 
        reverb_ratio = float(inp.get("reverb_ratio", 70.0)) 
        height_pct = float(inp.get("height_pct", 0.0)) 
        title1 = inp.get("title1", "") 
        title2 = inp.get("title2", "") 
        title3 = inp.get("title3", "") 
 
        if not media_url: 
            return {"status": "error", "message": "media_url is missing"} 
 
        # 1. 원본 파일 다운로드 
        input_file = "input_media.mp4" 
        res = requests.get(media_url, stream=True) 
        with open(input_file, "wb") as f: 
            for chunk in res.iter_content(chunk_size=8192): 
                f.write(chunk) 
 
        # 2. 30초 미리보기 모드 처리 (30초~60초 구간 고정 추출) 
        if mode == "preview_30s": 
            subprocess.run([ 
                "ffmpeg", "-y", "-ss", "00:00:30", "-i", input_file, "-t", "30",  
                "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", "preview_raw.wav" 
            ], check=True) 
             
            vocal_file, mr_file = run_mdx_separation("preview_raw.wav", output_dir="separated_preview") 
            extract_and_process_vocal(vocal_file, "preview_clean.wav", "preview_tuned.wav") 
            apply_vocal_master("preview_tuned.wav", "preview_vocal.wav", reverb_ratio) 
            apply_mr_master(mr_file, "preview_mr.wav") 
            smart_mix("preview_vocal.wav", "preview_mr.wav", "preview_mixed.wav") 
             
            subprocess.run(["ffmpeg", "-y", "-i", "preview_mixed.wav", "-b:a", "320k", "preview_final.mp3"], check=True) 
            subprocess.run(["ffmpeg", "-y", "-i", "preview_raw.wav", "-b:a", "320k", "preview_before.mp3"], check=True) 
 
            url_before = upload_result_to_host("preview_before.mp3") 
            url_after = upload_result_to_host("preview_final.mp3") 
 
            return { 
                "status": "success", 
                "audio_before": url_before, 
                "output_file": url_after 
            } 
 
        # 3. 풀 오디오(MP3) 또는 풀 영상(MP4) 처리 
        subprocess.run(["ffmpeg", "-y", "-i", input_file, "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", "raw_audio.wav"], check=True) 
        vocal_file, mr_file = run_mdx_separation("raw_audio.wav", output_dir="separated_raw") 
        extract_and_process_vocal(vocal_file, "live_vocal_clean.wav", "live_vocal_tuned.wav") 
        apply_vocal_master("live_vocal_tuned.wav", "live_vocal.wav", reverb_ratio) 
        apply_mr_master(mr_file, "live_mr.wav") 
        smart_mix("live_vocal.wav", "live_mr.wav", "smart_mixed.wav") 
 
        if mode == "audio_only": 
            subprocess.run(["ffmpeg", "-y", "-i", "smart_mixed.wav", "-b:a", "320k", "final_output.mp3"], check=True) 
            final_url = upload_result_to_host("final_output.mp3") 
            return {"status": "success", "output_file": final_url} 
 
        # 비디오 풀영상 렌더링 
        cmd_dim = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", input_file] 
        probe = subprocess.check_output(cmd_dim).decode("utf-8") 
        data = json.loads(probe) 
        vid_w = int(data["streams"][0]["width"]) 
        vid_h = int(data["streams"][0]["height"]) 
 
        styles = f"Style: Title2,NanumGothicExtraBold,72,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,105,100,0,0,3,4,0,8,25,25,180,1\n" 
        events = [] 
        if title2: events.append(f"Dialogue: 0,0:00:00.00,9:59:59.00,Title2,,0,0,0,,{title2}") 
        events.append("Dialogue: 0,0:00:00.00,9:59:59.00,Title2,,0,0,0,,VocalPickPick") 
         
        ass_content = f"[Script Info]\nScriptType: v4.00+\nPlayResX: {vid_w}\nPlayResY: {vid_h}\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n{styles}\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n" + "\n".join(events) 
         
        with open("sub.ass", "w", encoding="utf-8") as f: 
            f.write(ass_content) 
         
        render_cmd = [ 
            "ffmpeg", "-y", "-i", input_file, "-i", "smart_mixed.wav", "-vf", "ass=sub.ass", 
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", 
            "-c:a", "libmp3lame", "-b:a", "320k", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "final_output.mp4" 
        ] 
        subprocess.run(render_cmd, check=True) 
 
        final_url = upload_result_to_host("final_output.mp4") 
        return {"status": "success", "output_file": final_url} 
 
    except Exception as e: 
        err_detail = traceback.format_exc() 
        print(f"❌ HANDLER CRASH TRACEBACK:\n{err_detail}") 
        return { 
            "status": "error", 
            "message": str(e), 
            "traceback": err_detail 
        } 
 
runpod.serverless.start({"handler": handler})
