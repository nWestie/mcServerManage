#! /home/opc/MCmanage/.venv/bin/python
import argparse

import libtmux
import time

worlds: dict[str, int] = {}
worlds["main-world"] = 1
worlds["modded"] = 2


def main():
    parser = argparse.ArgumentParser(description="Service management tool")

    # Add a single positional argument for the command
    parser.add_argument("command", choices=[
                        "start", "stop", "backup"], help = "Command to execute")
    # parser.add_argument(
    #     "world", choices=worlds.keys(), help="world to run it on")

    args: argparse.Namespace = parser.parse_args()
    
    tmux = libtmux.Server()
    # print(worlds[args.world])
    # Execute the corresponding function based on the command
    if args.command == "start":
        """Starts the lazyMC session if not running already"""
        sesh = tmux.new_session("lazy")
        sesh.active_pane.send_keys('echo \"hiiiii its me\"')
    elif args.command == "stop":
        print("stopping")
    elif args.command == "backup":
        print("backing up...")
        for i in range(5):
            print(f"Time {i}", flush=True)
            time.sleep(1)
        print("done backup")


main()