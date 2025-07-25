#! /home/opc/MCmanage/.venv/bin/python

from pathlib import Path
import sys
from time import sleep
import time
import libtmux
import subprocess
import argparse
from enum import Enum
import tarfile
from datetime import date
import os

import tomli

# sesh_name = "lazy"


class WorldState(Enum):
    Starting = 1
    Stopping = 2
    Running = 3
    Stopped = 4  # tmux is running, but MC server is stopped
    Offline = 5  # tmux host is not running


tmux = libtmux.Server()


class World:
    def __init__(self, name: str, tmux_sesh: str, server_folder: str, start_cmd: str):
        "Name must be valid as a path"
        self.name: str = name
        self.tmux_id: str = tmux_sesh
        self.folder: str = server_folder
        self.start: str = start_cmd

    def __repr__(self):
        return f"[name: {self.name}, tmux: {self.tmux_id}, dir: {self.folder}]"

    def start_server(self):
        """Starts the lazyMC session if not running already"""
        if (self.session_running()):
            return
        sesh = tmux.new_session(self.tmux_id)
        if sesh.active_pane:
            sesh.active_pane.send_keys(f'cd {self.folder} && {self.start}')
        else:
            raise Exception("Error starting tmux session")

    def kill_server(self, message: str = "", msg_delay: float = 5):
        """Stops server with optional message and delay. Blocks until server is offline and then kills the session."""
        if (not self.session_running()):
            print("Server already stopped", flush=True)
            return

        # if starting, wait until its up
        if (self.status() == WorldState.Starting):
            print("World starting, will shut down once it's fully up...", flush=True)
            self.wait_for_status(WorldState.Running)

        # print message that server will be shutdown
        sesh = self.get_session()

        if (self.status() == WorldState.Running):
            if (message):
                print("Sending shutdown warning", flush=True)
                self.send_message(message)
                sleep(msg_delay)
            # kill server
            print("stopping server", flush=True)
            sesh.send_keys('stop')
        # wait for it to exit fully
        self.wait_for_status(WorldState.Stopped)
        sesh.kill()
        print("server stopped", flush=True)

    def backup_server(self):
        print(f"backing up {self.name}...", flush=True)
        # Stop server if needed, it will be saved as it shuts down
        if (self.status() == WorldState.Starting):
            self.wait_for_status(WorldState.Running)

        # Send message warning of shutdown soon
        if (self.status() == WorldState.Running):
            wait_time: int = 3
            print(
                f"Server running, will shut it down in {wait_time} mins ...", flush=True)
            self.send_message(
                f"Warning: Server will shutdown for backup in {wait_time} minutes")
            sleep(wait_time*60)
        print("shutting down server ...", flush=True)
        self.kill_server("Shutting down for backup.", 5)
        sleep(.2)

        # backup the world
        backup_file = f"/home/opc/backups/{self.name}-{date.today().strftime('%m-%d-%Y.tar.gz')}"
        print(f"Creating backup... ({backup_file})", flush=True)
        with tarfile.open(backup_file, "w:gz") as tar:
            tar.add(self.folder, arcname=os.path.basename(self.folder))
        print(f"Backup saved.", flush=True)
        sleep(.1)

        # Since it's all zipped, can restart now
        print("Restarting server...", flush=True)
        self.start_server()

        return backup_file

    def send_message(self, message: str, wait_for_start: bool = True):
        """sends message visible to all minecraft players - waits for server to boot if wait_for_start is true"""
        if (not self.session_running()):
            print("Server is not running, did not send", flush=True)
            return
        if (wait_for_start and self.status() == WorldState.Starting):
            self.wait_for_status(WorldState.Running)

        self.get_session().send_keys(f"say {message}")

    def status(self) -> WorldState:
        """Detirmines status of the MC sever based on log messages in the server session"""

        if (not self.session_running()):
            return WorldState.Offline

        term = self.get_session()
        # this should be valid for any valid  session
        term_height = int(term.height)  # type: ignore
        last_lines = term.capture_pane(term_height-400, term_height)
        if type(last_lines) is str:
            last_lines = [last_lines]

        # iterate over server messages starting with most recent
        for line in reversed(last_lines):
            if ("Server is now sleeping" in line):
                return WorldState.Stopped
            if ("Proxying public" in line):
                return WorldState.Stopped
            if ("Closing connection, error occurred" in line):
                return WorldState.Stopped
            if ("Server is now online" in line):
                return WorldState.Running
            if ("Server has been idle, sleeping" in line):
                return WorldState.Stopping
            if ("Starting server" in line):
                return WorldState.Starting
        # if none of these are in the last hundred lines(which is unlikely), should be running, probably.
        print("WARN - State unknown", flush=True)
        return WorldState.Running

    def session_running(self):
        """Check that TMUX is running the lazyMC handler"""
        return tmux.has_session(self.tmux_id)

    def get_session(self) -> libtmux.Pane:
        """Returns the running tmux session for this server, or throws if it does not exist"""
        if (not self.session_running()):
            raise Exception(f"tmux session {self.tmux_id} is not running")
        test_session = tmux.sessions.get(
            session_name=self.tmux_id)
        if test_session and test_session.active_pane:
            return test_session.active_pane
        else:
            raise Exception("Unknown Error retrieving tmux session")

    def wait_for_status(self, status: WorldState, timeout=-1):
        """Wait for a specific server status to be achieved"""
        while (self.status() != status):
            sleep(1)

    def last_ran_time(self) -> str:
        """Return a timestamp showing the last time the server was online"""
        log_p = "logs/latest.log"
        full_path = os.path.join(self.folder, log_p)
        return time.ctime(os.path.getmtime(full_path))


