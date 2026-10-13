"""Run the private workstation-profile CLI independently from cleanup commands."""
from . import main

if __name__ == "__main__":
    raise SystemExit(main())
