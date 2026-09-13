"""
EmbITE MVP - DSL Test Parser

File:
    utility/parser.py

Purpose:
    This module reads EmbITE `.tst` files and converts each DSL line
    into a structured action object that can be consumed by:

        utility/executor.py

Architecture:

    .tst File
        ↓
    TestParser
        ↓
    Parsed Action Dictionary
        ↓
    TestExecutor
        ↓
    ActionRegistry
        ↓
    Python API Function


Supported DSL Syntax
====================

1. No-parameter API

    GET_HOSTNAME

Parsed as:

    {
        "action": "GET_HOSTNAME",
        "args": [],
        "raw": "GET_HOSTNAME"
    }


2. Single-parameter API

    FILESYSTEM_CREATE ext4

Parsed as:

    {
        "action": "FILESYSTEM_CREATE",
        "args": ["ext4"],
        "raw": "FILESYSTEM_CREATE ext4"
    }


3. Multiple-parameter API

    PARTITION_CREATE gpt 1 2G

Parsed as:

    {
        "action": "PARTITION_CREATE",
        "args": ["gpt", "1", "2G"],
        "raw": "PARTITION_CREATE gpt 1 2G"
    }


4. Variable-number parameters

    USB_SELECT 1 2 3 4

Parsed as:

    {
        "action": "USB_SELECT",
        "args": ["1", "2", "3", "4"],
        "raw": "USB_SELECT 1 2 3 4"
    }


5. Quoted parameter containing spaces

    STORAGE_MOUNT "/mnt/EmbITE Test"

Parsed as:

    {
        "action": "STORAGE_MOUNT",
        "args": ["/mnt/EmbITE Test"],
        "raw": 'STORAGE_MOUNT "/mnt/EmbITE Test"'
    }


Comments
========

Full-line comments are supported.

Example:

    # Detect USB devices
    USB_DETECT

Blank lines are ignored.


Inline comments
===============

Inline comments are also supported by shlex.

Example:

    USB_SELECT 1 2     # Select PORT1 and PORT2

The comment portion is ignored.


Important Design Principle
==========================

The parser does NOT understand domain-specific APIs.

It does not know whether an action belongs to:

    USB
    Storage
    PCIe
    NVMe
    SATA
    Network
    System
    etc.

It only separates:

    ACTION_NAME

from:

    ARGUMENTS

The mapped Python method decides how many parameters it accepts.


Example Complete `.tst`
=======================

    # Discover USB hardware
    USB_LIST
    USB_DETECT

    # Select physical USB ports
    USB_SELECT 1 2

    # Inspect storage
    STORAGE_INSPECT
    STORAGE_CHECK_MOUNT

    # Create first partition
    PARTITION_CREATE gpt 1 2G
    FILESYSTEM_CREATE ext4

    # Create second partition
    PARTITION_CREATE gpt 2 4G
    FILESYSTEM_CREATE btrfs

    # Mount dynamically
    STORAGE_MOUNT

    # Verify mount state
    STORAGE_CHECK_MOUNT

    # Unmount
    STORAGE_UNMOUNT
"""

import shlex
from pathlib import Path


