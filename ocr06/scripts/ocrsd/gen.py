# OCRSD batch generator. Usage: python gen.py jobs.json
# jobs.json: [{"dir", "document_type", "mapping_id", "writing", "count", "seed", "filter", "text_only"}]
# One job at a time, respecting the site's limits (10 documents per job, 10 jobs per hour);
# skips jobs whose output folder already has job.json, so it can be stopped and resumed.
import io, json, os, re, sys, time, urllib.error, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from api import call as _call

OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "ocrsd"))
NUMERIC_TYPES = {"integer", "time", "document", "digit_sequence", "date"}
NUMERIC_IDS = re.compile(r"matricula|cpf|cnpj|numero|crm|data_|hora|cns|cep|rg\b|nire")
_maps = {}


def call(*a, **k):
    for attempt in range(8):
        try:
            return _call(*a, **k)
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            wait = int(e.headers.get("Retry-After") or 0) or 60 * (attempt + 1)
            print(f"    429: waiting {wait}s", flush=True)
            time.sleep(wait)
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"    network error ({e}); retrying in 60s", flush=True)
            time.sleep(60)
    raise RuntimeError("giving up after retries")


def mapping(dt, mid):
    if (dt, mid) not in _maps:
        _maps[(dt, mid)] = call("GET", f"/api/v1/document-types/{dt}/mappings/{mid}").get("fields", [])
    return _maps[(dt, mid)]


def build(j):
    fields = mapping(j["document_type"], j["mapping_id"])
    ids = [f["field_id"] for f in fields]
    if j.get("text_only"):  # neural writers garble digits
        ids = [f["field_id"] for f in fields
               if f.get("data_type") not in NUMERIC_TYPES and not NUMERIC_IDS.search(f["field_id"])]
    opts = {"name": "claude · " + j["dir"], "document_type": j["document_type"], "mapping_id": j["mapping_id"],
            "fields": ids, "count": j["count"], "seed": j["seed"], "writing": j["writing"],
            "filter_preset": j.get("filter", "medium"), "generation_mode": "traditional"}
    labels = {f["label"]: f["field_id"] for f in fields}
    for _ in range(8):
        try:
            call("POST", "/api/v1/generation/validate", opts)
            return opts
        except urllib.error.HTTPError as e:
            err = json.loads(e.read().decode() or "{}").get("error", {})
            msg = err.get("message", "")
            head = msg.split(":", 1)[0].strip()
            # Short ids/labels ("c", "1", "UF") would match any message by substring (DNV/DO
            # use single-character ids), so those only count when they are the message head.
            bad = [fid for lab, fid in labels.items() if lab and (lab == head or (len(lab) >= 6 and lab in msg))]
            bad += [fid for fid in opts["fields"] if fid == head or (len(fid) >= 4 and fid in msg)]
            if err.get("code") not in ("writing_incompatible", "unsupported_field") or not bad:
                raise RuntimeError(err)
            print(f"    dropping ({err['code']}): {sorted(set(bad))}", flush=True)
            opts["fields"] = [f for f in opts["fields"] if f not in bad]
    raise RuntimeError("could not validate")


def wait_for_slot(per_hour=10):
    while True:
        js = call("GET", "/api/v1/jobs")
        js = js if isinstance(js, list) else js.get("jobs", js.get("items", []))
        recent = sorted(j["created_at"] for j in js if j["created_at"] > time.time() - 3600)
        if len(recent) < per_hour:
            return
        wait = recent[len(recent) - per_hour] + 3600 + 30 - time.time()
        print(f"    hourly limit: waiting {wait / 60:.1f} min", flush=True)
        time.sleep(max(wait, 30))


jobs = json.load(open(sys.argv[1]))
for i, j in enumerate(jobs):
    tag = f"[{i + 1}/{len(jobs)}] {j['dir']}"
    d = os.path.join(OUT, j["dir"])
    if os.path.exists(os.path.join(d, "job.json")):
        print(f"{tag}: already there, skipping", flush=True)
        continue
    try:
        opts = build(j)
    except (RuntimeError, urllib.error.HTTPError) as e:
        print(f"{tag}: cannot generate: {e}", flush=True)
        continue
    wait_for_slot()
    try:
        job = call("POST", "/api/v1/jobs", opts)
    except urllib.error.HTTPError as e:
        print(f"{tag}: rejected ({e.code}): {e.read().decode()[:200]}", flush=True)
        continue
    except RuntimeError as e:  # 429 por muito tempo: espera e segue, sem derrubar a fila
        print(f"{tag}: {e}; pausing 15 min", flush=True)
        time.sleep(900)
        continue
    jid = job.get("id") or job.get("job_id")
    t0 = time.time()
    while True:
        time.sleep(20)
        st = call("GET", f"/api/v1/jobs/{jid}")
        if st["status"] in ("succeeded", "failed", "canceled", "cancelled") or time.time() - t0 > 1800:
            break
    print(f"{time.strftime('%H:%M')} {tag}: {st['status']} {st.get('completed')}/{st.get('total')} "
          f"in {time.time() - t0:.0f}s, {len(opts['fields'])} fields", flush=True)
    if st["status"] == "succeeded":
        z = call("GET", f"/api/v1/jobs/{jid}/artifacts/dataset.zip", raw=True)
        os.makedirs(d, exist_ok=True)
        zipfile.ZipFile(io.BytesIO(z)).extractall(d)
        json.dump({"job_id": jid, "options": opts}, open(os.path.join(d, "job.json"), "w"), ensure_ascii=False, indent=1)
    time.sleep(30)
print("done", flush=True)
