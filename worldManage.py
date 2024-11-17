#! /home/opc/MCmanage/.venv/bin/python

from time import sleep
import libtmux
import subprocess
import argparse
from enum import Enum
import tarfile
from datetime import date
import os

# sesh_name = "lazy"


class WorldState(Enum):
    Starting = 1
    Stopping = 2
    Running = 3
    Stopped = 4
    Offline = 5


tmux = libtmux.Server()


class World:
    def __init__(self, name: str, tmux_sesh: str, server_folder: str):
        "Name must be valid as a path"
        self.name: str = name
        self.tmux_id: str = tmux_sesh
        self.folder: str = server_folder

    def start_server(self):
        """Starts the lazyMC session if not running already"""
        if (self.session_running()):
            return
        sesh = tmux.new_session(self.tmux_id)
        sesh.active_pane.send_keys(f'cd {self.folder} && ./lazymc')

    def kill_server(self, message: str = "", msg_delay: float = 5):
        """Stops server with optional message and delay. Blocks until server is offline and then kills the session."""
        if (not self.session_running()):
            print("Server already stopped")
            return

        # if starting, wait until its up
        if (self.status() == WorldState.Starting):
            print("waiting to fully start world...")
            self.wait_for_status(WorldState.Running)

        # print message that server will be shutdown
        sesh = self.get_session()

        if (self.status() == WorldState.Running):
            if (message):
                print("Sending warning")
                self.send_message(message)
                sleep(msg_delay)
            # kill server
            print("stopping")
            sesh.send_keys('stop')
        # wait for it to exit fully
        self.wait_for_status(WorldState.Stopped)
        sesh.kill()
        print("server stopped")

    def backup_server(self):
        print("backing up...")
        # Stop server if needed, it will be saved as it shuts down
        if (self.status() == WorldState.Starting):
            self.wait_for_status(WorldState.Running)

        # Send message warning of shutdown soon
        if (self.status() == WorldState.Running):
            wait_time: int = 3
            print(f"shutting down server after waiting for {wait_time} mins ...")
            self.send_message(
                f"Warning: Server will shutdown for backup in {wait_time} minutes")
            sleep(wait_time*60)
        print("killing server ...")
        self.kill_server("Shutting down for backup.", 5)
        sleep(.2)

        # backup the world
        backup_file = f"/home/opc/backups/{self.name}-{date.today().strftime('%m-%d-%Y.tar.gz')}"
        print(f"Creating backup... ({backup_file})")
        with tarfile.open(backup_file, "w:gz") as tar:
            tar.add(self.folder, arcname=os.path.basename(self.folder))
        print(f"Backup saved.")
        sleep(.1)

        # Since it's all zipped, can restart now
        print("Restarting server...")
        self.start_server()

        return backup_file

    def send_message(self, message: str, wait_for_start: bool = True):
        """sends message visible to all minecraft players - waits for server to boot if wait_for_start is true"""
        if (not self.session_running()):
            print("Server is not running, cannot send")
            return
        if (wait_for_start and self.status() == WorldState.Starting):
            self.wait_for_status(WorldState.Running)

        self.get_session().send_keys(f"say {message}")

    def status(self) -> WorldState:
        """Detirmines status of the MC sever based on log messages in the server session"""

        if (not self.session_running()):
            return WorldState.Offline

        term = self.get_session()
        term_height = int(term.height)
        last_lines: list[str] = term.capture_pane(term_height-200, term_height)

        # iterate over server messages starting with most recent
        for line in reversed(last_lines):
            if ("Server is now sleeping" in line):
                return WorldState.Stopped
            if ("Proxying public" in line):
                return WorldState.Stopped
            if ("Server is now online" in line):
                return WorldState.Running
            if ("Server has been idle, sleeping" in line):
                return WorldState.Stopping
            if ("Starting server" in line):
                return WorldState.Starting
        # if none of these are in the last hundred lines(which is unlikely), should be running, probably.
        print("WARN - State unknown")
        return WorldState.Running

    def session_running(self):
        """Check that TMUX is running the lazyMC handler"""
        return tmux.has_session(self.tmux_id)

    def get_session(self):
        """Returns the running tmux session for this server, or throws if it does not exist"""
        if (not self.session_running()):
            raise Exception(f"tmux session {self.tmux_id} is not running")
        test_session: libtmux.Session = tmux.sessions.get(
            session_name=self.tmux_id)
        return test_session.active_pane

    def wait_for_status(self, status: WorldState, timeout=-1):
        """Wait for a specific server status to be achieved"""
        while (self.status() != status):
            sleep(1)


def rclone_upload(filepath: str):
    """Save a file to the minecraft backup folder in google drive"""
    print("Uploading backup...")
    subprocess.run(["rclone", "copy", "-P", filepath,
                    "west_gdrive:minecraft/"])
    print("Fully uploaded")


home = "/home/opc/"
worlds: dict[str, World] = {}
worlds["main-world"] = World("OG-Server", "lazy", home+"mcMainWorld")
worlds["modded"] = World("ModdedServer", "modded", home+"RyansModdedServer")
worlds["robo"] = World("RoboFriends", "robo", home+"roboFriends")


def main():
    parser = argparse.ArgumentParser(description="Service management tool")

    # Add a single positional argument for the command
    parser.add_argument("command", choices=[
                        "start", "stop", "backup", "status"], help="Command to execute")
    parser.add_argument(
        "world", choices=worlds.keys(), help="Command to execute")

    args: argparse.Namespace = parser.parse_args()

    world = worlds[args.world]
    # Execute the corresponding function based on the command
    if args.command == "start":
        world.start_server()
    elif args.command == "stop":
        world.kill_server()
    elif args.command == "backup":
        file_name = world.backup_server()
        print(file_name)
    elif args.command == "status":
        print(f"World \"{world.name}\" is {world.status().name}")


if __name__ == "__main__":
    main()