class TestParser:
    """
    Parser for EmbITE DSL `.tst` files.

    The parser converts every executable DSL line into:

        {
            "action": <DSL action name>,
            "args": <list of parameters>,
            "raw": <original DSL line>
        }

    Example:

        PARTITION_CREATE gpt 1 2G

    becomes:

        {
            "action": "PARTITION_CREATE",
            "args": [
                "gpt",
                "1",
                "2G",
            ],
            "raw": "PARTITION_CREATE gpt 1 2G",
        }
    """

    # ==========================================================
    # PARSE TEST FILE
    # ==========================================================

    def parse(
        self,
        test_file,
    ):
        """
        Parse one EmbITE `.tst` file.

        Parameters:
            test_file:
                Path to the EmbITE test file.

                Example:

                    projects/raspberry_pi5/tests/USB.tst

        Returns:
            List of parsed DSL action dictionaries.

        Example return value:

            [
                {
                    "action": "USB_DETECT",
                    "args": [],
                    "raw": "USB_DETECT",
                },
                {
                    "action": "USB_SELECT",
                    "args": ["1", "2"],
                    "raw": "USB_SELECT 1 2",
                },
                {
                    "action": "PARTITION_CREATE",
                    "args": ["gpt", "1", "2G"],
                    "raw": "PARTITION_CREATE gpt 1 2G",
                },
            ]

        Raises:
            FileNotFoundError:
                If the requested `.tst` file does not exist.

            ValueError:
                If a DSL line contains invalid quoting/syntax.
        """

        test_path = Path(
            test_file
        )

        # ------------------------------------------------------
        # Validate test file
        # ------------------------------------------------------

        if not test_path.exists():

            raise FileNotFoundError(
                f"EmbITE test file not found: {test_path}"
            )

        if not test_path.is_file():

            raise ValueError(
                f"EmbITE test path is not a file: {test_path}"
            )

        actions = []

        # ------------------------------------------------------
        # Read test file line-by-line
        # ------------------------------------------------------

        with test_path.open(
            mode="r",
            encoding="utf-8",
        ) as file:

            for line_number, line in enumerate(
                file,
                start=1,
            ):

                # Remove leading/trailing whitespace.
                raw_line = line.strip()

                # --------------------------------------------------
                # Ignore blank lines
                # --------------------------------------------------

                if not raw_line:
                    continue

                # --------------------------------------------------
                # Ignore full-line comments
                # --------------------------------------------------

                if raw_line.startswith(
                    "#"
                ):
                    continue

                # --------------------------------------------------
                # Parse DSL tokens
                #
                # posix=True provides shell-like behavior:
                #
                #   STORAGE_MOUNT "/mnt/EmbITE Test"
                #
                # becomes:
                #
                #   [
                #       "STORAGE_MOUNT",
                #       "/mnt/EmbITE Test",
                #   ]
                #
                # comments=True allows:
                #
                #   USB_SELECT 1 2 # Select two ports
                #
                # --------------------------------------------------

                lexer = shlex.shlex(
                    raw_line,
                    posix=True,
                )

                lexer.whitespace_split = True

                lexer.commenters = "#"

                try:

                    tokens = list(
                        lexer
                    )

                except ValueError as exc:

                    raise ValueError(
                        "Invalid EmbITE DSL syntax in "
                        f"{test_path} at line {line_number}: "
                        f"{raw_line}\n"
                        f"{exc}"
                    ) from exc

                # An inline comment may result in no remaining
                # executable tokens.
                if not tokens:
                    continue

                # --------------------------------------------------
                # First token is always the action name
                # --------------------------------------------------

                action_name = (
                    tokens[0]
                    .strip()
                    .upper()
                )

                if not action_name:

                    raise ValueError(
                        "Empty EmbITE action name in "
                        f"{test_path} at line {line_number}."
                    )

                # --------------------------------------------------
                # Remaining tokens are parameters
                # --------------------------------------------------

                arguments = tokens[
                    1:
                ]

                # --------------------------------------------------
                # Keep original executable DSL line for logging
                #
                # We remove inline comments from the stored raw value
                # by reconstructing it from parsed tokens.
                #
                # This prevents log output such as:
                #
                #   DSL: USB_SELECT 1 2 # some comment
                #
                # and keeps:
                #
                #   DSL: USB_SELECT 1 2
                # --------------------------------------------------

                clean_raw = (
                    self._format_raw_action(
                        action_name,
                        arguments,
                    )
                )

                # --------------------------------------------------
                # Store parsed action
                # --------------------------------------------------

                actions.append(
                    {
                        "action": action_name,
                        "args": arguments,
                        "raw": clean_raw,
                        "line_number": line_number,
                        "source": str(
                            test_path
                        ),
                    }
                )

        return actions

    # ==========================================================
    # FORMAT RAW ACTION
    # ==========================================================

    @staticmethod
    def _format_raw_action(
        action_name,
        arguments,
    ):
        """
        Reconstruct a clean DSL representation for logging.

        Parameters:
            action_name:
                DSL action name.

            arguments:
                Parsed argument list.

        Example:

            action_name:
                STORAGE_MOUNT

            arguments:
                ["/mnt/EmbITE Test"]

        Result:

            STORAGE_MOUNT '/mnt/EmbITE Test'

        shlex.quote() is used so parameters containing spaces remain
        unambiguous in execution logs.
        """

        if not arguments:
            return action_name

        formatted_arguments = [
            shlex.quote(
                str(argument)
            )
            for argument in arguments
        ]

        return (
            action_name
            + " "
            + " ".join(
                formatted_arguments
            )
        )
