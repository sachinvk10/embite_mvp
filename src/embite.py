"""
EmbITE MVP - Main Execution Entry Point

File:
    src/embite.py

Purpose:
    This module is the main orchestration layer for the EmbITE MVP.

    It does not implement hardware-specific validation logic directly.
    Instead, it connects all major EmbITE framework components:

        Project Configuration
                ↓
        DUT Connection
                ↓
        Runtime Context
                ↓
        Action Registry
                ↓
        DSL Parser
                ↓
        DSL Executor
                ↓
        USB / Storage / System APIs
                ↓
        DUT
                ↓
        Logging / Reporting

Main Responsibilities:
    1. Accept a project directory from the command line.
    2. Load project configuration from:

           <project>/config/project.yaml

    3. Create the per-run logger.
    4. Connect to the DUT using BoardActions.
    5. Detect the DUT environment.
    6. Create one RuntimeContext for the complete test execution.
    7. Register all supported DSL APIs.
    8. Parse configured .tst files.
    9. Execute DSL APIs with variable parameters.
    10. Handle PASS / FAIL / BLOCKED results.
    11. Stop further execution when a storage safety condition is BLOCKED.
    12. Disconnect from the DUT safely.
    13. Generate one execution log for the complete run.

Runtime Context:
    A single RuntimeContext object is created for each EmbITE run.

    It allows one DSL API to dynamically pass information to another.

    Example:

        USB_DETECT
            ↓
        detects USB hardware topology

        USB_SELECT 1 2
            ↓
        stores selected USB devices

        RuntimeContext:
            PORT1 -> /dev/sda
            PORT2 -> /dev/sdc

        PARTITION_CREATE gpt 1 2G
            ↓
        dynamically discovers:
            PORT1 -> /dev/sda1
            PORT2 -> /dev/sdc1

        FILESYSTEM_CREATE ext4
            ↓
        automatically uses the partitions stored in RuntimeContext.

Storage Safety:
    Destructive storage operations are controlled through:

        storage:
          safety:
            allow_overwrite: false

    Default:
        allow_overwrite = false

    If existing device data is detected:
        - partition creation is blocked
        - filesystem creation is blocked
        - existing data is preserved
        - remaining dependent DSL operations are halted

    When allow_overwrite=true:
        - selected USB devices may be unmounted
        - existing partition/filesystem metadata may be replaced
        - only devices associated with USB_SELECT are allowed
        - unrelated system storage devices must never be modified

Usage:
    From the repository root:

        source .venv/bin/activate

        python -m src.embite projects/raspberry_pi5

Example project structure:

    projects/
    └── raspberry_pi5/
        ├── config/
        │   └── project.yaml
        ├── tests/
        │   ├── system.tst
        │   └── USB.tst
        └── report/
            └── runs/

Example USB.tst:

    USB_LIST
    USB_DETECT
    USB_SELECT 1 2

    STORAGE_INSPECT
    STORAGE_CHECK_MOUNT
    PARTITION_LIST

    PARTITION_CREATE gpt 1 2G
    FILESYSTEM_CREATE ext4

    STORAGE_MOUNT
    STORAGE_CHECK_MOUNT

    STORAGE_UNMOUNT
"""

import getpass
import sys
from pathlib import Path

from board_actions.board_actions import BoardActions
from lib.storage import Storage
from lib.usb import USB
from utility.action_registry import ActionRegistry
from utility.config_manager import ConfigManager
from utility.executor import TestExecutor
from utility.logger import RunLogger
from utility.parser import TestParser
from utility.runtime_context import RuntimeContext


