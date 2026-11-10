import importlib

VERSION = "2.0.0"


def main():
    while True:
        print("\n================================")
        print(f"       GeoLink v{VERSION}")
        print("================================")
        print("1. Start Sender")
        print("2. Start Receiver")
        print("3. Exit")

        choice = input("\nSelect option: ").strip()

        if choice == "1":
            module_name = "modules.sender"
        elif choice == "2":
            module_name = "modules.receiver"
        elif choice == "3":
            print("GeoLink closed.")
            break
        else:
            print("Invalid option.")
            continue

        try:
            module = importlib.import_module(module_name)
            module.run()
        except KeyboardInterrupt:
            print("\nOperation stopped.")
        except Exception as error:
            print(f"\nError: {error}")

        input("\nPress Enter to return to menu...")


if __name__ == "__main__":
    main()
