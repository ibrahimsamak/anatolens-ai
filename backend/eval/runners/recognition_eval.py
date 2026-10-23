import json, time
from app.recognition.pipeline import recognize

def run_recognition_eval(cfg, db) -> dict:
    rows = [json.loads(l) for l in open(cfg.datasets["recognition"])]
    correct = false_rec = 0; latencies = []
    for r in rows:
        with open(r["image_path"], "rb") as f:
            image = f.read()
        t = time.perf_counter()
        res = recognize(image, db)
        latencies.append((time.perf_counter() - t) * 1000)
        if res.lesson_id == r["expected_lesson"]: correct += 1
        elif res.lesson_id is not None: false_rec += 1
    n = len(rows)
    if not n:
        return {"top1": 0.0, "false_recognition": 0.0, "avg_latency_ms": 0.0, "n": 0}
    return {"top1": correct / n, "false_recognition": false_rec / n,
            "avg_latency_ms": sum(latencies) / n, "n": n}
