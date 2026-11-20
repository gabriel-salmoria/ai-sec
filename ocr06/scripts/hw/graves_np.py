"""NumPy port of the sjvasquez Graves handwriting-synthesis model (inference only).

Loads the original TF checkpoint ``model-17900`` (converted once to .npz) and
reproduces the sampling graph of github.com/sjvasquez/handwriting-synthesis
(same as the TF2 port github.com/otuva/handwriting-synthesis):

* 3 stacked LSTMs (400 units, TF1 ``LSTMCell`` semantics, forget bias 1.0),
* Gaussian attention window (10 components) over the one-hot character string,
* 20-component bivariate GMM + Bernoulli pen-up head,
* ``bias`` sharpening (pi * (1 + b), log sigma - b), optional priming with
  stroke sequences of a known text.

Differences from the TF graph, all deliberate:
* randomness comes from one ``numpy.random.Generator`` per sample, so a given
  (text, style, bias, seed) is reproducible regardless of batch composition;
* the step limit is per sample (40 * len(text)) instead of the batch maximum.

The deterministic forward pass was checked against the TF graph (teacher-forced
NLL agrees to float32 precision, see scripts/hw/check_graves_port.py).
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np

ALPHABET = [
    '\x00', ' ', '!', '"', '#', "'", '(', ')', ',', '-', '.',
    '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', ':', ';',
    '?', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K',
    'L', 'M', 'N', 'O', 'P', 'R', 'S', 'T', 'U', 'V', 'W', 'Y',
    'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l',
    'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x',
    'y', 'z',
]
CHAR_TO_ID = {c: i for i, c in enumerate(ALPHABET)}
CHARSET = set(ALPHABET[1:])  # everything except the NUL end token
MAX_CHARS = 75               # limit enforced by the original Hand.write
LSTM = 400
K_ATT = 10
M_OUT = 20
V = len(ALPHABET)

_VARS = {
    "K1": "rnn/LSTMAttentionCell/lstm_cell/kernel",
    "b1": "rnn/LSTMAttentionCell/lstm_cell/bias",
    "K2": "rnn/LSTMAttentionCell/lstm_cell_1/kernel",
    "b2": "rnn/LSTMAttentionCell/lstm_cell_1/bias",
    "K3": "rnn/LSTMAttentionCell/lstm_cell_2/kernel",
    "b3": "rnn/LSTMAttentionCell/lstm_cell_2/bias",
    "Wa": "rnn/LSTMAttentionCell/attention/weights",
    "ba": "rnn/LSTMAttentionCell/attention/biases",
    "Wg": "rnn/gmm/weights",
    "bg": "rnn/gmm/biases",
}


def convert_checkpoint(ckpt_prefix: str, npz_path: str) -> None:
    """One-off conversion TF checkpoint -> npz (needs tensorflow installed)."""
    import tensorflow as tf  # noqa: lazy, only for conversion
    r = tf.train.load_checkpoint(ckpt_prefix)
    arrs = {k: r.get_tensor(v).astype(np.float32) for k, v in _VARS.items()}
    os.makedirs(os.path.dirname(npz_path), exist_ok=True)
    np.savez(npz_path, **arrs)


def load_weights(npz_path: str, ckpt_prefix: str | None = None) -> dict:
    if not os.path.exists(npz_path):
        if ckpt_prefix is None:
            raise FileNotFoundError(npz_path)
        convert_checkpoint(ckpt_prefix, npz_path)
    d = np.load(npz_path)
    return {k: d[k] for k in d.files}


def encode(text: str) -> np.ndarray:
    bad = sorted({c for c in text if c not in CHARSET})
    if bad:
        raise ValueError(f"characters outside the Graves/IAM-OnDB alphabet: {bad!r}")
    return np.array([CHAR_TO_ID[c] for c in text] + [0], dtype=np.int64)


def _sigmoid(x):
    return 0.5 * (np.tanh(0.5 * x) + 1.0)


def _softplus(x):
    return np.logaddexp(0.0, x)


@dataclass
class State:
    h1: np.ndarray
    c1: np.ndarray
    h2: np.ndarray
    c2: np.ndarray
    h3: np.ndarray
    c3: np.ndarray
    kappa: np.ndarray
    w: np.ndarray
    phi: np.ndarray

    @staticmethod
    def zeros(b: int, u: int) -> "State":
        z = lambda n: np.zeros((b, n), np.float32)  # noqa: E731
        return State(z(LSTM), z(LSTM), z(LSTM), z(LSTM), z(LSTM), z(LSTM),
                     z(K_ATT), z(V), z(u))

    def where(self, keep: np.ndarray, other: "State") -> "State":
        """Rows with keep=True take values from self, others from `other`."""
        m = keep[:, None]
        return State(*[np.where(m, getattr(self, f), getattr(other, f))
                       for f in self.__dataclass_fields__])


class GravesNP:
    def __init__(self, weights: dict):
        self.W = weights

    # ---- cell -------------------------------------------------------------
    def _lstm(self, x, h, c, K, b):
        z = np.concatenate([x, h], axis=1) @ K + b
        i, j, f, o = np.split(z, 4, axis=1)
        c = _sigmoid(f + 1.0) * c + _sigmoid(i) * np.tanh(j)
        h = _sigmoid(o) * np.tanh(c)
        return h, c

    def step(self, x, s: State, onehot, mask, u) -> State:
        W = self.W
        h1, c1 = self._lstm(np.concatenate([s.w, x], 1), s.h1, s.c1, W["K1"], W["b1"])
        att = _softplus(np.concatenate([s.w, x, h1], 1) @ W["Wa"] + W["ba"])
        alpha, beta, dk = np.split(att, 3, axis=1)
        kappa = s.kappa + dk / 25.0
        beta = np.maximum(beta, 0.01)
        phi = np.sum(alpha[:, :, None] * np.exp(-np.square(kappa[:, :, None] - u[None, None, :])
                                                / beta[:, :, None]), axis=1)
        w = np.einsum("bu,buv->bv", phi * mask, onehot)
        h2, c2 = self._lstm(np.concatenate([x, h1, w], 1), s.h2, s.c2, W["K2"], W["b2"])
        h3, c3 = self._lstm(np.concatenate([x, h2, w], 1), s.h3, s.c3, W["K3"], W["b3"])
        return State(h1, c1, h2, c2, h3, c3, kappa, w.astype(np.float32), phi.astype(np.float32))

    # ---- output head ------------------------------------------------------
    def gmm_params(self, h3, bias):
        z = h3 @ self.W["Wg"] + self.W["bg"]
        pis, sig, rho, mu, e = np.split(z, [M_OUT, 3 * M_OUT, 4 * M_OUT, 6 * M_OUT], axis=1)
        b = bias[:, None]
        pis = pis * (1.0 + b)
        pis = np.exp(pis - pis.max(1, keepdims=True))
        pis /= pis.sum(1, keepdims=True)
        pis = np.where(pis < 0.01, 0.0, pis)
        sig = np.maximum(np.exp(sig - b), 1e-4)
        rho = np.clip(np.tanh(rho), 1e-8 - 1.0, 1.0 - 1e-8)
        e = np.clip(_sigmoid(e[:, 0]), 1e-8, 1.0 - 1e-8)
        e = np.where(e < 0.01, 0.0, e)
        return pis, mu, sig, rho, e

    @staticmethod
    def draw(params, r):
        """r: (B, 4) uniforms/normals = [u_cat, z1, z2, u_eos]."""
        pis, mu, sig, rho, e = params
        B = pis.shape[0]
        cdf = np.cumsum(pis, axis=1)
        cdf /= cdf[:, -1:]
        k = np.minimum((cdf < r[:, :1]).sum(1), M_OUT - 1)
        ix = np.arange(B)
        m1, m2 = mu[ix, k], mu[ix, M_OUT + k]
        s1, s2 = sig[ix, k], sig[ix, M_OUT + k]
        p = rho[ix, k]
        x1 = m1 + s1 * r[:, 1]
        x2 = m2 + s2 * (p * r[:, 1] + np.sqrt(1.0 - p * p) * r[:, 2])
        eos = (r[:, 3] < e).astype(np.float32)
        return np.stack([x1, x2, eos], 1).astype(np.float32)

    # ---- sampling ---------------------------------------------------------
    def sample(self, texts, biases, seeds, primes=None, steps_per_char=40):
        """texts: list[str]; biases: list[float]; seeds: list[int|None];
        primes: list[None | (offsets (N,3) normalised, prime_text)].
        Returns list of (offsets (T,3), char_index (T,)) per sample."""
        B = len(texts)
        primes = primes or [None] * B
        full = []
        for t, p in zip(texts, primes):
            full.append((p[1] + " " + t) if p is not None else t)
        enc = [encode(s) for s in full]
        U = max(120, max(len(e) for e in enc) + 10)
        onehot = np.zeros((B, U, V), np.float32)
        mask = np.zeros((B, U), np.float32)
        clen = np.zeros(B, np.int64)
        for i, e in enumerate(enc):
            onehot[i, np.arange(len(e)), e] = 1.0
            mask[i, :len(e)] = 1.0
            clen[i] = len(e)
        u = np.arange(U, dtype=np.float32)
        bias = np.asarray(biases, np.float32)
        limits = np.array([steps_per_char * len(t) for t in texts])
        Tmax = int(limits.max())
        # per-sample random streams, drawn up front: [u_cat, z1, z2, u_eos, u_term]
        R = np.zeros((Tmax + 1, B, 5), np.float32)
        for i, sd in enumerate(seeds):
            g = np.random.default_rng(sd)
            n = limits[i] + 1
            R[:n, i, 0] = g.random(n)
            R[:n, i, 1:3] = g.standard_normal((n, 2))
            R[:n, i, 3:5] = g.random((n, 2))

        s = State.zeros(B, U)
        # priming (teacher forcing over each sample's own stroke sequence)
        plen = np.array([0 if p is None else len(p[0]) for p in primes])
        if plen.max() > 0:
            for t in range(int(plen.max())):
                x = np.zeros((B, 3), np.float32)
                for i, p in enumerate(primes):
                    if p is not None and t < len(p[0]):
                        x[i] = p[0][t]
                ns = self.step(x, s, onehot, mask, u)
                s = s.where(t >= plen, ns)  # frozen once its prime ended
        x = np.tile(np.array([[0.0, 0.0, 1.0]], np.float32), (B, 1))
        primed = plen > 0
        if primed.any():
            x0 = self.draw(self.gmm_params(s.h3, bias), R[0, :, :4])
            x[primed] = x0[primed]

        out = np.zeros((Tmax, B, 3), np.float32)
        cidx = np.full((Tmax, B), -1, np.int64)
        finished = self._terminated(s, clen, bias, R[0, :, 4])
        for t in range(Tmax):
            if finished.all():
                out, cidx = out[:t], cidx[:t]
                break
            ns = self.step(x, s, onehot, mask, u)
            s = s.where(finished, ns)
            params = self.gmm_params(s.h3, bias)
            y = self.draw(params, R[t + 1, :, :4])
            y[finished] = 0.0
            out[t] = y
            cidx[t] = np.where(finished, -1, np.argmax(s.phi, axis=1))
            term = self._terminated(s, clen, bias, R[t + 1, :, 4], params)
            finished = finished | term | (t + 1 >= limits)
            x = y
        res = []
        for i in range(B):
            keep = cidx[:, i] >= 0
            off = out[keep, i]
            ci = cidx[keep, i]
            if primes[i] is not None:  # char index relative to the target text
                ci = ci - (len(primes[i][1]) + 1)
            res.append((off, ci))
        return res

    def _terminated(self, s, clen, bias, u_term, params=None):
        ci = np.argmax(s.phi, axis=1)
        if params is None:
            params = self.gmm_params(s.h3, bias)
        eos = u_term < params[4]
        return ((ci >= clen - 1) & eos) | (ci >= clen)

    # ---- teacher-forced loss (for checking against the TF graph) ----------
    def nll(self, x, y, text):
        e = encode(text)
        U = len(e)
        onehot = np.zeros((1, U, V), np.float32)
        onehot[0, np.arange(U), e] = 1
        mask = np.ones((1, U), np.float32)
        u = np.arange(U, dtype=np.float32)
        s = State.zeros(1, U)
        tot = 0.0
        for t in range(len(x)):
            s = self.step(x[t:t + 1].astype(np.float32), s, onehot, mask, u)
            z = s.h3 @ self.W["Wg"] + self.W["bg"]
            pis, sig, rho, mu, ee = np.split(z[0], [M_OUT, 3 * M_OUT, 4 * M_OUT, 6 * M_OUT])
            pis = np.exp(pis - pis.max()); pis /= pis.sum()
            sig = np.maximum(np.exp(sig), 1e-4)
            rho = np.clip(np.tanh(rho), 1e-8 - 1, 1 - 1e-8)
            ee = np.clip(_sigmoid(ee[0]), 1e-8, 1 - 1e-8)
            s1, s2 = sig[:M_OUT], sig[M_OUT:]
            m1, m2 = mu[:M_OUT], mu[M_OUT:]
            zz = ((y[t, 0] - m1) / s1) ** 2 + ((y[t, 1] - m2) / s2) ** 2 \
                - 2 * rho * (y[t, 0] - m1) * (y[t, 1] - m2) / (s1 * s2)
            g = np.exp(-zz / (2 * (1 - rho ** 2))) / (2 * np.pi * s1 * s2 * np.sqrt(1 - rho ** 2))
            gl = max(float(np.sum(pis * g)), 1e-8)
            bl = ee if y[t, 2] == 1 else 1 - ee
            tot += -(np.log(gl) + np.log(bl))
        return tot / len(x)
