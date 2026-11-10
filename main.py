import importlib

VERSION = "1.0.0"


def launch_module(module_name):
    try:
        module = importlib.import_module(module_name)
        module.run()
    except ImportError as error:
        print(f"\nModule error: {error}")
    except KeyboardInterrupt:
        print("\nGeoLink stopped.")


def main():
    while True:
        print("\n================================")
        print("       GeoLink v" + VERSION)
        print("================================")
        print("1. Start Sender")
        print("2. Start Receiver")
        print("3. Exit")

        choice = input("\nSelect option: ").strip()

        if choice == "1":
            launch_module("modules.sender")
        elif choice == "2":
            launch_module("modules.receiver")
        elif choice == "3":
            print("Goodbye!")
            break
        else:
            print("Invalid option.")


if __name__ == "__main__":
    main()
