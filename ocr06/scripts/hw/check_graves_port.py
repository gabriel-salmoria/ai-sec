"""Check graves_np against the TF2 port (otuva) on the same checkpoint.

Teacher-forced NLL of the 13 priming sequences must agree between the NumPy
port and the TF graph. Run with .venv-hw-graves (needs tensorflow 2.12).
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OCR06 = os.path.abspath(os.path.join(HERE, "..", ".."))
OTUVA = os.path.join(OCR06, "third_party", "otuva")
sys.path.insert(0, HERE)
import graves_np  # noqa: E402

NPZ = os.path.join(OCR06, "third_party", "graves_np", "model-17900.npz")
W = graves_np.load_weights(NPZ, os.path.join(OTUVA, "model", "checkpoint", "model-17900"))
port = graves_np.GravesNP(W)

sys.path.insert(0, OTUVA)
cwd = os.getcwd()
os.chdir(OTUVA)
from handwriting_synthesis import Hand  # noqa: E402
hand = Hand()
os.chdir(cwd)
nn = hand.nn

for s in range(13):
    x_p = np.load(f"{OTUVA}/model/style/style-{s}-strokes.npy").astype(np.float32)
    text = np.load(f"{OTUVA}/model/style/style-{s}-chars.npy").tobytes().decode()
    x, y = x_p[:-1], x_p[1:]
    c = graves_np.encode(text)
    tf_loss = nn.session.run(nn.loss, feed_dict={
        nn.x: x[None], nn.y: y[None], nn.x_len: [len(x)],
        nn.c: c[None], nn.c_len: [len(c)], nn.num_samples: 1,
    })
    np_loss = port.nll(x, y, text)
    print(f"style {s:2d}  tf {tf_loss:.6f}  numpy {np_loss:.6f}  diff {abs(tf_loss - np_loss):.2e}")
