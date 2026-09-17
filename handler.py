import runpod
import torch

print("================================")
print("=== TORCH & CUDA CHECK START ===")
print(f"Torch Version: {torch.__version__}")
print(f"CUDA Available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU Device: {torch.cuda.get_device_name(0)}")
print("================================")

def handler(job):
    print("JOB RECEIVED")
    return {
        "status": "success",
        "cuda_available": torch.cuda.is_available()
    }

runpod.serverless.start({
    "handler": handler
})
