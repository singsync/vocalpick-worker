import os
import requests
import subprocess
import runpod

def handler(job):
    job_input = job.get("input", {})
    media_url = job_input.get("media_url")
    mode = job_input.get("mode", "video_full")
    reverb_ratio = job_input.get("reverb_ratio", 70)
    height_pct = job_input.get("height_pct", 0.0)
    title1 = job_input.get("title1", "")
    title2 = job_input.get("title2", "")
    title3 = job_input.get("title3", "")

    if not media_url:
        return {"status": "error", "message": "No media_url provided"}

    input_file = "input_media.mp4"
    audio_input = "input_audio.wav"

    print(f"📥 [RunPod] EC2 다이렉트 파일 다운로드 시작: {media_url}")
    try:
        response = requests.get(media_url, stream=True, timeout=180)
        response.raise_for_status()
        with open(input_file, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
        
        file_size = os.path.getsize(input_file)
        print(f"✅ [RunPod] 다운로드 완료! 파일 크기: {file_size / (1024*1024):.2f} MB")
        
        if file_size < 1000:
            return {"status": "error", "message": "Downloaded file is too small or invalid."}
            
    except Exception as e:
        return {"status": "error", "message": f"File download failed: {str(e)}"}

    # 💡 FFmpeg 오디오 추출 (에러 로그 상세 출력 포함)
    print("⚡ [RunPod] FFmpeg 오디오 추출 시작...")
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", input_file, "-vn", "-acodec", "pcm_s16le", "-ar", "44100", audio_input],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        print("✨ [RunPod] FFmpeg 오디오 추출 성공!")
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg STDERR:\n{e.stderr}")
        return {
            "status": "error", 
            "message": f"FFmpeg failed with exit code {e.returncode}",
            "stderr": e.stderr
        }

    # =========================================================================
    # 🎵 이 아래에 기존에 사용하시던 보컬 분리(audio-separator) 및 렌더링 로직을 연결하시면 됩니다.
    # =========================================================================

    if mode == "preview_30s":
        # 30초 미리보기 모드일 경우 결과 반환 예시
        return {
            "status": "success",
            "audio_before": audio_input,
            "output_file": audio_input  # 테스트용 음원 경로
        }

    # 기본 풀영상/음원 완성 모드 결과 반환 예시
    return {
        "status": "success",
        "output_file": input_file # 최종 처리된 결과 파일 경로로 교체 필요
    }

runpod.serverless.start({"handler": handler})
