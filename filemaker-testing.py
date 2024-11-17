#! /home/opc/MCmanage/.venv/bin/python

from datetime import datetime
from os import path
import time


backups_folder = "/home/opc/backups"
backup_path = path.join(backups_folder, "test-file.txt")
with open(backup_path, 'w') as f:
    f.write("Testing write\n")
    print("Running filemaker :)")
    f.write(datetime.today().isoformat())
    print(backup_path)




