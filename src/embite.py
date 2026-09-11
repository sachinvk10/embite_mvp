"""
EmbITE - Embedded Integrated Test Environment

Main framework entry point.
"""

import getpass

from board_action.command_executor import CommandExecutor
from board_action.shell_detector import ShellDetector
from board_action.ssh_connection import SSHConnection

from config.config_manager import ConfigManager

from executor.action_registry import ActionRegistry
from executor.test_executor import TestExecutor
from executor.test_parser import TestParser

from lib.system_info import SystemInfo


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

    try:
        connection.connect()

        print("SSH connection established.")

        # Detect DUT execution environment
        shell_detector = ShellDetector(connection)
        shell_info = shell_detector.detect()

        print(f"DUT OS: {shell_info['os']}")
        print(f"DUT Shell: {shell_info['shell']}")
        print(f"DUT Shell Path: {shell_info['shell_path']}")

        # Generic DUT command execution layer
        command_executor = CommandExecutor(connection)

        # Validation libraries
        system_info = SystemInfo(command_executor)

        # DSL action mapping
        action_registry = ActionRegistry(system_info)

        # Parse .tst file
        test_file = "tests/system/system_info.tst"

        print(f"\nLoading test file: {test_file}")

        parser = TestParser()
        actions = parser.parse(test_file)

        print(f"Actions: {actions}")

        # Execute parsed DSL actions
        test_executor = TestExecutor(action_registry)
        results = test_executor.execute(actions)

        print("\nTest Results")
        print("-" * 50)

        for result in results:
            print(f"Action : {result['action']}")
            print(f"Status : {result['status']}")

            if result["status"] == "PASS":
                print(f"Result : {result['result']}")
            else:
                print(f"Error  : {result['error']}")

            print("-" * 50)

    finally:
        connection.disconnect()

        print("\nSSH connection closed.")

    print("EmbITE MVP completed.")


if __name__ == "__main__":
    main()
