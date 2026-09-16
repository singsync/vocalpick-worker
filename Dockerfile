FROM runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04

# 시스템 필수 패키지 미리 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 파이썬 AI 패키지 미리 설치 (부팅 시간 단축)
RUN pip install --no-cache-dir \
    audio-separator \
    pyloudnorm \
    noisereduce \
    librosa \
    soundfile \
    runpod \
    onnxruntime-gpu

WORKDIR /app

# 핸들러 파일 및 소스코드를 컨테이너 안으로 복사
COPY . .

CMD ["python3", "-u", "handler.py"]
