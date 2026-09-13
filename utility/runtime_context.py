"""
EmbITE MVP - Runtime Context

File:
    utility/runtime_context.py

Purpose:
    RuntimeContext provides temporary in-memory state shared between
    EmbITE DSL APIs during one complete test execution.

Why It Is Needed
================

Many EmbITE operations are dynamic.

Example:

    USB_DETECT
        ↓
    discovers actual USB topology and block nodes

    USB_SELECT 1 2
        ↓
    selects PORT1 and PORT2

    RuntimeContext stores:

        PORT1 -> /dev/sda
        PORT2 -> /dev/sdc

    PARTITION_CREATE gpt 1 2G
        ↓
    Linux creates partitions dynamically

    RuntimeContext updates:

        PORT1 -> /dev/sda1
        PORT2 -> /dev/sdc1

    FILESYSTEM_CREATE ext4
        ↓
    uses the partition nodes already stored in RuntimeContext

    STORAGE_MOUNT
        ↓
    generates and stores mountpoints dynamically


This avoids hard-coding values such as:

    /dev/sda
    /dev/sdb
    /dev/sda1
    /mnt/test


Runtime Lifetime
================

RuntimeContext exists only for the current EmbITE execution.

It is:

    - created once in src/embite.py
    - shared with USB and Storage libraries
    - updated during DSL execution
    - discarded when the EmbITE process ends

It does NOT persist data across runs.


Architecture
============

    src/embite.py
          ↓
    RuntimeContext
      ┌──────┴────────┐
      ↓               ↓
    USB Library    Storage Library
      ↓               ↓
    USB_DETECT     PARTITION_CREATE
    USB_SELECT     FILESYSTEM_CREATE
                   STORAGE_MOUNT


Typical Keys
============

USB inventory:

    usb.devices

USB topology:

    usb.ports

Selected ports:

    usb.selected_ports

Storage targets:

    storage.targets


Example:

    storage.targets = [
        {
            "port": 1,
            "usb_path": "3-1",
            "device_node": "/dev/sda",
            "transport": "usb",
            "vendor": "Sony",
            "model": "Storage Media",
            "serial": "...",
            "size": "7.2G",

            "partitions": {
                1: {
                    "node": "/dev/sda1",
                    "filesystem": "ext4",
                    "mount_point":
                        "/mnt/embite/PORT1/partition1/mountpoint1"
                }
            },

            "active_partition": 1
        }
    ]


Design Principle
================

RuntimeContext is intentionally domain-independent.

It does not know anything about:

    USB
    Storage
    PCIe
    NVMe
    SATA
    Network
    CPU
    etc.

It simply stores values by key.

Future modules can use the same context without modifying this file.
"""


