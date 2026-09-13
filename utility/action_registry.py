"""
EmbITE MVP - DSL Action Registry

File:
    utility/action_registry.py

Purpose:
    This module maintains the mapping between EmbITE DSL action names
    and the Python functions that implement those actions.

    The ActionRegistry acts as the central lookup table used by the
    TestExecutor.

Architecture:

    .tst File
        ↓
    TestParser
        ↓
    Parsed DSL Action
        ↓
    TestExecutor
        ↓
    ActionRegistry
        ↓
    Python Function
        ↓
    BoardActions / USB / Storage / PCIe / NVMe / etc.


Example:

    DSL:

        GET_HOSTNAME

    Registry mapping:

        "GET_HOSTNAME"
            ↓
        board_actions.get_hostname


Dynamic domain registration:

    USB_LIST
        ↓
    usb.list_devices

    USB_DETECT
        ↓
    usb.detect_ports

    USB_SELECT
        ↓
    usb.select_ports

    PARTITION_CREATE
        ↓
    storage.create_partition


Design Principle:
    ActionRegistry should remain domain-independent.

    It should NOT contain hard-coded knowledge about:

        USB
        Storage
        PCIe
        NVMe
        SATA
        Network
        CPU
        Memory
        etc.

    Only the basic system-level APIs are registered during
    initialization because they are directly provided by BoardActions.

    All additional domain APIs are registered dynamically from:

        src/embite.py


Example registration:

    action_registry.register(
        "USB_LIST",
        usb.list_devices,
    )

    action_registry.register(
        "PARTITION_CREATE",
        storage.create_partition,
    )


Benefits:
    - Reusable
    - Easy to extend
    - No domain coupling
    - No large if/elif action dispatcher
    - Supports parameterized DSL APIs
    - Supports future EmbITE libraries without changing this file
"""


