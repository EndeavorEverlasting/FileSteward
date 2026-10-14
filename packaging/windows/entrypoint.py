"""Native launcher entry; all product behavior remains in the package."""

import logging
import os
import sys


def main(argv=None) -> int:
    """Preserve a visible startup failure even in the windowed frozen entry."""
    try:
        from filesteward.launch import main as launch_main

        return launch_main(argv)
    except Exception as error:
        logging.exception("FileSteward startup failed")
        if os.name == "nt" and not sys.stderr:
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, str(error), "FileSteward could not start", 0x10)
        else:
            print(str(error), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
