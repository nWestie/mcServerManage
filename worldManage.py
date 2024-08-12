#! /home/opc/MCmanage/.venv/bin/python

from time import sleep
import libtmux
import subprocess
import argparse
from enum import Enum
import tarfile
from datetime import date
import os

sesh_name = "lazy"
tmux = libtmux.Server()


class ServerState(Enum):
    Starting = 1
    Stopping = 2
    Running = 3
    Stopped = 4


def start_server():
    """Starts the lazyMC session if not running already"""
    if (session_running()):
        return
    tmux.new_session(session_name=sesh_name,
                     window_command='cd /home/opc/mcMainWorld && ./lazymc')


def kill_server(message: str = "", msg_delay: float = 5):
    """Stops server with optional message and delay. Blocks until server is offline and then kills the session."""
    if (not session_running()):
        print("Server already stopped")
        return

    state = server_state()

    # if starting, wait til done
    while (state == ServerState.Starting):
        print("waiting for start...")
        sleep(1)
        state = server_state()
    # print message that server will be shutdown
    pane = get_terminal()
    if (state == ServerState.Running):
        print("Sending warning")
        if (message):
            send_message(message)
            sleep(msg_delay)
        print("stopping")
        pane.send_keys('stop')

    while (server_state() != ServerState.Stopped):
        sleep(1)
    pane.kill()
    print("server stopped")


def backup_server():
    print("backing up...")
    # Stop server if needed, it will be saved as it shuts down
    while (server_state() == ServerState.Starting):
        sleep(1)
    if (server_state() == ServerState.Running):
        print("shutting down server...")
        send_message("Warning: Server will shutdown for backup in 5 minutes")
        sleep(5*60)
    kill_server("Shutting down for backup.", 5)
    sleep(.2)

    # backup the world
    backup_file = "/home/opc/backups/" + date.today().strftime("backup-%m-%d-%Y.tar.gz")
    worldFolder = "/home/opc/mcMainWorld"
    print(f"Creating backup... ({backup_file})")
    with tarfile.open(backup_file, "w:gz") as tar:
        tar.add(worldFolder, arcname=os.path.basename(worldFolder))
    print(f"Backup saved.")
    sleep(.1)

    # Since it's all zipped, can restart now
    print("Restarting server...")
    start_server()
    
    # Upload to rclone
    print("Uploading backup...")
    subprocess.run(["rclone", "copy", "-P", backup_file, "west_gdrive:minecraft/"])
    print("Fully uploaded")

    # Send message
    for __ in range(30*5):
        if(server_state() == ServerState.Running):
            break
        sleep(2)
    send_message(f"Successfully backed up {os.path.basename(backup_file)}")


def send_message(message: str):
    """sends message visible to all minecraft players, assumes server is running on terminal(check server_running() before using)"""
    terminal = get_terminal()
    terminal.send_keys(f"say {message}")


def server_state() -> ServerState:
    """If the actual minecraft server is open in lazyMC"""

    if (not session_running()):
        return False

    term = get_terminal()
    term_height = int(term.height)
    last_lines: list[str] = term.capture_pane(term_height-100, term_height)

    # iterate over server messages starting with most recent
    for line in reversed(last_lines):
        if ("Server is now sleeping" in line):
            return ServerState.Stopped
        if ("Server is now online" in line):
            return ServerState.Running
        if ("Server has been idle, sleeping" in line):
            return ServerState.Stopping
        if ("Starting server for" in line):
            return ServerState.Starting
    # if none of these are in the last hundred lines(which is unlikely), should be running, probably.
    return ServerState.Running


def session_running():
    """if the lazyMC session is running"""
    return tmux.has_session(sesh_name)


def get_terminal():
    if (not session_running()):
        return None
    test_session: libtmux.Session = tmux.sessions.get(session_name=sesh_name)
    return test_session.active_pane


def main():
    parser = argparse.ArgumentParser(description="Service management tool")

    # Add a single positional argument for the command
    parser.add_argument("command", choices=[
                        "start", "stop", "backup"], help="Command to execute")

    args: argparse.Namespace = parser.parse_args()

    # Execute the corresponding function based on the command
    if args.command == "start":
        start_server()
    elif args.command == "stop":
        kill_server()
    elif args.command == "backup":
        backup_server()


if __name__ == "__main__":
    main()
