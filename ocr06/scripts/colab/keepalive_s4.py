# Keeps the Colab kernel busy until sessao4 writes DONE or FAIL; prints new status lines at
# once and the latest GPU-use line (logs/gpu_s4.csv) about every 60 s.
import os, time
st = "/content/ai-sec/ocr06/logs/colab_status_s4"
gpu = "/content/ai-sec/ocr06/logs/gpu_s4.csv"
last, t = "", 0
while True:
    s = open(st).read() if os.path.exists(st) else ""
    if s != last:
        print("\n" + s[len(last):].strip(), flush=True)
        last = s
    if t % 6 == 0 and os.path.exists(gpu):
        lines = open(gpu).read().strip().splitlines()
        if lines:
            print("GPU " + lines[-1], flush=True)
    if "DONE" in s or "FAIL" in s:
        break
    t += 1
    time.sleep(10)
