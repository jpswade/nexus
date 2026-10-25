"""One launcher for both Nexus views; F5 switches between them."""
import argparse
import os
from pathlib import Path
import runpy
import shutil
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("view", nargs="?", choices=("nexus", "home"), default="nexus")
    args, remainder = parser.parse_known_args()
    root = Path(__file__).resolve().parent
    os.chdir(root)
    if args.view == "home":
        config = Path(os.environ.get("NEXUS_HOME_CONFIG", root / "home.json"))
        if not config.exists() and "--config" not in remainder:
            shutil.copyfile(root / "home.example.json", config)
        sys.argv = ["pi_dashboard", "--config", str(config), *remainder]
        runpy.run_module("pi_dashboard", run_name="__main__")
    else:
        sys.argv = ["dashboard.py", *remainder]
        runpy.run_path(str(root / "dashboard.py"), run_name="__main__")


if __name__ == "__main__":
    main()
