#! /home/opc/MCmanage/.venv/bin/python

import os
import tomli
import libtmux
import time
from pathlib import Path


def main():
    mainDir = Path(__file__).parent.resolve()
    with open(mainDir.joinpath('worlds.toml'), 'rb') as f:
        config = tomli.load(f)
    
    home = config.pop('root_dir')
    log_p = "logs/latest.log"
    for name, dat in config.items():
        full_path = os.path.join(home, dat["dir"], log_p)
        print(time.ctime(os.path.getmtime(full_path)))

main()