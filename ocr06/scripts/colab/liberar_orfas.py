"""Lists the machines assigned on Colab's side and, with --liberar, releases the ones the
local CLI doesn't know (orphans left by a request whose client died). Read-only by default.
    /usr/bin/python scripts/colab/liberar_orfas.py [--liberar]"""
import json, sys
from pathlib import Path
from colab_cli.common import state

known = {s.get("endpoint") for s in json.loads((Path.home() / ".config/colab-cli/sessions.json").read_text() or "{}").values()
         if isinstance(s, dict)}
for a in state.client.list_assignments():
    ep = getattr(a, "endpoint", None)
    orphan = ep not in known
    print(f"{ep} accel={getattr(a, 'accelerator', '?')} {'ÓRFÃ' if orphan else 'conhecida'}")
    if orphan and "--liberar" in sys.argv:
        state.client.unassign(ep)
        print(f"  liberada: {ep}")
