import runpod

print("================================")
print("VOCALPICK WORKER START TEST")
print("================================")

def handler(job):
    print("JOB RECEIVED")
    return {
        "status": "ok",
        "message": "Worker is alive!"
    }

runpod.serverless.start({
    "handler": handler
})
