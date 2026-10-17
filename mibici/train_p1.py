"""Acceso corto: ``python -m mibici.train_p1`` equivale a ``python -m mibici.train --question P1``."""

import sys

from mibici.train import main

if __name__ == "__main__":
    main(["--question", "P1", *sys.argv[1:]])
