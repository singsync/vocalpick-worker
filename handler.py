import os
import subprocess
import requests

def handler(job):
    job_input = job.get("input", {})
    media_url = job_input.get("media_url")
    mode = job_input.get("mode", "video_full")
    reverb_ratio = job_input.get("reverb_ratio", 70)
    height_pct = job_input.get("height_pct", 0.0)
    title1 = job_input.get("title1", "")
    title2 = job_input.get("title2", "")
    title3 = job_input.get("title3", "")

    input_file = "input_media.mp4"
    audio_input = "input_audio.wav"

    print(f"========================================")
    print(f"=== 🎤 VOCALPICK JOB RECEIVED ===")
    print(f"========================================")
    print(f"📥 미디어 파일 다운로드 중: {media_url}")

    # 1. 파일 다운로드
    try:
        res = requests.get(media_url, stream=True, timeout=120)
        with open(input_file, "wb") as f:
            for chunk in res.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    except Exception as e:
        raise RuntimeError(f"파일 다운로드 중 네트워크 에러 발생: {e}")

    # 2. GPT 진단 로직 실행 (파일 정체 파악)
    print("========================================")
    print("🔍 INPUT MEDIA 진단 시작")
    print("========================================")
    print(f"📁 input_file = {input_file}")
    print(f"📁 exists = {os.path.exists(input_file)}")
    
    if os.path.exists(input_file):
        file_size = os.path.getsize(input_file)
        print(f"📦 file size = {file_size:,} bytes")

        with open(input_file, "rb") as f:
            header = f.read(64)
        print(f"🔎 first 64 bytes = {header!r}")

    # 3. FFprobe 검사
    print("========================================")
    print("🔍 FFPROBE 검사")
    print("========================================")
    probe = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=format_name,duration,size",
            "-of", "default=noprint_wrappers=1",
            input_file
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    print("----- FFPROBE STDOUT -----")
    print(probe.stdout)
    print("----- FFPROBE STDERR -----")
    print(probe.stderr)
    print(f"----- FFPROBE RETURN CODE: {probe.returncode} -----")

    # 4. FFmpeg 검사 및 오디오 추출
    print("========================================")
    print("🔍 FFmpeg 검사")
    print("========================================")
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            input_file,
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "44100",
            audio_input
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    print("----- FFMPEG STDOUT -----")
    print(result.stdout)
    print("----- FFMPEG STDERR -----")
    print(result.stderr)
    print(f"----- FFMPEG RETURN CODE: {result.returncode} -----")

    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg audio extraction failed.\n"
            f"input_file={input_file}\n"
            f"file_size={os.path.getsize(input_file) if os.path.exists(input_file) else 0}\n"
            f"ffprobe={probe.stderr}\n"
            f"ffmpeg={result.stderr}"
        )

    # 이후 보컬 분리 및 렌더링 로직 (기존 흐름 유지)
    # ...
    return {"status": "success", "output_file": "final_output.mp4"}
