"""Utilidades compartilhadas: configuração, downloads, hashing estável e I/O."""
from __future__ import annotations

import csv
import hashlib
import json
import time
from pathlib import Path

import requests
import yaml
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[2]


def load_config(path: str | Path = "configs/default.yaml") -> dict:
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve(cfg: dict, key: str) -> Path:
    p = Path(cfg["paths"][key])
    p = p if p.is_absolute() else ROOT / p
    p.mkdir(parents=True, exist_ok=True)
    return p


def stable_unit(*parts) -> float:
    """Número em [0, 1) determinístico para uma tupla (independe de PYTHONHASHSEED)."""
    h = hashlib.sha1(":".join(map(str, parts)).encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") / 2**64


def stable_int(*parts) -> int:
    h = hashlib.sha1(":".join(map(str, parts)).encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big")


def assign_split(splits: dict, *parts) -> str:
    u = stable_unit(*parts)
    acc = 0.0
    for name, frac in splits.items():
        acc += frac
        if u < acc:
            return name
    return list(splits)[-1]


def download(url: str, dest: Path, auth=None, retries: int = 5) -> Path:
    """Baixa `url` para `dest` (pula se já existir). Grava em .part e renomeia no fim;
    se a conexão cair, a próxima tentativa continua de onde parou (HTTP Range)."""
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, retries + 1):
        try:
            done = tmp.stat().st_size if tmp.exists() else 0
            headers = {"Range": f"bytes={done}-"} if done else {}
            with requests.get(url, stream=True, auth=auth, timeout=60, headers=headers) as r:
                r.raise_for_status()
                resumed = r.status_code == 206
                total = int(r.headers.get("content-length", 0)) or None
                with open(tmp, "ab" if resumed else "wb") as f, \
                        tqdm(total=(total or 0) + (done if resumed else 0) or None,
                             initial=done if resumed else 0, unit="B", unit_scale=True,
                             desc=dest.name, leave=False) as bar:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
                        bar.update(len(chunk))
            tmp.rename(dest)
            return dest
        except requests.RequestException as e:
            if attempt == retries:
                raise
            print(f"  falha ao baixar {url} ({e}); tentativa {attempt + 1}/{retries}")
            time.sleep(2 * attempt)
    return dest


def get_json(url: str, retries: int = 3):
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, timeout=120)
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if attempt == retries:
                raise
            time.sleep(2 * attempt)


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def read_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)
