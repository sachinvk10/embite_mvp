"""
EmbITE MVP - DSL Test Executor

File:
    utility/executor.py

Purpose:
    This module executes parsed EmbITE DSL actions.

    It receives parsed DSL entries from:

        utility/parser.py

    resolves each DSL action through:

        utility/action_registry.py

    and invokes the mapped Python callable.

Execution Flow:

    .tst File
        ↓
    TestParser
        ↓
    Parsed Action
        ↓
    TestExecutor
        ↓
    ActionRegistry
        ↓
    Python API Function
        ↓
    Result:
        PASS
        FAIL
        BLOCKED


Parameterized DSL
=================

The executor supports APIs with zero, one, or many parameters.

Example:

    GET_HOSTNAME

Parsed as:

    {
        "action": "GET_HOSTNAME",
        "args": [],
        "raw": "GET_HOSTNAME"
    }

The executor calls:

    action()


Example:

    USB_SELECT 1 2 3

Parsed as:

    {
        "action": "USB_SELECT",
        "args": ["1", "2", "3"],
        "raw": "USB_SELECT 1 2 3"
    }

The executor calls:

    action(
        "1",
        "2",
        "3",
    )


Example:

    PARTITION_CREATE gpt 1 2G

The executor calls:

    storage.create_partition(
        "gpt",
        "1",
        "2G",
    )


Result Status
=============

PASS
    The API completed successfully.

FAIL
    The API failed due to an execution or runtime error.

BLOCKED
    The API was intentionally prevented by an EmbITE safety rule.

    Examples:
        - existing data detected
        - allow_overwrite=false
        - selected USB port has no storage device
        - USB device changed after selection
        - ambiguous storage selection
        - destructive prerequisite not satisfied


Safety Halt
===========

When a BlockedActionError occurs, the executor stops executing the
remaining DSL actions from that batch.

Example:

    PARTITION_CREATE gpt 1 2G
    FILESYSTEM_CREATE ext4
    STORAGE_MOUNT

If PARTITION_CREATE is BLOCKED because existing data is protected:

    PARTITION_CREATE -> BLOCKED

then:

    FILESYSTEM_CREATE
    STORAGE_MOUNT

must not execute.

This prevents dependent operations from running after a safety condition.
"""

from utility.exceptions import BlockedActionError


class TestExecutor:
    """
    Generic EmbITE DSL executor.

    Parameters:
        action_registry:
            ActionRegistry instance used to resolve DSL action names
            into Python callables.

    The executor is domain-independent.

    It does not know whether an action belongs to:

        System
        USB
        Storage
        PCIe
        NVMe
        SATA
        Network
        etc.

    It simply:

        1. resolves the action
        2. passes arguments
        3. captures the result
        4. converts exceptions into framework statuses
    """

    def __init__(
        self,
        action_registry,
    ):
        """
        Initialize TestExecutor.

        Parameters:
            action_registry:
                EmbITE ActionRegistry instance.
        """

        self.action_registry = (
            action_registry
        )

    # ==========================================================
    # EXECUTE
    # ==========================================================

    def execute(
        self,
        actions,
    ):
        """
        Execute a list of parsed DSL actions.

        Parameters:
            actions:
                List returned by TestParser.

        Expected format:

            [
                {
                    "action": "USB_DETECT",
                    "args": [],
                    "raw": "USB_DETECT"
                },
                {
                    "action": "USB_SELECT",
                    "args": ["1", "2"],
                    "raw": "USB_SELECT 1 2"
                },
                {
                    "action": "PARTITION_CREATE",
                    "args": ["gpt", "1", "2G"],
                    "raw": "PARTITION_CREATE gpt 1 2G"
                }
            ]

        Returns:
            List of execution result dictionaries.

        Example:

            [
                {
                    "action": "USB_DETECT",
                    "raw": "USB_DETECT",
                    "status": "PASS",
                    "result": "..."
                },
                {
                    "action": "PARTITION_CREATE",
                    "raw": "PARTITION_CREATE gpt 1 2G",
                    "status": "BLOCKED",
                    "error": "Existing storage content detected."
                }
            ]

        Execution Rules:
            - PASS:
                Continue to next action.

            - FAIL:
                Record failure and continue.

            - BLOCKED:
                Record safety block and stop remaining actions.
        """

        results = []

        for action_data in actions:

            # ==================================================
            # NORMALIZE PARSED ACTION
            # ==================================================

            action_name = action_data.get(
                "action"
            )

            args = action_data.get(
                "args",
                [],
            )

            raw = action_data.get(
                "raw",
                action_name,
            )

            if not action_name:

                results.append(
                    {
                        "action": "",
                        "raw": raw,
                        "status": "FAIL",
                        "error": (
                            "Parsed DSL entry does not contain "
                            "an action name."
                        ),
                    }
                )

                continue

            # ==================================================
            # EXECUTE ACTION
            # ==================================================

            try:

                # ----------------------------------------------
                # Resolve DSL action from registry
                # ----------------------------------------------

                action = (
                    self.action_registry
                    .get_action(
                        action_name
                    )
                )

                # ----------------------------------------------
                # Invoke mapped function with variable arguments
                #
                # Examples:
                #
                # GET_HOSTNAME
                #     -> action()
                #
                # USB_SELECT 1 2
                #     -> action("1", "2")
                #
                # PARTITION_CREATE gpt 1 2G
                #     -> action("gpt", "1", "2G")
                # ----------------------------------------------

                output = action(
                    *args
                )

                # ----------------------------------------------
                # PASS
                # ----------------------------------------------

                results.append(
                    {
                        "action": action_name,
                        "raw": raw,
                        "status": "PASS",
                        "result": output,
                    }
                )

            # ==================================================
            # BLOCKED
            # ==================================================

            except BlockedActionError as exc:

                results.append(
                    {
                        "action": action_name,
                        "raw": raw,
                        "status": "BLOCKED",
                        "error": str(
                            exc
                        ),
                    }
                )

                # ----------------------------------------------
                # Safety rule:
                #
                # A BLOCKED action means subsequent dependent
                # actions must not execute.
                #
                # Example:
                #
                # PARTITION_CREATE -> BLOCKED
                #
                # Do not continue into:
                #
                # FILESYSTEM_CREATE
                # STORAGE_MOUNT
                # FILE_WRITE
                # ----------------------------------------------

                break

            # ==================================================
            # FAIL
            # ==================================================

            except Exception as exc:

                results.append(
                    {
                        "action": action_name,
                        "raw": raw,
                        "status": "FAIL",
                        "error": str(
                            exc
                        ),
                    }
                )

                # A normal FAIL does not automatically stop the
                # executor in the current MVP.
                #
                # This allows independent validation actions to
                # continue.
                #
                # Safety-sensitive operations should raise
                # BlockedActionError instead.

        return results
