"""
EmbITE - Embedded Integrated Test Environment

Main framework entry point.
"""

import getpass
from board_action.shell_detector import ShellDetector
from config.config_manager import ConfigManager
from board_action.ssh_connection import SSHConnection


def main():
    print("=" * 50)
    print("           EmbITE MVP")
    print("=" * 50)

    print("Loading configuration...")

    config_manager = ConfigManager("config/dut_config.yaml")
    config_manager.load()

    dut_config = config_manager.get_dut_config()
    connection_config = dut_config.get("connection", {})

    print(f"DUT: {dut_config.get('name')}")
    print(f"Connection type: {connection_config.get('type')}")

    if connection_config.get("type") != "ssh":
        raise ValueError(
            f"Unsupported connection type: "
            f"{connection_config.get('type')}"
        )

    password = getpass.getpass("Enter password: ")

    connection = SSHConnection(
        host=connection_config.get("host"),
        port=connection_config.get("port", 22),
        username=connection_config.get("username"),
        password=password,
    )

    print("Connecting to DUT...")

    connection.connect()

    print("SSH connection established.")

    shell_detector = ShellDetector(connection)
    shell_info = shell_detector.detect()
    print(f"DUT OS: {shell_info['os']}")
    print(f"DUT Shell: {shell_info['shell']}")
    print(f"DUT Shell Path: {shell_info['shell_path']}")

    output, error = connection.execute("uname -a")

    print("\nDUT Response:")
    print(output)

    if error:
        print("\nDUT Error:")
        print(error)

    connection.disconnect()

    print("\nSSH connection closed.")
    print("EmbITE MVP completed.")


if __name__ == "__main__":
    main()