def rclone_upload(filepath: str):
    """Save a file to the minecraft backup folder in google drive"""
    print("Uploading backup...")
    subprocess.run(["rclone", "copy", "-P", filepath,
                    "west_gdrive:minecraft/"])
    print("Fully uploaded")


def purge_backups(folder: str, prefix: str, keep_count=1):
    f_list: list[tuple[date, str]] = []

    for f_name in os.listdir(folder):
        if not f_name.startswith(prefix):
            continue
        date_str = f_name.removeprefix(f"{prefix}-")
        date_str = date_str.removesuffix(".tar.gz").removesuffix(".7z")
        d = None
        # Getting date from file name
        s = date_str.split("-")
        d = date(month=int(s[0]), day=int(s[1]), year=int(s[2]))
        f_list.append((d, f_name))

    f_list.sort(key=lambda f: f[0], reverse=True)
    for d, f_name in f_list[keep_count:]:
        print(f"deleting backup: {f_name}", flush=True)
        os.remove(os.path.join(folder, f_name))


def main():

    mainDir = Path(__file__).parent.resolve()
    with open(mainDir.joinpath('worlds.toml'), 'rb') as f:
        config = tomli.load(f)

    home = config.pop("root_dir")
    back_folder = config.pop("backup_dir")

    parser = argparse.ArgumentParser(description="Service management tool")

    # Add a positional argument for the command
    parser.add_argument("command", choices=[
                        "start", "stop", "backup", "purge-backups", "status", "ls"], help="Command to execute")

    # Add a positional argument for the world unless list worlds was requested
    if ("ls" not in sys.argv):
        parser.add_argument(
            "world", choices=config.keys(), help="World to run the command on")

    args: argparse.Namespace = parser.parse_args()

    # List worlds
    if args.command == "ls":
        [print(k) for k in config.keys()]
        exit()

    w_conf = config[args.world]

    world: World = World(
        args.world, w_conf["tmux"], home+w_conf["dir"], w_conf["startup_cmd"])
    # Execute the corresponding function based on the command
    if args.command == "start":
        world.start_server()
        print(f"Started {world.name}")
    elif args.command == "stop":
        world.kill_server()
    elif args.command == "backup":
        file_name = world.backup_server()
        print(file_name)
    elif args.command == "purge-backups":
        file_name = purge_backups("/home/opc/backups", args.world)
    elif args.command == "status":
        print(f"World \"{world.name}\" is {world.status().name}")
        print(f" ↪ Last Online: {world.last_ran_time()}")


if __name__ == "__main__":
    main()