def main():
    """
    Execute one complete EmbITE MVP project run.

    Command-line syntax:

        python -m src.embite <project_path>

    Example:

        python -m src.embite projects/raspberry_pi5

    Execution Flow:
        1. Validate command-line arguments.
        2. Resolve the project directory.
        3. Load project.yaml.
        4. Initialize logging.
        5. Read DUT connection details.
        6. Prompt for password if configured.
        7. Connect to DUT.
        8. Detect DUT environment.
        9. Create shared RuntimeContext.
        10. Initialize ActionRegistry.
        11. Register USB DSL APIs.
        12. Register Storage DSL APIs.
        13. Parse each configured test file.
        14. Execute DSL APIs.
        15. Log PASS / FAIL / BLOCKED results.
        16. Halt dependent execution on BLOCKED safety conditions.
        17. Disconnect DUT.
        18. Close report log.

    Overall Status:
        PASS:
            All executed DSL APIs passed.

        FAIL:
            One or more DSL APIs failed due to execution/runtime errors.

        BLOCKED:
            Execution was intentionally stopped by an EmbITE safety rule.

            Example:
                Existing storage data detected while:

                    allow_overwrite: false
    """

    # ==========================================================
    # COMMAND-LINE VALIDATION
    # ==========================================================

    if len(sys.argv) != 2:
        print(
            "Usage: python -m src.embite <project_path>"
        )
        raise SystemExit(2)

    # Example:
    #
    #   projects/raspberry_pi5
    #
    project_path = Path(
        sys.argv[1]
    )

    # Every EmbITE project has its own project.yaml.
    config_path = (
        project_path
        / "config"
        / "project.yaml"
    )

    # ==========================================================
    # LOAD PROJECT CONFIGURATION
    # ==========================================================

    config_manager = ConfigManager(
        config_path
    )

    config = config_manager.load()

    # ----------------------------------------------------------
    # Project metadata
    # ----------------------------------------------------------

    project_config = (
        config.get(
            "project",
            {},
        )
        or {}
    )

    # ----------------------------------------------------------
    # DUT configuration
    # ----------------------------------------------------------

    dut_config = (
        config.get(
            "dut",
            {},
        )
        or {}
    )

    # ----------------------------------------------------------
    # Test files
    #
    # Example:
    #
    # tests:
    #   - tests/system.tst
    #   - tests/USB.tst
    # ----------------------------------------------------------

    tests_config = (
        config.get(
            "tests",
            [],
        )
        or []
    )

    # ----------------------------------------------------------
    # Reporting configuration
    # ----------------------------------------------------------

    reporting_config = (
        config.get(
            "reporting",
            {},
        )
        or {}
    )

    # ----------------------------------------------------------
    # Storage safety configuration
    #
    # Example:
    #
    # storage:
    #   safety:
    #     allow_overwrite: false
    # ----------------------------------------------------------

    storage_config = (
        config.get(
            "storage",
            {},
        )
        or {}
    )

    # Use configured project name.
    #
    # If absent, use the project directory name.
    project_name = project_config.get(
        "name",
        project_path.name,
    )

    # ==========================================================
    # REPORTING / LOGGER CONFIGURATION
    # ==========================================================

    reporting_enabled = bool(
        reporting_config.get(
            "enabled",
            False,
        )
    )

    reporting_console = bool(
        reporting_config.get(
            "console",
            True,
        )
    )

    # Example:
    #
    # projects/raspberry_pi5/report/runs/
    #
    report_directory = (
        project_path
        / reporting_config.get(
            "directory",
            "report/runs",
        )
    )

    # RunLogger automatically creates the report directory
    # if reporting is enabled.
    #
    # One log file is created for the complete EmbITE run.
    logger = RunLogger(
        project_name=project_name,
        report_directory=report_directory,
        enabled=reporting_enabled,
        console=reporting_console,
    )

    # ==========================================================
    # RUNTIME STATE
    # ==========================================================

    board = None

    connection_established = False

    overall_status = "PASS"

    try:

        # ======================================================
        # EXECUTION START
        # ======================================================

        logger.info(
            "EmbITE MVP execution started"
        )

        logger.info(
            f"Project: {project_name}"
        )

        logger.info(
            f"Project path: {project_path}"
        )

        logger.info(
            f"Configuration: {config_path}"
        )

        if logger.log_path:

            logger.info(
                f"Report log: {logger.log_path}"
            )

        # ======================================================
        # STORAGE SAFETY POLICY
        # ======================================================

        safety = (
            storage_config.get(
                "safety",
                {},
            )
            or {}
        )

        # IMPORTANT:
        #
        # Default must always remain False.
        #
        # A missing configuration must never enable
        # destructive storage operations.
        allow_overwrite = safety.get(
            "allow_overwrite",
            False,
        )

        logger.info(
            "Storage allow_overwrite: "
            f"{allow_overwrite}"
        )

        # ======================================================
        # DUT CONNECTION CONFIGURATION
        # ======================================================

        connection_config = (
            dut_config.get(
                "connection",
                {},
            )
            or {}
        )

        password = None

        # Password is intentionally not stored in RuntimeContext
        # or written to any report.
        if connection_config.get(
            "password_prompt",
            False,
        ):

            password = getpass.getpass(
                "DUT password: "
            )

        # ======================================================
        # BOARD ACTIONS
        # ======================================================

        board = BoardActions(
            dut_config=dut_config,
            password=password,
        )

        logger.info(
            "DUT: "
            + str(
                dut_config.get(
                    "name",
                    dut_config.get(
                        "platform",
                        "unknown",
                    ),
                )
            )
        )

        logger.info(
            "Connection: "
            + str(
                connection_config.get(
                    "type",
                    "unknown",
                )
            )
            + " -> "
            + str(
                connection_config.get(
                    "host",
                    "unknown",
                )
            )
        )

        # ======================================================
        # CONNECT TO DUT
        # ======================================================

        board.connect()

        connection_established = True

        logger.pass_result(
            "DUT connection established"
        )

        # ======================================================
        # DETECT DUT ENVIRONMENT
        # ======================================================

        environment = (
            board.detect_environment()
        )

        logger.info(
            f"Detected environment: {environment}"
        )

        # ======================================================
        # CREATE SHARED RUNTIME CONTEXT
        # ======================================================

        # One RuntimeContext exists for the entire run.
        #
        # All DSL libraries receive the same object.
        #
        # This allows information discovered by one API
        # to be reused by subsequent APIs.
        #
        # Example:
        #
        # USB_DETECT
        #     ↓
        # USB_SELECT 1 2
        #     ↓
        # RuntimeContext
        #     PORT1 -> /dev/sda
        #     PORT2 -> /dev/sdc
        #
        runtime_context = RuntimeContext()

        # ======================================================
        # ACTION REGISTRY
        # ======================================================

        # ActionRegistry automatically contains the
        # system-level DSL APIs:
        #
        # GET_HOSTNAME
        # GET_IP_ADDRESS
        # GET_OS
        # GET_KERNEL
        # GET_ARCHITECTURE
        # GET_MEMORY
        #
        action_registry = ActionRegistry(
            board
        )

        # ======================================================
        # USB VALIDATION LIBRARY
        # ======================================================

        usb = USB(
            board_actions=board,
            runtime_context=runtime_context,
        )

        # ======================================================
        # STORAGE VALIDATION LIBRARY
        # ======================================================

        storage = Storage(
            board_actions=board,
            runtime_context=runtime_context,
            storage_config=storage_config,
        )

        # ======================================================
        # REGISTER USB DSL APIs
        # ======================================================

        # USB_LIST
        #
        # Lists connected USB devices and metadata.
        action_registry.register(
            "USB_LIST",
            usb.list_devices,
        )

        # USB_DETECT
        #
        # Detects occupied USB topology/hardware ports
        # and stores discovered information into
        # RuntimeContext.
        action_registry.register(
            "USB_DETECT",
            usb.detect_ports,
        )

        # USB_SELECT <port1> [port2] [port3] ...
        #
        # Examples:
        #
        # USB_SELECT 1
        # USB_SELECT 1 2
        # USB_SELECT 1 2 3
        #
        # Only the selected USB ports are allowed to
        # participate in later storage operations.
        action_registry.register(
            "USB_SELECT",
            usb.select_ports,
        )

        # ======================================================
        # REGISTER STORAGE DSL APIs
        # ======================================================

        # STORAGE_INSPECT
        #
        # Safely inspect selected storage devices.
        action_registry.register(
            "STORAGE_INSPECT",
            storage.inspect,
        )

        # STORAGE_CHECK_MOUNT
        #
        # Detect existing automount/manual mount state.
        action_registry.register(
            "STORAGE_CHECK_MOUNT",
            storage.check_mount,
        )

        # STORAGE_UNMOUNT
        #
        # Unmount selected storage partitions.
        action_registry.register(
            "STORAGE_UNMOUNT",
            storage.unmount,
        )

        # STORAGE_MOUNT
        #
        # Dynamically creates mount points such as:
        #
        # /mnt/embite/PORT1/partition1/mountpoint1
        #
        action_registry.register(
            "STORAGE_MOUNT",
            storage.mount,
        )

        # PARTITION_LIST
        #
        # Lists partitions belonging only to the
        # selected USB storage devices.
        action_registry.register(
            "PARTITION_LIST",
            storage.list_partitions,
        )

        # PARTITION_CREATE <table> <number> <size>
        #
        # Example:
        #
        # PARTITION_CREATE gpt 1 2G
        #
        action_registry.register(
            "PARTITION_CREATE",
            storage.create_partition,
        )

        # FILESYSTEM_DETECT
        #
        # Detect filesystems on selected partitions.
        action_registry.register(
            "FILESYSTEM_DETECT",
            storage.detect_filesystem,
        )

        # FILESYSTEM_CREATE <filesystem>
        #
        # Example:
        #
        # FILESYSTEM_CREATE ext4
        #
        action_registry.register(
            "FILESYSTEM_CREATE",
            storage.create_filesystem,
        )

        # ======================================================
        # DSL PARSER AND EXECUTOR
        # ======================================================

        parser = TestParser()

        executor = TestExecutor(
            action_registry
        )

        # When a safety-related action becomes BLOCKED,
        # remaining dependent test execution must stop.
        halt_execution = False

        # ======================================================
        # EXECUTE CONFIGURED TEST FILES
        # ======================================================

        for test_entry in tests_config:

            if halt_execution:
                break

            # Example:
            #
            # projects/raspberry_pi5/tests/USB.tst
            #
            test_file = (
                project_path
                / test_entry
            )

            logger.info(
                f"Test file: {test_file}"
            )

            # --------------------------------------------------
            # Parse DSL
            # --------------------------------------------------

            actions = parser.parse(
                test_file
            )

            if not actions:

                logger.warning(
                    f"No actions found in {test_file}"
                )

                continue

            # Log DSL before execution.
            #
            # Example:
            #
            # DSL: USB_SELECT 1 2
            # DSL: PARTITION_CREATE gpt 1 2G
            #
            for action in actions:

                logger.info(
                    f"DSL: {action['raw']}"
                )

            # --------------------------------------------------
            # Execute parsed DSL
            # --------------------------------------------------

            results = executor.execute(
                actions
            )

            # ==================================================
            # PROCESS DSL RESULTS
            # ==================================================

            for result in results:

                action_display = result.get(
                    "raw",
                    result["action"],
                )

                status = result[
                    "status"
                ]

                # ==============================================
                # PASS
                # ==============================================

                if status == "PASS":

                    logger.pass_result(
                        f"{action_display} -> "
                        f"{result.get('result', '')}"
                    )

                # ==============================================
                # BLOCKED
                # ==============================================

                elif status == "BLOCKED":

                    # BLOCKED does not necessarily mean that
                    # the framework itself failed.
                    #
                    # It means a safety rule intentionally
                    # prevented the requested operation.
                    if overall_status == "PASS":

                        overall_status = (
                            "BLOCKED"
                        )

                    logger.blocked(
                        f"{action_display} -> "
                        f"{result.get('error', '')}"
                    )

                    logger.blocked(
                        "Execution halted. "
                        "Remaining DSL actions will not run "
                        "until the safety condition is resolved."
                    )

                    halt_execution = True

                # ==============================================
                # FAIL
                # ==============================================

                else:

                    overall_status = "FAIL"

                    logger.fail_result(
                        f"{action_display} -> "
                        f"{result.get('error', '')}"
                    )

        # ======================================================
        # COMPLETE EXECUTION
        # ======================================================

        logger.info(
            f"Overall status: {overall_status}"
        )

    # ==========================================================
    # TOP-LEVEL EXECUTION ERROR
    # ==========================================================

    except Exception as exc:

        overall_status = "FAIL"

        logger.exception(
            str(exc)
        )

        # Re-raise so command line / CI also receives
        # the execution failure.
        raise

    # ==========================================================
    # CLEANUP
    # ==========================================================

    finally:

        # Disconnect only when the connection was
        # successfully established.
        if board and connection_established:

            try:

                board.disconnect()

                logger.info(
                    "DUT disconnected"
                )

            except Exception as exc:

                # Disconnect issues should be logged,
                # but should not hide the original result.
                logger.warning(
                    "DUT disconnect warning: "
                    f"{exc}"
                )

        logger.info(
            f"Final status: {overall_status}"
        )

        logger.close()


# ==============================================================
# PYTHON MODULE ENTRY POINT
# ==============================================================

if __name__ == "__main__":
    main()
