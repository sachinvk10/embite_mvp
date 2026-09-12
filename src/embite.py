"""
EmbITE - Embedded Integrated Test Environment

Main framework entry point.
"""

import getpass
import sys
from pathlib import Path

from board_action.command_executor import CommandExecutor
from board_action.shell_detector import ShellDetector
from board_action.ssh_connection import SSHConnection

from config.config_manager import ConfigManager

from utility.action_registry import ActionRegistry
from utility.executor import TestExecutor
from utility.parser import TestParser

from lib.system_info import SystemInfo


def main():
    print("=" * 50)
    print("           EmbITE MVP")
    print("=" * 50)

    # --------------------------------------------------
    # Project path
    # --------------------------------------------------

    if len(sys.argv) != 2:
        print(
            "Usage: python -m src.embite "
            "projects/<project_name>"
        )
        sys.exit(1)

    project_path = Path(sys.argv[1])

    if not project_path.exists():
        raise FileNotFoundError(
            f"Project directory not found: {project_path}"
        )

    project_config_file = (
        project_path / "config" / "project.yaml"
    )

    print(f"Project path: {project_path}")
    print(f"Loading project configuration: {project_config_file}")

    # --------------------------------------------------
    # Load Project Configuration
    # --------------------------------------------------

    config_manager = ConfigManager(project_config_file)
    config = config_manager.load()

    project_config = config.get("project", {})
    dut_config = config.get("dut", {})
    test_files = config.get("tests", [])

    project_name = project_config.get(
        "name",
        project_path.name,
    )

    connection_config = dut_config.get(
        "connection",
        {},
    )

    print(f"Project: {project_name}")
    print(f"DUT: {dut_config.get('name')}")
    print(
        f"Connection type: "
        f"{connection_config.get('type')}"
    )

    # --------------------------------------------------
    # Validate Connection Type
    # --------------------------------------------------

    if connection_config.get("type") != "ssh":
        raise ValueError(
            f"Unsupported connection type: "
            f"{connection_config.get('type')}"
        )

    # --------------------------------------------------
    # Credentials
    # --------------------------------------------------

    password = None

    if connection_config.get(
        "password_prompt",
        True,
    ):
        password = getpass.getpass(
            "Enter password: "
        )

    # --------------------------------------------------
    # Create Connection
    # --------------------------------------------------

    connection = SSHConnection(
        host=connection_config.get("host"),
        port=connection_config.get(
            "port",
            22,
        ),
        username=connection_config.get(
            "username"
        ),
        password=password,
    )

    print("Connecting to DUT...")

    try:
        connection.connect()

        print("SSH connection established.")

        # ----------------------------------------------
        # Detect DUT Environment
        # ----------------------------------------------

        shell_detector = ShellDetector(
            connection
        )

        shell_info = shell_detector.detect()

        print(
            f"DUT OS: "
            f"{shell_info['os']}"
        )
        print(
            f"DUT Shell: "
            f"{shell_info['shell']}"
        )
        print(
            f"DUT Shell Path: "
            f"{shell_info['shell_path']}"
        )

        # ----------------------------------------------
        # Framework Components
        # ----------------------------------------------

        command_executor = CommandExecutor(
            connection
        )

        system_info = SystemInfo(
            command_executor
        )

        action_registry = ActionRegistry(
            system_info
        )

        parser = TestParser()

        test_executor = TestExecutor(
            action_registry
        )

        # ----------------------------------------------
        # Execute Project Test Files
        # ----------------------------------------------

        if not test_files:
            print(
                "\nNo test files configured "
                "for this project."
            )
            return

        print("\nConfigured test files:")

        for test_file in test_files:
            print(f"  - {test_file}")

        for test_file in test_files:

            test_file_path = (
                project_path / test_file
            )

            if not test_file_path.exists():
                raise FileNotFoundError(
                    f"Test file not found: "
                    f"{test_file_path}"
                )

            print("\n" + "=" * 50)
            print(
                f"Executing Test File: "
                f"{test_file}"
            )
            print("=" * 50)

            actions = parser.parse(
                test_file_path
            )

            print(
                f"Actions: {actions}"
            )

            results = test_executor.execute(
                actions
            )

            print("\nTest Results")
            print("-" * 50)

            for result in results:

                print(
                    f"Action : "
                    f"{result['action']}"
                )

                print(
                    f"Status : "
                    f"{result['status']}"
                )

                if result["status"] == "PASS":
                    print(
                        f"Result : "
                        f"{result['result']}"
                    )
                else:
                    print(
                        f"Error  : "
                        f"{result['error']}"
                    )

                print("-" * 50)

    finally:

        connection.disconnect()

        print(
            "\nSSH connection closed."
        )

    print(
        f"EmbITE project "
        f"'{project_name}' completed."
    )


if __name__ == "__main__":
    main()
