"""
EmbITE Logger

Reusable logging service for EmbITE framework execution.

Features:
- Automatically creates report directories if missing
- Creates one timestamped log file per run
- Writes logs to file
- Writes the same logs to console
- Supports INFO, WARNING, ERROR, PASS and FAIL
"""

from datetime import datetime
from pathlib import Path
import re
import traceback


class RunLogger:
    """Reusable logger for one complete EmbITE execution."""

    def __init__(
        self,
        project_name,
        report_directory,
        enabled=True,
        console=True,
    ):
        self.project_name = project_name
        self.enabled = enabled
        self.console = console

        self.log_file = None
        self._file = None

        if not self.enabled:
            return

        report_directory = Path(
            report_directory
        )

        # ------------------------------------------------------
        # CREATE REPORT DIRECTORY IF REQUIRED
        #
        # If directory already exists:
        #     Nothing happens.
        #
        # If directory does not exist:
        #     Complete path is created automatically.
        # ------------------------------------------------------

        report_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        # ------------------------------------------------------
        # SAFE PROJECT NAME
        # ------------------------------------------------------

        safe_project_name = re.sub(
            r"[^A-Za-z0-9_.-]+",
            "_",
            project_name,
        ).strip("_")

        if not safe_project_name:
            safe_project_name = "embite"

        # ------------------------------------------------------
        # RUN TIMESTAMP
        # ------------------------------------------------------

        run_timestamp = datetime.now().strftime(
            "%Y-%m-%d_%H%M%S"
        )

        # ------------------------------------------------------
        # LOG FILE
        # ------------------------------------------------------

        self.log_file = (
            report_directory
            / f"{safe_project_name}_{run_timestamp}.log"
        )

        self._file = self.log_file.open(
            "w",
            encoding="utf-8",
        )

    # ==========================================================
    # PUBLIC LOGGING METHODS
    # ==========================================================

    def info(self, message):
        self._write(
            "INFO",
            message,
        )

    def warning(self, message):
        self._write(
            "WARNING",
            message,
        )

    def error(self, message):
        self._write(
            "ERROR",
            message,
        )

    def pass_result(self, message):
        self._write(
            "PASS",
            message,
        )

    def fail_result(self, message):
        self._write(
            "FAIL",
            message,
        )

    def exception(
        self,
        message,
        exception=None,
    ):
        """
        Log an exception and traceback.
        """

        if exception is not None:
            self._write(
                "ERROR",
                f"{message}: {exception}",
            )
        else:
            self._write(
                "ERROR",
                message,
            )

        trace = traceback.format_exc()

        if (
            trace
            and trace != "NoneType: None\n"
        ):
            for line in trace.strip().splitlines():
                self._write(
                    "ERROR",
                    line,
                )

    def close(self):
        """
        Close the log file.
        """

        if (
            self._file
            and not self._file.closed
        ):
            self._file.close()

    # ==========================================================
    # INTERNAL
    # ==========================================================

    def _write(
        self,
        level,
        message,
    ):
        """
        Write formatted log entries to console and log file.

        Multi-line messages are split so every line
        gets its own timestamp and log level.
        """

        if not self.enabled:
            return

        message = str(message)

        # Split multiline messages
        lines = message.splitlines() or [""]

        for line in lines:

            timestamp = self._timestamp()

            # IMPORTANT:
            # use 'line' here, NOT 'message'
            log_line = (
                f"{timestamp} "
                f"[{level}] "
                f"{line}"
            )

            if self.console:
                print(log_line)

            if self._file:
                self._file.write(
                    log_line + "\n"
                )

                self._file.flush()

    @staticmethod
    def _timestamp():
        """
        Timestamp with millisecond precision.
        """

        now = datetime.now()

        return (
            now.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            + f".{now.microsecond // 1000:03d}"
        )
