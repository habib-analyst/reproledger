"""reproledger: the reproducibility attestation network.

SLSA/Sigstore prove *provenance* (who built an artifact). Nothing proves
*independent reproducibility* — that someone else, on their own machine,
re-ran your code and got your numbers. reproledger is that missing layer:

  repro publish   author a repro recipe (code + data + env + command + tolerances)
  repro verify    anyone re-runs the recipe and checks metrics within tolerance
  repro attest    a passing run becomes a signed attestation in the public log
  repro log       query the log: who reproduced what, on what hardware
  repro badge     "reproduced by N independent parties" SVG badges

The public log is a GitHub repo (this one, under ledger/). No blockchain,
no servers, $0. Append = pull request.
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
