import os
import sys
import time
import importlib

VERSION = "1.0.0"

def clear():
    os.system("clear")

def banner():
    print("""
  ____ _____ ___  _     ___ _   _ _  __
 / ___| ____/ _ \\| |   |_ _| \\ | | |/ /
| |  _|  _|| | | | |    | ||  \\| | ' /
| |_| | |__| |_| | |___ | || |\\  | . \\
 \\____|_____\\___/|_____|___|_| \\_|_|\\_\\

       GEO-LINK TERMUX EDITION
             Version 1.0
    """)

def launch_module(module_name, role):
    try:
        module = importlib.import_module(module_name)
        module.run()
    except ModuleNotFoundError:
        print(f"\n[!] {role} module abhi available nahi hai.")
        print("[i] Development in progress.")
        input("\nPress Enter to continue...")
    except KeyboardInterrupt:
        print("\n[!] Session stopped.")
        time.sleep(1)
    except Exception as error:
        print(f"\n[ERROR] {error}")
        input("\nPress Enter to continue...")

def main():
    while True:
        clear()
        banner()

        print("[1] Sender")
        print("[2] Receiver")
        print("[3] Configuration")
        print("[4] Exit")

        choice = input("\nGeoLink > ").strip()

        if choice == "1":
            launch_module("modules.sender", "Sender")

        elif choice == "2":
            launch_module("modules.receiver", "Receiver")

        elif choice == "3":
            print("\nConfiguration module coming soon.")
            input("\nPress Enter to continue...")

        elif choice == "4":
            print("\nGeoLink closed.")
            sys.exit(0)

        else:
            print("\n[!] Invalid option.")
            time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nGeoLink terminated.")
