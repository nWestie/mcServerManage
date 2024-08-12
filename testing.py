#! ./.venv/bin/python

from datetime import date
import os
import tarfile
import libtmux
import subprocess
import argparse
from time import sleep
from enum import Enum

import worldManage


def main():
    # worldManage.kill_server("stopping server for backup")

    # # backup the world
    # backup_file = os.path.abspath(
    #     "./backups/" + date.today().strftime("backup-%d-%m-%Y.tar.gz"))
    # worldFolder = "/home/opc/mcMainBackup"
    # print(f"Creating backup...")
    # with tarfile.open(backup_file, "w:gz") as tar:
    #     tar.add(worldFolder, arcname=os.path.basename(worldFolder))
    # print(f"Backup saved: {backup_file}")
    subprocess.run(["rclone", "copy", "-P", "backups/backup-11-08-2024.7z", "west_gdrive:minecraft/"])

if __name__ == "__main__":
    main()
