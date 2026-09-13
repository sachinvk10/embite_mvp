"""
EmbITE MVP - Run Logger

File:
    utility/logger.py

Purpose:
    This module provides the common execution logger used by the
    EmbITE framework.

    The same logger is used for:

        - Console output
        - Per-run report log file
        - Framework information
        - DSL PASS results
        - DSL FAIL results
        - Safety BLOCKED results
        - Warnings
        - Exceptions


Architecture:

    src/embite.py
          ↓
      RunLogger
       ┌────┴────┐
       ↓         ↓
    Console    Log File


Example Log File:

    projects/
    └── raspberry_pi5/
        └── report/
            └── runs/
                └── raspberry_pi5_2026-09-13_002500.log


Log Format:

    YYYY-MM-DD HH:MM:SS.mmm [LEVEL] message


Example:

    2026-09-13 00:25:00.120 [INFO] EmbITE MVP execution started
    2026-09-13 00:25:01.310 [PASS] DUT connection established
    2026-09-13 00:25:02.101 [INFO] DSL: USB_DETECT
    2026-09-13 00:25:02.500 [PASS] USB_DETECT -> [PORT1]
    2026-09-13 00:25:02.501 [PASS] USB Root Path : 3-1


Multiline Logging
=================

Many EmbITE APIs return multiline information.

Example:

    STORAGE_INSPECT

may return:

    [PORT1]
    Node             : /dev/sda
    Transport        : usb
    Existing Content : YES

Every physical line must receive its own timestamp and log level.

Correct:

    2026-09-13 00:25:05.100 [PASS] STORAGE_INSPECT -> [PORT1]
    2026-09-13 00:25:05.101 [PASS] Node             : /dev/sda
    2026-09-13 00:25:05.102 [PASS] Transport        : usb
    2026-09-13 00:25:05.103 [PASS] Existing Content : YES

This is intentionally implemented by splitting multiline messages before
writing them.


BLOCKED Status
==============

BLOCKED is different from FAIL.

Example:

    PARTITION_CREATE gpt 1 2G

when:

    storage:
      safety:
        allow_overwrite: false

and existing data is detected.

The result should be:

    [BLOCKED]

because the framework intentionally protected the storage device.

It is not a framework execution failure.


Logger Configuration
====================

Example project.yaml:

    reporting:
      enabled: true
      directory: report/runs
      console: true


Parameters:

    enabled:
        Enables/disables RunLogger output.

        If false:
            - no log directory is created
            - no log file is created
            - logger methods silently return

    console:
        When enabled=true:

        true:
            write to console and log file

        false:
            write only to the log file


Log File Naming
===============

Format:

    <project_name>_<YYYY-MM-DD_HHMMSS>.log

Example:

    raspberry_pi5_2026-09-13_002500.log


Project names are sanitized before being used as filenames.
"""

import re
import traceback
from datetime import datetime
from pathlib import Path


