"""
EmbITE - Embedded Integrated Test Environment

Main framework entry point.
"""

import getpass
import sys
from pathlib import Path

from board_actions.board_actions import BoardActions

from utility.action_registry import ActionRegistry
from utility.config_manager import ConfigManager
from utility.executor import TestExecutor
from utility.logger import RunLogger
from utility.parser import TestParser


def main():

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

    if not project_path.is_dir():
        raise ValueError(
            f"Project path is not a directory: {project_path}"
        )

    project_config_file = (
        project_path / "config" / "project.yaml"
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

    # ==========================================================
    # REPORTING / LOGGING
    # ==========================================================

    reporting_config = config.get(
        "reporting",
        {}
    )

    reporting_enabled = reporting_config.get(
        "enabled",
        False,
    )

    report_directory = (
        project_path
        / reporting_config.get(
            "directory",
            "report/runs",
        )
    )

    logger = RunLogger(
        project_name=project_name,
        report_directory=report_directory,
        enabled=reporting_enabled,
        console=reporting_config.get(
            "console",
            True,
        ),
    )

    # ==========================================================
    # FRAMEWORK STARTUP
    # ==========================================================

    logger.info(
        "=" * 50
    )

    logger.info(
        "EmbITE MVP execution started"
    )

    logger.info(
        "=" * 50
    )

    logger.info(
        f"Project path: {project_path}"
    )

    logger.info(
        f"Configuration: {project_config_file}"
    )

    logger.info(
        f"Project: {project_name}"
    )

    logger.info(
        f"DUT: {dut_config.get('name')}"
    )

    logger.info(
        f"Platform: {dut_config.get('platform')}"
    )

    logger.info(
        f"Connection type: {connection_type}"
    )

    if logger.log_file:
        logger.info(
            f"Report log: {logger.log_file}"
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

    overall_status = "PASS"
    connection_established = False

    try:

        # ======================================================
        # CONNECT TO DUT
        # ======================================================

        logger.info(
            "Connecting to DUT"
        )

        board.connect()

        connection_established = True

        logger.info(
            f"{connection_type.upper()} "
            f"connection established"
        )

        # ======================================================
        # DETECT DUT ENVIRONMENT
        # ======================================================

        environment = (
            board.detect_environment()
        )

        dut_os = environment.get(
            "os"
        )

        dut_shell = environment.get(
            "shell"
        )

        dut_shell_path = environment.get(
            "shell_path"
        )

        logger.info(
            f"DUT OS: {dut_os}"
        )

        logger.info(
            f"DUT Shell: {dut_shell}"
        )

        logger.info(
            f"DUT Shell Path: "
            f"{dut_shell_path}"
        )

        # ======================================================
        # DSL FRAMEWORK COMPONENTS
        # ======================================================

        action_registry = ActionRegistry(
            board
        )

        parser = TestParser()

        test_executor = TestExecutor(
            action_registry
        )

        # ======================================================
        # TEST FILE CONFIGURATION
        # ======================================================

        if not test_files:

            logger.warning(
                "No test files configured "
                "for this project"
            )

        else:

            logger.info(
                "Configured test files: "
                + ", ".join(test_files)
            )

        # ======================================================
        # EXECUTE PROJECT TEST FILES
        # ======================================================

        for test_file in test_files:

            test_file_path = (
                project_path / test_file
            )

            if not test_file_path.exists():

                overall_status = "FAIL"

                raise FileNotFoundError(
                    f"Test file not found: "
                    f"{test_file_path}"
                )

            logger.info(
                "-" * 50
            )

            logger.info(
                f"Test file started: "
                f"{test_file}"
            )

            # --------------------------------------------------
            # PARSE TEST FILE
            # --------------------------------------------------

            actions = parser.parse(
                test_file_path
            )

            logger.info(
                f"Actions: {actions}"
            )

            # --------------------------------------------------
            # EXECUTE ACTIONS
            # --------------------------------------------------

            results = test_executor.execute(
                actions
            )

            # --------------------------------------------------
            # PROCESS RESULTS
            # --------------------------------------------------

            for result in results:

                action_name = result.get(
                    "action"
                )

                action_status = result.get(
                    "status"
                )

                if action_status == "PASS":

                    action_result = result.get(
                        "result"
                    )

                    logger.pass_result(
                        f"{action_name} -> "
                        f"{action_result}"
                    )

                else:

                    overall_status = "FAIL"

                    action_error = result.get(
                        "error"
                    )

                    logger.fail_result(
                        f"{action_name} -> "
                        f"{action_error}"
                    )

            logger.info(
                f"Test file completed: "
                f"{test_file}"
            )

            logger.info(
                "-" * 50
            )

    except Exception as exc:

        overall_status = "FAIL"

        logger.exception(
            "EmbITE execution failed",
            exc,
        )

        raise

    finally:

        # ======================================================
        # DISCONNECT DUT
        # ======================================================

        try:

            board.disconnect()

            if connection_established:

                logger.info(
                    f"{connection_type.upper()} "
                    f"connection closed"
                )

        except Exception as disconnect_error:

            overall_status = "FAIL"

            logger.error(
                "Failed to disconnect DUT: "
                f"{disconnect_error}"
            )

        # ======================================================
        # FINAL RUN STATUS
        # ======================================================

        logger.info(
            f"Overall status: "
            f"{overall_status}"
        )

        logger.info(
            f"EmbITE project "
            f"'{project_name}' completed"
        )

        logger.info(
            "=" * 50
        )

        logger.close()


if __name__ == "__main__":
    main()
