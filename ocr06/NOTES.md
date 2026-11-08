# Notes: running the model part on Colab (session 2026-10-27)

## Where things stand

- The full pipeline is in `ocr06/`. `data/` is not in git, so the data step has to be run first (step 5 below). The model steps (vLLM baseline, LoRA training, merge + FP8, evaluation) have **never run on a GPU**, since the lab L40S is still not available.
- I tested `train.py` and `merge.py` on CPU with a tiny random model that has Chandra's real config and processor. Pilot, full training (eval, early stopping, best checkpoint) and merge all passed on transformers 5.2, 5.17 and 5.21. Label masking and LoRA targets are correct.
- One crash was found and fixed (commit 44c9b16). `warmup_ratio` no longer exists in transformers 5.x, so it is now passed as `warmup_steps` (a value below 1 is read as a ratio).
- Not tested (needs a GPU): vLLM, FP8 with llm-compressor, real memory use and speed.
- The local PC (GTX 1060 6GB) can't train it. Only 4-bit QLoRA would fit, Unsloth advises against it for Qwen3.5, and torch cu130 doesn't support that GPU.

## Decision: Colab Pro

- Colab Pro costs R$58 for 100 compute units. Use the **L4** runtime (BF16 + FP8, about 1.7 CU/h).
- Estimated full run (baseline + training + merge/FP8 + eval) with the current config: 8–14 L4-hours. In the worst case it is about 40–70 CU, which fits.
- If Colab is a problem:
  - Lightning AI gives about 31 free L4-hours once a card is added and runs the pipeline unchanged.
  - RunPod is also unchanged: L40S $0.79/h, RTX 4090 $0.34/h.
  - Kaggle T4 is a poor fit (no BF16/FP8, 12 h limit).

## Colab steps

1. Runtime > Change runtime type > **L4**.
2. Run `!nvidia-smi` and check "CUDA Version". **13.x** is fine. If it shows **12.x**, the default torch/vLLM wheels (cu130) won't work and torch has to be installed from a cu12x index first.
3. Clone the repo. It is private, so use a GitHub token with read access:
   `!git clone https://<TOKEN>@github.com/gabriel-salmoria/ai-sec.git`
4. Install with `!cd ai-sec/ocr06 && bash scripts/setup.sh`.
   - If creating the venvs fails (missing ensurepip), run `!apt-get install -y python3-venv` (or `python3.12-venv`) and run setup again.
5. Get the data in. IBGE/TSE/RFB block US IPs (Colab), so the `lexicon` step runs in Brazil and its output is in git: `data/lexicon/` plus the IBGE files in `data/raw/` (force-added; `data/` is otherwise ignored). On Colab, skip `lexicon` and run `scripts/run.sh fonts bressay generate mix exp1 exp2`. BRESSAY (Zenodo) and the fonts (Google) download fine from the US.
   - Colab can be driven from the PC with Google's CLI (`pip install google-colab-cli`): `colab new -s l4 --gpu L4`, `colab exec`, `colab ssh` (one SSH connection per runtime at a time), `colab stop`.
   - Old note, before the lexicon was committed:
   - Either run `scripts/run.sh dados` on the laptop (CPU, about 1 h, after `scripts/setup.sh --sem-gpu`), zip `ocr06/data/`, put it on Drive and unzip it in Colab,
   - or run `scripts/run.sh dados` in Colab, which burns CU while the GPU sits idle.
6. Run `!cd ai-sec/ocr06 && bash scripts/run.sh teste-rapido` first. It does a vLLM FP8 baseline on 32 lines plus 100 training steps, takes about 20 min and uses about 0.5 CU. It also prints speed and peak memory.
7. Then run the steps one at a time: `baseline`, `treino`, `quantizar`, `avaliacao` (or all at once with `modelo`).

### Colab caveats

- **Data env needs Python 3.14.** On Colab's Python 3.13, augraphy's `BadPhotoCopy` (numba 0.68.1) crashes in about 21% of calls with a numba `AssertionError`, which kills `generate`. Build `.venv` with `uv python install 3.14` and `PYTHON=$(uv python find 3.14) bash scripts/setup.sh --sem-gpu`; that gave 0 failures in 400 calls, same as the PC.
- `scripts/setup.sh` falls back to `uv venv` when Python has no `ensurepip` (Colab).

- **Keep the tab open.** Colab disconnects closed or idle tabs, the VM disk is wiped, and `train.py` can't resume yet.
- **Save outputs to Drive after each step.** Mount it with `from google.colab import drive; drive.mount('/content/drive')`. What matters:
  - `models/lora_v0/adapter/` and `models/lora_v0/treino.json`
  - `experiments/`
  - `logs/`

  The merged models are large (BF16 is about 10.6 GB, FP8 about 6 GB) and can be rebuilt from the adapter.
- **Keep the model cache off Drive.** `HF_HOME` defaults to `models/hf_cache`, which holds about 17 GB of downloaded models. Don't symlink `models/` to Drive, or that cache fills it.

## Known issues, not fixed yet (optional)

1. **Image size differs between training and vLLM.**
   - `train.py` uses the processor's default `min_pixels` (65,536). Synthetic lines are upscaled to 69 visual tokens in training, but the vLLM config asks for `min_pixels` 3136 (32 tokens).
   - Fix, in `train.py` after loading the processor:
     `processor.image_processor.size = {"shortest_edge": 3136, "longest_edge": 6291456}`
   - Passing `min_pixels` as a call argument had no effect; this assignment does. It also makes training about 20% faster.
2. **`flash-linear-attention` is not in `requirements-gpu.txt`.** The 24 linear-attention (Gated DeltaNet) layers fall back to slow torch code (transformers prints "fast path is not available"). Adding `flash-linear-attention` is enough.
3. **No `resume_from_checkpoint`** in `train.py`. This matters for Colab disconnects.
4. **1 epoch instead of 2** (`model.train.epochs` in `configs/default.yaml`). Together with fixes 1 and 2, this brings training down to about 5–7 L4-hours.

## Version constraints (from PyPI)

- `llmcompressor` 0.14.0.1 requires transformers >=5.15.0,<=5.17.0 and torch <=2.14.0, so `.venv-gpu` ends up with transformers 5.17.
- `vllm` 0.32.0 requires torch==2.13.0 and transformers >=5.16.1,<5.20.

## Model facts (datalab-to/chandra-ocr-2)

- 5.3B params, BF16, 10.6 GB, Qwen3.5-4B base.
- 32 layers: 24 linear-attention and 8 full-attention.
- The embedding is tied with lm_head.
- License: modified OpenRAIL-M (research use OK).
- Tokens per sample:
  - synthetic line: about 125 tokens per training sample
  - BRESSAY line: about 154
  - with Chandra's own long prompt: about 520–550

## For Claude, when continuing on another machine

Answer directly and simply. Don't bring up the schedule or deadlines unprompted. Ask before starting big downloads, installs or test builds.