class ActionRegistry:
    """
    Registry for EmbITE DSL actions.

    Parameters:
        board_actions:
            BoardActions instance.

            BoardActions provides the core system-level APIs such as:

                GET_HOSTNAME
                GET_IP_ADDRESS
                GET_OS
                GET_KERNEL
                GET_ARCHITECTURE
                GET_MEMORY

    Additional domain APIs are registered later using:

        register(action_name, callable)
    """

    def __init__(
        self,
        board_actions,
    ):
        """
        Initialize the action registry.

        System-level DSL APIs are registered immediately.

        Domain-specific APIs such as USB and Storage are registered
        dynamically later from src/embite.py.
        """

        self.board_actions = (
            board_actions
        )

        # ======================================================
        # ACTION LOOKUP TABLE
        # ======================================================
        #
        # Key:
        #     EmbITE DSL action name
        #
        # Value:
        #     Python callable that implements the action
        #
        # Example:
        #
        #     "GET_HOSTNAME":
        #         self.board_actions.get_hostname
        #
        self.actions = {

            # --------------------------------------------------
            # SYSTEM INFORMATION DSL APIs
            # --------------------------------------------------

            "GET_HOSTNAME":
                self.board_actions.get_hostname,

            "GET_IP_ADDRESS":
                self.board_actions.get_ip_address,

            "GET_OS":
                self.board_actions.get_os,

            "GET_KERNEL":
                self.board_actions.get_kernel,

            "GET_ARCHITECTURE":
                self.board_actions.get_architecture,

            "GET_MEMORY":
                self.board_actions.get_memory,
        }

    # ==========================================================
    # REGISTER ACTION
    # ==========================================================

    def register(
        self,
        action_name,
        action,
    ):
        """
        Register a new EmbITE DSL action.

        Parameters:
            action_name:
                DSL action name.

                Example:

                    USB_LIST
                    USB_DETECT
                    USB_SELECT
                    STORAGE_INSPECT
                    PARTITION_CREATE
                    FILESYSTEM_CREATE

            action:
                Python callable implementing the DSL action.

        Example:

            action_registry.register(
                "USB_LIST",
                usb.list_devices,
            )

        Parameterized DSL APIs work automatically.

        Example:

            DSL:

                PARTITION_CREATE gpt 1 2G

            Registry:

                "PARTITION_CREATE"
                    ↓
                storage.create_partition

            Executor later calls:

                storage.create_partition(
                    "gpt",
                    "1",
                    "2G",
                )

        The registry itself does not need to understand the parameters.
        """

        # ------------------------------------------------------
        # Validate action name
        # ------------------------------------------------------

        if not action_name:

            raise ValueError(
                "Action name cannot be empty."
            )

        if not isinstance(
            action_name,
            str,
        ):

            raise TypeError(
                "Action name must be a string."
            )

        # Normalize DSL action names.
        #
        # Example:
        #
        #   usb_list
        #
        # becomes:
        #
        #   USB_LIST
        #
        normalized_name = (
            action_name
            .strip()
            .upper()
        )

        if not normalized_name:

            raise ValueError(
                "Action name cannot be empty."
            )

        # ------------------------------------------------------
        # Validate action callable
        # ------------------------------------------------------

        if not callable(
            action
        ):

            raise ValueError(
                f"Action '{normalized_name}' "
                "is not callable."
            )

        # ------------------------------------------------------
        # Register / replace mapping
        # ------------------------------------------------------
        #
        # During development it is useful to allow replacement.
        #
        # Example:
        #
        # register("USB_LIST", old_function)
        # register("USB_LIST", new_function)
        #
        # The latest registered function becomes active.
        #
        self.actions[
            normalized_name
        ] = action

    # ==========================================================
    # GET ACTION
    # ==========================================================

    def get_action(
        self,
        action_name,
    ):
        """
        Resolve an EmbITE DSL action into its Python callable.

        Parameters:
            action_name:
                DSL action name parsed from the .tst file.

        Returns:
            Callable associated with the DSL action.

        Example:

            action = registry.get_action(
                "USB_DETECT"
            )

            result = action()

        Parameterized example:

            action = registry.get_action(
                "PARTITION_CREATE"
            )

            result = action(
                "gpt",
                "1",
                "2G",
            )

        Raises:
            ValueError:
                If the DSL action has not been registered.
        """

        if not action_name:

            raise ValueError(
                "Action name cannot be empty."
            )

        normalized_name = (
            str(
                action_name
            )
            .strip()
            .upper()
        )

        action = self.actions.get(
            normalized_name
        )

        if action is None:

            raise ValueError(
                "Unsupported EmbITE action: "
                f"{normalized_name}"
            )

        return action

    # ==========================================================
    # CHECK ACTION
    # ==========================================================

    def has_action(
        self,
        action_name,
    ):
        """
        Check whether an action is currently registered.

        Parameters:
            action_name:
                EmbITE DSL action name.

        Returns:
            True:
                Action exists.

            False:
                Action is not registered.

        Example:

            if registry.has_action(
                "USB_LIST"
            ):
                ...
        """

        if not action_name:
            return False

        normalized_name = (
            str(
                action_name
            )
            .strip()
            .upper()
        )

        return (
            normalized_name
            in self.actions
        )

    # ==========================================================
    # LIST ACTIONS
    # ==========================================================

    def list_actions(self):
        """
        Return all currently registered DSL action names.

        Returns:
            Sorted list of DSL names.

        Example result:

            [
                "FILESYSTEM_CREATE",
                "FILESYSTEM_DETECT",
                "GET_ARCHITECTURE",
                "GET_HOSTNAME",
                "GET_IP_ADDRESS",
                "GET_KERNEL",
                "GET_MEMORY",
                "GET_OS",
                "PARTITION_CREATE",
                "PARTITION_LIST",
                "STORAGE_CHECK_MOUNT",
                "STORAGE_INSPECT",
                "STORAGE_MOUNT",
                "STORAGE_UNMOUNT",
                "USB_DETECT",
                "USB_LIST",
                "USB_SELECT",
            ]

        This can later be useful for:

            - CLI help
            - DSL documentation generation
            - Debugging
            - UI API catalogs
            - Validation of .tst files
        """

        return sorted(
            self.actions.keys()
        )
