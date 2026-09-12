"""
EmbITE - Embedded Integrated Test Environment

Main framework entry point.
"""

import getpass
import sys
from pathlib import Path

from board_actions.board_actions import BoardActions

from config.config_manager import ConfigManager

from utility.action_registry import ActionRegistry
from utility.executor import TestExecutor
from utility.parser import TestParser


def main():

    print("=" * 50)
    print("           EmbITE MVP")
    print("=" * 50)

    # ==========================================================
    # PROJECT PATH
    # ==========================================================

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
    print(
        f"Loading project configuration: "
        f"{project_config_file}"
    )

    # ==========================================================
    # LOAD PROJECT CONFIGURATION
    # ==========================================================

    config_manager = ConfigManager(
        project_config_file
    )

    config = config_manager.load()

    project_config = config.get(
        "project",
        {}
    )

    dut_config = config.get(
        "dut",
        {}
    )

    test_files = config.get(
        "tests",
        []
    )

    project_name = project_config.get(
        "name",
        project_path.name,
    )

    connection_config = dut_config.get(
        "connection",
        {}
    )

    connection_type = connection_config.get(
        "type"
    )

    print(f"Project: {project_name}")
    print(f"DUT: {dut_config.get('name')}")
    print(
        f"Connection type: "
        f"{connection_type}"
    )

    # ==========================================================
    # PASSWORD
    # ==========================================================

    password = None

    if connection_config.get(
        "password_prompt",
        False,
    ):
        password = getpass.getpass(
            "Enter password: "
        )

    # ==========================================================
    # BOARD ACTIONS
    # ==========================================================

    board = BoardActions(
        dut_config=dut_config,
        password=password,
    )

    print("Connecting to DUT...")

    try:

        board.connect()

        print(
            f"{connection_type.upper()} "
            f"connection established."
        )

        # ======================================================
        # DETECT DUT ENVIRONMENT
        # ======================================================

        environment = (
            board.detect_environment()
        )

        print(
            f"DUT OS: "
            f"{environment.get('os')}"
        )

        print(
            f"DUT Shell: "
            f"{environment.get('shell')}"
        )

        print(
            f"DUT Shell Path: "
            f"{environment.get('shell_path')}"
        )

        # ======================================================
        # DSL FRAMEWORK
        # ======================================================

        action_registry = ActionRegistry(
            board
        )

        parser = TestParser()

        test_executor = TestExecutor(
            action_registry
        )

        # ======================================================
        # EXECUTE PROJECT TEST FILES
        # ======================================================

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

        board.disconnect()

        print(
            f"\n{connection_type.upper()} "
            f"connection closed."
        )

    print(
        f"EmbITE project "
        f"'{project_name}' completed."
    )


if __name__ == "__main__":
    main()
