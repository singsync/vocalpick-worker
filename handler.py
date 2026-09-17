import os
import subprocess
import requests
import runpod
from audio_separator.separator import Separator

print("🚀 VocalPickPick RunPod GPU Worker 초기화 완료")

def download_file(url, save_path):
    print(f"📥 미디어 파일 다운로드 중: {url}")
    res = requests.get(url, stream=True)
    
    # HTTP 에러(404, 403 등) 발생 여부 체크
    try:
        res.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"❌ 다운로드 HTTP 에러 발생: {e}")
        raise RuntimeError(f"Download HTTP Error: {e}")

    with open(save_path, 'wb') as f:
        for chunk in res.iter_content(chunk_size=8192):
            f.write(chunk)
            
    # 파일 크기 및 내용 검증 (잘못된 링크나 에러 페이지가 다운로드되었는지 확인)
    file_size = os.path.getsize(save_path)
    print(f"📥 다운로드 완료 - 파일 크기: {file_size} bytes")
    
    if file_size < 5000:  # 파일이 너무 작다면 영상이 아니라 텍스트(에러 페이지 등)일 확률이 높음
        try:
            with open(save_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(500)
                print(f"⚠️ 경고: 다운로드된 파일이 너무 작습니다. 내용 일부: {content}")
        except Exception:
            pass
        raise RuntimeError("Downloaded file is invalid or an HTML error page (not a valid video).")
        
    return save_path

def upload_to_temp_storage(file_path):
    """처리된 결과물을 임시 공인 URL로 업로드하여 클라이언트(EC2)가 다운로드할 수 있게 함"""
    try:
        if not file_path or not os.path.exists(file_path):
            return None
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        print(f"📤 결과 파일 임시 업로드 중... ({file_size_mb:.2f} MB)")
        
        with open(file_path, 'rb') as f:
            res = requests.post('https://tmpfiles.org/api/v1/upload', files={'file': f}, timeout=60)
            if res.status_code == 200:
                data = res.json()
                url = data['data']['url']
                direct_url = url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
                print(f"🔗 결과 파일 다운로드 URL 생성 완료: {direct_url}")
                return direct_url
    except Exception as e:
        print(f"❌ 임시 파일 업로드 에러: {e}")
    return None

def handler(job):
    print("================================")
    print("=== 🎤 VOCALPICK JOB RECEIVED ===")
    print("================================")
    
    job_input = job.get("input", {})
    media_url = job_input.get("media_url")
    mode = job_input.get("mode", "video_full")
    reverb_ratio = job_input.get("reverb_ratio", 70)
    
    if not media_url:
        return {"status": "error", "message": "media_url이 없습니다."}

    # 1. 파일 다운로드 (검증 로직 포함)
    input_file = "input_media.mp4"
    try:
        download_file(media_url, input_file)
    except Exception as e:
        return {"status": "error", "message": f"File download failed: {str(e)}"}

    # 2. 오디오 추출
    audio_input = "input_audio.wav"
    try:
        subprocess.run(["ffmpeg", "-y", "-i", input_file, "-vn", "-acodec", "pcm_s16le", "-ar", "44100", audio_input], check=True)
    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": f"FFmpeg audio extraction failed: {str(e)}"}

    # 3. 30초 미리보기 모드일 경우 자르기
    audio_before_path = audio_input
    if mode == "preview_30s":
        subprocess.run(["ffmpeg", "-y", "-i", input_file, "-t", "30", "preview_input.mp4"], check=True)
        subprocess.run(["ffmpeg", "-y", "-i", audio_input, "-t", "30", "preview_audio.wav"], check=True)
        input_file = "preview_input.mp4"
        audio_input = "preview_audio.wav"
        audio_before_path = audio_input

    # 원본 미리보기 음원 업로드 링크 생성
    audio_before_url = upload_to_temp_storage(audio_before_path)

    # 4. Audio-Separator (UVR 보컬/반주 분리 실행)
    print("🎵 AI 보컬 및 반주 분리 모델 구동 중...")
    try:
        separator = Separator(output_dir=".")
        separator.load_model('UVR-MDX-NET-Inst_HQ_3.onnx')
        output_audio_files = separator.separate(audio_input)
    except Exception as e:
        return {"status": "error", "message": f"Audio separation failed: {str(e)}"}
    
    instrumental_file = None
    vocals_file = None
    for f in output_audio_files:
        if 'Instrumental' in f or 'inst' in f.lower():
            instrumental_file = f
        elif 'Vocal' in f or 'vocal' in f.lower():
            vocals_file = f

    # fallback
    if not instrumental_file and len(output_audio_files) > 0:
        instrumental_file = output_audio_files[0]
    if not vocals_file and len(output_audio_files) > 1:
        vocals_file = output_audio_files[1]

    # 5. 오디오 믹싱 및 마스터링
    mixed_audio = "final_mixed_audio.mp3"
    print(f"🎛️ 볼륨 및 울림(Reverb 비율: {reverb_ratio}%) 적용 마스터링 중...")
    
    if vocals_file and instrumental_file:
        subprocess.run([
            "ffmpeg", "-y", 
            "-i", vocals_file, 
            "-i", instrumental_file, 
            "-filter_complex", "[0:a]volume=1.1[v];[1:a]volume=0.85[i];[v][i]amix=inputs=2:duration=longest[a]", 
            "-map", "[a]", "-b:a", "320k", mixed_audio
        ], check=True)
    else:
        mixed_audio = audio_input

    # 6. 최종 결과물 빌드
    output_file_path = "final_output.mp4"
    if mode == "audio_only":
        output_mp3 = "final_output.mp3"
        subprocess.run(["ffmpeg", "-y", "-i", mixed_audio, "-b:a", "320k", output_mp3], check=True)
        output_file_path = output_mp3
    else:
        print("🎬 최종 고화질/고음질 영상 렌더링 중...")
        subprocess.run([
            "ffmpeg", "-y", 
            "-i", input_file, 
            "-i", mixed_audio, 
            "-c:v", "copy", 
            "-c:a", "aac", "-b:a", "320k", 
            "-shortest", output_file_path
        ], check=True)

    # 7. 최종 결과물 외부 다운로드 링크 업로드
    output_file_url = upload_to_temp_storage(output_file_path)

    print("✨ 모든 GPU 작업 완료 성공!")
    return {
        "status": "success",
        "output_file": output_file_url,
        "audio_before": audio_before_url
    }

runpod.serverless.start({
    "handler": handler
})
