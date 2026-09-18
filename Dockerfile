FROM runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04

# ============================================================
# 🎤 VocalPick GPU Engine
# 시스템 필수 패키지 설치
# ============================================================

RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*


# ============================================================
# 🐍 Python AI / 오디오 처리 패키지 설치
# ============================================================

RUN pip install --no-cache-dir \
    audio-separator \
    pyloudnorm \
    noisereduce \
    librosa \
    soundfile \
    runpod \
    onnxruntime-gpu


# ============================================================
# 🤖 AI 모델 사전 다운로드
# Docker 이미지 생성 시 모델을 미리 받아둠
# RunPod 작업마다 모델을 다시 다운로드하지 않도록 함
# ============================================================

RUN python3 -c "from audio_separator.separator import Separator; Separator().load_model('UVR-MDX-NET-Inst_HQ_3.onnx')"


# ============================================================
# 📂 작업 디렉터리
# ============================================================

WORKDIR /app


# ============================================================
# 📦 VocalPick 소스코드 복사
# handler.py 등이 /app 안으로 들어감
# ============================================================

COPY . .


# ============================================================
# 🚀 RunPod 시작 명령
# 컨테이너가 시작되면 handler.py를 바로 실행
# ============================================================

ENTRYPOINT ["python3", "-u", "handler.py"]