class RuntimeContext:
    """
    Shared temporary runtime-state container for EmbITE.

    Example:

        context = RuntimeContext()

        context.set(
            "storage.device_node",
            "/dev/sda"
        )

        node = context.get(
            "storage.device_node"
        )

    The internal structure is a normal Python dictionary.
    """

    def __init__(self):
        """
        Create an empty RuntimeContext.

        State exists only for the current process/run.
        """

        self._data = {}

    # ==========================================================
    # SET
    # ==========================================================

    def set(
        self,
        key,
        value,
    ):
        """
        Store or replace a runtime value.

        Parameters:
            key:
                String key.

                Examples:

                    usb.devices
                    usb.ports
                    usb.selected_ports
                    storage.targets

            value:
                Any Python object.

                Common values include:

                    string
                    integer
                    boolean
                    list
                    dictionary

        Example:

            context.set(
                "usb.selected_ports",
                [1, 2]
            )

        Existing keys are replaced.
        """

        if not key:

            raise ValueError(
                "RuntimeContext key cannot be empty."
            )

        self._data[
            str(key)
        ] = value

    # ==========================================================
    # GET
    # ==========================================================

    def get(
        self,
        key,
        default=None,
    ):
        """
        Retrieve a runtime value.

        Parameters:
            key:
                RuntimeContext key.

            default:
                Value returned when the key does not exist.

                Default:
                    None

        Example:

            targets = context.get(
                "storage.targets",
                []
            )

        Returns:
            Stored value or default.
        """

        if not key:
            return default

        return self._data.get(
            str(key),
            default,
        )

    # ==========================================================
    # REQUIRE
    # ==========================================================

    def require(
        self,
        key,
    ):
        """
        Retrieve a required runtime value.

        Raises RuntimeError if the key does not exist
        or its value is None.

        Example:

            ports = context.require(
                "usb.ports"
            )

        This is useful when one DSL API depends on the successful
        completion of an earlier DSL API.

        Example:

            USB_SELECT requires USB_DETECT first.
        """

        if not key:

            raise ValueError(
                "RuntimeContext key cannot be empty."
            )

        normalized_key = str(
            key
        )

        if normalized_key not in self._data:

            raise RuntimeError(
                "Required runtime value is not available: "
                f"{normalized_key}"
            )

        value = self._data[
            normalized_key
        ]

        if value is None:

            raise RuntimeError(
                "Required runtime value is not available: "
                f"{normalized_key}"
            )

        return value

    # ==========================================================
    # HAS
    # ==========================================================

    def has(
        self,
        key,
    ):
        """
        Check whether a runtime key exists.

        Example:

            if context.has(
                "usb.ports"
            ):
                ...

        Returns:
            True if key exists.
            False otherwise.
        """

        if not key:
            return False

        return (
            str(key)
            in self._data
        )

    # ==========================================================
    # REMOVE
    # ==========================================================

    def remove(
        self,
        key,
    ):
        """
        Remove one runtime key.

        Missing keys are ignored.

        Example:

            context.remove(
                "storage.targets"
            )

        Useful when a new discovery invalidates old state.
        """

        if not key:
            return

        self._data.pop(
            str(key),
            None,
        )

    # ==========================================================
    # CLEAR
    # ==========================================================

    def clear(self):
        """
        Remove all runtime state.

        Example:

            context.clear()

        Normally this is not required because one RuntimeContext
        is created per EmbITE execution.

        It may be useful later for:
            - rerun support
            - interactive execution
            - UI-triggered resets
        """

        self._data.clear()

    # ==========================================================
    # UPDATE
    # ==========================================================

    def update(
        self,
        values,
    ):
        """
        Update multiple runtime values at once.

        Parameters:
            values:
                Dictionary of key/value pairs.

        Example:

            context.update(
                {
                    "storage.device_node": "/dev/sda",
                    "storage.transport": "usb",
                    "storage.serial": "ABC123",
                }
            )
        """

        if not isinstance(
            values,
            dict,
        ):

            raise TypeError(
                "RuntimeContext.update() requires a dictionary."
            )

        for key, value in values.items():

            self.set(
                key,
                value,
            )

    # ==========================================================
    # SNAPSHOT
    # ==========================================================

    def snapshot(self):
        """
        Return a shallow copy of the current runtime state.

        Useful for:
            - debugging
            - reporting
            - future UI visualization
            - diagnostics

        Example:

            state = context.snapshot()

        Modifying the returned top-level dictionary does not change
        RuntimeContext directly.

        Note:
            Nested lists/dictionaries are not deep-copied.
        """

        return dict(
            self._data
        )

    # ==========================================================
    # KEYS
    # ==========================================================

    def keys(self):
        """
        Return currently stored runtime keys.

        Example:

            [
                "usb.devices",
                "usb.ports",
                "usb.selected_ports",
                "storage.targets",
            ]
        """

        return list(
            self._data.keys()
        )

    # ==========================================================
    # REPRESENTATION
    # ==========================================================

    def __repr__(self):
        """
        Developer-friendly representation.

        Sensitive information such as DUT passwords should never
        be stored in RuntimeContext.

        Example:

            RuntimeContext(
                keys=[
                    'usb.ports',
                    'storage.targets'
                ]
            )
        """

        return (
            "RuntimeContext("
            f"keys={list(self._data.keys())}"
            ")"
        )
