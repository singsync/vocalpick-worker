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

    print("========================================")
    print("=== 🎤 VOCALPICK JOB RECEIVED ===")
    print("========================================")
    print(f"📥 미디어 파일 다운로드 중: {media_url}")
    print(f"🎛️ mode = {mode}")
    print(f"🎛️ reverb_ratio = {reverb_ratio}")
    print(f"📐 height_pct = {height_pct}")
    print(f"📝 title1 = {title1}")
    print(f"📝 title2 = {title2}")
    print(f"📝 title3 = {title3}")

    # =========================================================
    # 1. 파일 다운로드
    # =========================================================
    try:
        res = requests.get(
            media_url,
            stream=True,
            timeout=120,
            allow_redirects=True
        )

        print("========================================")
        print("🌐 DOWNLOAD RESPONSE")
        print("========================================")
        print(f"HTTP status      = {res.status_code}")
        print(f"Final URL        = {res.url}")
        print(f"Content-Type     = {res.headers.get('Content-Type')}")
        print(f"Content-Length   = {res.headers.get('Content-Length')}")
        print(f"History          = {[r.status_code for r in res.history]}")
        print("========================================")

        # HTTP 오류면 즉시 중단
        res.raise_for_status()

        total_bytes = 0

        with open(input_file, "wb") as f:
            for chunk in res.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
                    total_bytes += len(chunk)

        print(f"📦 실제 다운로드 완료: {total_bytes:,} bytes")

        if total_bytes <= 0:
            raise RuntimeError(
                "다운로드된 파일 크기가 0 bytes입니다."
            )

    except Exception as e:
        raise RuntimeError(
            f"파일 다운로드 중 네트워크 에러 발생: {e}"
        )

    # =========================================================
    # 2. INPUT MEDIA 진단
    # =========================================================
    print("========================================")
    print("🔍 INPUT MEDIA 진단 시작")
    print("========================================")

    print(f"📁 input_file = {input_file}")
    print(f"📁 exists = {os.path.exists(input_file)}")

    file_size = 0

    if os.path.exists(input_file):
        file_size = os.path.getsize(input_file)

        print(f"📦 file size = {file_size:,} bytes")

        with open(input_file, "rb") as f:
            header = f.read(64)

        print(f"🔎 first 64 bytes = {header!r}")

        # 사람이 읽기 쉽게 HEX도 표시
        print(f"🔎 first 64 bytes HEX = {header.hex()}")

    if file_size <= 0:
        raise RuntimeError(
            "input_media.mp4 파일이 존재하지 않거나 0 bytes입니다."
        )

    # =========================================================
    # 3. FFPROBE 검사
    # =========================================================
    print("========================================")
    print("🔍 FFPROBE 검사")
    print("========================================")

    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=format_name,duration,size",
            "-of",
            "default=noprint_wrappers=1",
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

    print(
        f"----- FFPROBE RETURN CODE: {probe.returncode} -----"
    )

    # FFprobe 단계에서 이미 파일이 잘못되었는지 확인
    if probe.returncode != 0:
        raise RuntimeError(
            "FFprobe에서 input_media.mp4를 정상적인 미디어 파일로 "
            "인식하지 못했습니다.\n"
            f"file_size={file_size}\n"
            f"content_type={res.headers.get('Content-Type')}\n"
            f"final_url={res.url}\n"
            f"ffprobe={probe.stderr}"
        )

    # =========================================================
    # 4. FFmpeg 오디오 추출
    # =========================================================
    print("========================================")
    print("🔍 FFmpeg 오디오 추출 시작")
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

    print(
        f"----- FFMPEG RETURN CODE: {result.returncode} -----"
    )

    if result.returncode != 0:
        raise RuntimeError(
            "FFmpeg audio extraction failed.\n"
            f"input_file={input_file}\n"
            f"file_size={file_size}\n"
            f"content_type={res.headers.get('Content-Type')}\n"
            f"final_url={res.url}\n"
            f"ffprobe={probe.stderr}\n"
            f"ffmpeg={result.stderr}"
        )

    # =========================================================
    # 5. 오디오 파일 생성 확인
    # =========================================================
    print("========================================")
    print("🔍 AUDIO OUTPUT 검사")
    print("========================================")

    print(f"📁 audio_input = {audio_input}")
    print(f"📁 exists = {os.path.exists(audio_input)}")

    if os.path.exists(audio_input):
        audio_size = os.path.getsize(audio_input)
        print(f"🎵 audio file size = {audio_size:,} bytes")

        if audio_size <= 0:
            raise RuntimeError(
                "FFmpeg가 실행되었지만 input_audio.wav가 0 bytes입니다."
            )

    # =========================================================
    # 6. 이후 기존 보컬 분리 / 렌더링 로직
    # =========================================================
    #
    # 여기에 기존 VocalPick 보컬 분리 및 렌더링 로직을 유지합니다.
    #
    # 예:
    # - audio-separator
    # - Demucs
    # - 보컬 보정
    # - 리버브
    # - EQ
    # - Loudness
    # - 영상 렌더링
    #
    # =========================================================

    print("========================================")
    print("🎉 INPUT / AUDIO 단계 정상 통과")
    print("========================================")

    return {
        "status": "success",
        "output_file": "final_output.mp4"
    }