class RunLogger:
    """
    EmbITE per-run logger.

    One RunLogger instance should be created for one complete
    EmbITE project execution.

    Parameters:
        project_name:
            Name of the EmbITE project.

            Example:
                raspberry_pi5

        report_directory:
            Directory in which the run log should be created.

            Example:
                projects/raspberry_pi5/report/runs

        enabled:
            Enable or disable logger output.

            Default:
                True

        console:
            Print log messages to the console in addition to the
            log file.

            Default:
                True


    Example:

        logger = RunLogger(
            project_name="raspberry_pi5",
            report_directory=(
                "projects/raspberry_pi5/report/runs"
            ),
            enabled=True,
            console=True,
        )

        logger.info(
            "EmbITE MVP execution started"
        )

        logger.pass_result(
            "GET_HOSTNAME -> raspberrypi"
        )

        logger.close()
    """

    def __init__(
        self,
        project_name,
        report_directory,
        enabled=True,
        console=True,
    ):
        """
        Initialize the EmbITE run logger.

        When logging is enabled:

            1. Sanitize project name.
            2. Create report directory if missing.
            3. Generate timestamped log filename.
            4. Open one log file for the complete run.
        """

        self.project_name = str(
            project_name
        )

        self.report_directory = Path(
            report_directory
        )

        self.enabled = bool(
            enabled
        )

        self.console = bool(
            console
        )

        # File object used for the current execution log.
        self._file = None

        # Public path of the current run log.
        #
        # src/embite.py can display:
        #
        #     logger.log_path
        #
        self.log_path = None

        # Prevent duplicate close operations.
        self._closed = False

        # ------------------------------------------------------
        # Logging disabled
        # ------------------------------------------------------
        #
        # Important:
        #
        # Do not create:
        #
        #   report/
        #   report/runs/
        #   *.log
        #
        # when logger is disabled.
        #
        if not self.enabled:
            return

        # ------------------------------------------------------
        # Create report directory automatically
        # ------------------------------------------------------

        self.report_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        # ------------------------------------------------------
        # Sanitize project name for filesystem use
        # ------------------------------------------------------

        safe_project_name = (
            self._sanitize_project_name(
                self.project_name
            )
        )

        # ------------------------------------------------------
        # Generate one filename for this complete execution
        # ------------------------------------------------------

        file_timestamp = datetime.now().strftime(
            "%Y-%m-%d_%H%M%S"
        )

        filename = (
            f"{safe_project_name}_"
            f"{file_timestamp}.log"
        )

        self.log_path = (
            self.report_directory
            / filename
        )

        # ------------------------------------------------------
        # Open log file
        # ------------------------------------------------------

        self._file = self.log_path.open(
            mode="a",
            encoding="utf-8",
        )

    # ==========================================================
    # PUBLIC LOGGING APIs
    # ==========================================================

    def info(
        self,
        message,
    ):
        """
        Write INFO-level message.

        Example:

            logger.info(
                "EmbITE MVP execution started"
            )
        """

        self._write(
            "INFO",
            message,
        )

    def warning(
        self,
        message,
    ):
        """
        Write WARNING-level message.

        Example:

            logger.warning(
                "DUT disconnect warning"
            )
        """

        self._write(
            "WARNING",
            message,
        )

    def error(
        self,
        message,
    ):
        """
        Write ERROR-level message.

        Intended for framework/runtime errors that do not already
        have a specific PASS/FAIL/BLOCKED semantic.
        """

        self._write(
            "ERROR",
            message,
        )

    def pass_result(
        self,
        message,
    ):
        """
        Write PASS-level DSL/test result.

        Example:

            logger.pass_result(
                "GET_HOSTNAME -> raspberrypi"
            )

        Multiline API results are automatically split so every physical
        line receives its own timestamp.
        """

        self._write(
            "PASS",
            message,
        )

    def fail_result(
        self,
        message,
    ):
        """
        Write FAIL-level DSL/test result.

        Example:

            logger.fail_result(
                "USB_DETECT -> no USB device detected"
            )
        """

        self._write(
            "FAIL",
            message,
        )

    def blocked(
        self,
        message,
    ):
        """
        Write BLOCKED-level result.

        BLOCKED represents intentional framework protection.

        Example:

            logger.blocked(
                "PARTITION_CREATE -> "
                "existing data detected"
            )

        Typical causes:
            - allow_overwrite=false
            - selected USB port has no storage
            - storage device changed after USB_SELECT
            - ambiguous USB storage selection
            - destructive operation is not considered safe
        """

        self._write(
            "BLOCKED",
            message,
        )

    def exception(
        self,
        message,
        include_traceback=True,
    ):
        """
        Log an exception.

        Parameters:
            message:
                Human-readable error description.

            include_traceback:
                If true, include the active Python traceback.

                Default:
                    True

        Example:

            try:
                ...
            except Exception as exc:

                logger.exception(
                    str(exc)
                )

        Output example:

            [ERROR] Unexpected execution error
            [ERROR] Traceback (most recent call last):
            [ERROR] ...
        """

        self._write(
            "ERROR",
            message,
        )

        if not include_traceback:
            return

        traceback_text = (
            traceback.format_exc()
        )

        # traceback.format_exc() returns:
        #
        # "NoneType: None"
        #
        # when called outside an active exception handler.
        #
        # Avoid adding that meaningless text to the report.
        if (
            traceback_text
            and traceback_text.strip()
            != "NoneType: None"
        ):

            self._write(
                "ERROR",
                traceback_text.rstrip(),
            )

    # ==========================================================
    # CORE WRITE IMPLEMENTATION
    # ==========================================================

    def _write(
        self,
        level,
        message,
    ):
        """
        Write one logical message.

        Multiline messages are split into separate physical log lines.

        Every physical line receives:
            - timestamp
            - log level

        Example input:

            message =
                "Node: /dev/sda\\n"
                "Filesystem: ext4"

        Output:

            timestamp [PASS] Node: /dev/sda
            timestamp [PASS] Filesystem: ext4
        """

        if not self.enabled:
            return

        if self._closed:
            return

        # ------------------------------------------------------
        # Normalize message
        # ------------------------------------------------------

        if message is None:
            message = ""

        message = str(
            message
        )

        # ------------------------------------------------------
        # Split multiline API output
        # ------------------------------------------------------

        lines = (
            message.splitlines()
            or [""]
        )

        for line in lines:

            timestamp = (
                self._timestamp()
            )

            log_line = (
                f"{timestamp} "
                f"[{level}] "
                f"{line}"
            )

            # --------------------------------------------------
            # Console output
            # --------------------------------------------------

            if self.console:

                print(
                    log_line,
                    flush=True,
                )

            # --------------------------------------------------
            # File output
            # --------------------------------------------------

            if self._file:

                self._file.write(
                    log_line
                    + "\n"
                )

                # Flush immediately so logs survive even if an
                # unexpected failure occurs later in execution.
                self._file.flush()

    # ==========================================================
    # TIMESTAMP
    # ==========================================================

    @staticmethod
    def _timestamp():
        """
        Return timestamp with millisecond precision.

        Format:

            YYYY-MM-DD HH:MM:SS.mmm

        Example:

            2026-09-13 00:25:10.123
        """

        now = datetime.now()

        milliseconds = (
            now.microsecond
            // 1000
        )

        return (
            now.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            + f".{milliseconds:03d}"
        )

    # ==========================================================
    # PROJECT NAME SANITIZATION
    # ==========================================================

    @staticmethod
    def _sanitize_project_name(
        project_name,
    ):
        """
        Convert project name into a safe filename component.

        Example:

            "Raspberry Pi 5 Validation"

        becomes:

            "Raspberry_Pi_5_Validation"

        Characters other than:

            letters
            numbers
            underscore
            hyphen

        are replaced with underscore.
        """

        value = str(
            project_name
        ).strip()

        value = re.sub(
            r"[^A-Za-z0-9_-]+",
            "_",
            value,
        )

        value = value.strip(
            "_"
        )

        if not value:

            return "embite"

        return value

    # ==========================================================
    # CLOSE LOGGER
    # ==========================================================

    def close(self):
        """
        Flush and close the current run log.

        Safe to call more than once.

        Normally called from:

            src/embite.py

        inside its finally block.
        """

        if self._closed:
            return

        if self._file:

            try:

                self._file.flush()

            finally:

                self._file.close()

                self._file = None

        self._closed = True

    # ==========================================================
    # CONTEXT MANAGER SUPPORT
    # ==========================================================

    def __enter__(self):
        """
        Optional Python context-manager support.

        Example:

            with RunLogger(...) as logger:
                logger.info("Started")
        """

        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        exc_traceback,
    ):
        """
        Automatically close logger when used as a context manager.
        """

        self.close()

        # Do not suppress exceptions.
        return False
