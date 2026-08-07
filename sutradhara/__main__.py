"""sutradhara: __main__.py.

Lets `python3 -m sutradhara` run the real CLI directly from the repo root.
"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
