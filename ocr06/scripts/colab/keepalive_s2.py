# Keeps the Colab kernel busy (an idle kernel gets the VM recycled) until the session
# script writes DONE or FAIL to its status file. Run with `colab exec -s <session> -f`.
import os, time
st = "/content/ai-sec/ocr06/logs/colab_status_s2"
last = ""
while True:
    s = open(st).read() if os.path.exists(st) else ""
    if s != last:
        print("\n" + s[len(last):].strip(), flush=True)
        last = s
    else:
        print(".", end="", flush=True)
    if "DONE" in s or "FAIL" in s:
        break
    time.sleep(10)
