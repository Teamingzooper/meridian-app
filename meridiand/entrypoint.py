"""Entry point for the bundled sidecar.

PyInstaller runs its target as a top-level script with no package context, so the
relative imports in `meridiand/__main__.py` fail there. This imports by absolute
path instead, which works both frozen and from a checkout.
"""

import sys

from meridiand.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
