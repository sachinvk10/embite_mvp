"""
EmbITE MVP - Storage Validation Library

File:
    lib/storage.py

Purpose:
    Provides reusable storage validation and management APIs for
    storage devices selected through EmbITE USB APIs.

Supported DSL APIs:
    STORAGE_INSPECT
    STORAGE_CHECK_MOUNT
    STORAGE_UNMOUNT
    STORAGE_MOUNT
    PARTITION_LIST
    PARTITION_CREATE <table> <number> <size>
    FILESYSTEM_DETECT
    FILESYSTEM_CREATE <filesystem>

Key design principles:
    - Device nodes are dynamically discovered.
    - Partition nodes are dynamically discovered.
    - Storage operations are limited to USB_SELECT targets.
    - Destructive operations require allow_overwrite=true.
    - Multi-device destructive operations are preflight checked.
    - Administrative utilities use an explicit PATH.
    - Privileged command success is based on exit code, not stderr.
    - blkid/parted read-only probes can execute through sudo.
"""

import math
import re
import shlex

from utility.exceptions import BlockedActionError


class Storage:
    """
    EmbITE storage validation and management interface.
    """

    DEFAULT_MOUNT_ROOT = "/mnt/embite"

    SYSTEM_PATH = (
        "/usr/local/sbin:"
        "/usr/local/bin:"
        "/usr/sbin:"
        "/usr/bin:"
        "/sbin:"
        "/bin"
    )

    def __init__(
        self,
        board_actions,
        runtime_context,
        storage_config=None,
    ):
        self.board = board_actions
        self.context = runtime_context

        self.config = (
            storage_config
            or {}
        )

        self.safety_config = (
            self.config.get(
                "safety",
                {},
            )
            or {}
        )

    # ==========================================================
    # STORAGE_INSPECT
    # ==========================================================

    def inspect(self):
        """
        DSL:
            STORAGE_INSPECT

        Read-only inspection of selected storage targets.
        """

        targets = self._selected_targets()

        lines = [
            "[STORAGE INSPECTION]"
        ]

        for target in targets:

            self._validate_target_ownership(
                target
            )

            state = self._inspect_target_state(
                target
            )

            if len(lines) > 1:
                lines.append("")

            lines.extend(
                [
                    f"[PORT{target['port']}]",
                    (
                        "USB Path          : "
                        f"{target.get('usb_path') or 'N/A'}"
                    ),
                    (
                        "Node              : "
                        f"{target.get('device_node') or 'N/A'}"
                    ),
                    (
                        "Transport         : "
                        f"{state.get('transport') or 'N/A'}"
                    ),
                    (
                        "Vendor            : "
                        f"{state.get('vendor') or 'N/A'}"
                    ),
                    (
                        "Model             : "
                        f"{state.get('model') or 'N/A'}"
                    ),
                    (
                        "Serial            : "
                        f"{state.get('serial') or 'N/A'}"
                    ),
                    (
                        "Size              : "
                        f"{state.get('size') or 'N/A'}"
                    ),
                    (
                        "Partition Table   : "
                        f"{state.get('partition_table') or 'None'}"
                    ),
                    (
                        "Partitions        : "
                        f"{len(state.get('partitions', []))}"
                    ),
                    (
                        "Filesystem        : "
                        f"{'YES' if state.get('has_filesystem') else 'NO'}"
                    ),
                    (
                        "Mounted           : "
                        f"{'YES' if state.get('mounted') else 'NO'}"
                    ),
                    (
                        "Existing Content  : "
                        f"{'YES' if state.get('existing_content') else 'NO'}"
                    ),
                    (
                        "Allow Overwrite   : "
                        f"{self._allow_overwrite()}"
                    ),
                ]
            )

            partitions = state.get(
                "partitions",
                [],
            )

            if partitions:

                lines.append(
                    "[PARTITIONS]"
                )

                for partition in partitions:

                    lines.append(
                        " | ".join(
                            [
                                (
                                    "Partition="
                                    f"{partition.get('number')}"
                                ),
                                (
                                    "Node="
                                    f"{partition.get('node')}"
                                ),
                                (
                                    "Size="
                                    f"{partition.get('size') or 'N/A'}"
                                ),
                                (
                                    "Filesystem="
                                    f"{partition.get('filesystem') or 'None'}"
                                ),
                                (
                                    "Mountpoint="
                                    f"{partition.get('mount_point') or 'None'}"
                                ),
                            ]
                        )
                    )

            if (
                state.get(
                    "existing_content"
                )
                and
                not self._allow_overwrite()
            ):

                lines.extend(
                    [
                        "[SAFETY]",
                        (
                            "Device contains existing "
                            "storage content."
                        ),
                        (
                            "Destructive storage operations "
                            "will be BLOCKED."
                        ),
                    ]
                )

        self._save_targets(
            targets
        )

        return "\n".join(
            lines
        )

    # ==========================================================
    # STORAGE_CHECK_MOUNT
    # ==========================================================

    def check_mount(self):
        """
        DSL:
            STORAGE_CHECK_MOUNT
        """

        targets = self._selected_targets()

        lines = [
            "[STORAGE MOUNT STATUS]"
        ]

        for target in targets:

            self._validate_target_ownership(
                target
            )

            rows = self._lsblk_rows(
                target[
                    "device_node"
                ]
            )

            if len(lines) > 1:
                lines.append("")

            lines.append(
                f"[PORT{target['port']}]"
            )

            found = False

            for row in rows:

                node = row.get(
                    "NAME"
                )

                if not node:
                    continue

                mountpoints = (
                    self._get_mountpoints(
                        node
                    )
                )

                if not mountpoints:
                    continue

                found = True

                filesystem = (
                    row.get(
                        "FSTYPE"
                    )
                    or
                    self._probe_filesystem(
                        node
                    )
                )

                for mountpoint in mountpoints:

                    lines.extend(
                        [
                            f"Node       : {node}",
                            (
                                "Filesystem : "
                                f"{filesystem or 'N/A'}"
                            ),
                            "Mounted    : YES",
                            (
                                "Mountpoint : "
                                f"{mountpoint}"
                            ),
                        ]
                    )

            if not found:

                lines.append(
                    "Mounted : NO"
                )

            self._refresh_target_partitions(
                target
            )

        self._save_targets(
            targets
        )

        return "\n".join(
            lines
        )

    # ==========================================================
    # STORAGE_UNMOUNT
    # ==========================================================

    def unmount(self):
        """
        DSL:
            STORAGE_UNMOUNT
        """

        targets = self._selected_targets()

        # Validate the entire selection first.
        for target in targets:

            self._validate_target_ownership(
                target
            )

        lines = [
            "[STORAGE UNMOUNT]"
        ]

        any_unmounted = False

        for target in targets:

            results = self._unmount_target(
                target
            )

            if len(lines) > 1:
                lines.append("")

            lines.append(
                f"[PORT{target['port']}]"
            )

            if not results:

                lines.append(
                    "No mounted filesystem detected."
                )

                continue

            any_unmounted = True

            lines.extend(
                results
            )

            self._refresh_target_partitions(
                target
            )

        self._save_targets(
            targets
        )

        if not any_unmounted:

            lines.append(
                "No selected storage device "
                "required unmounting."
            )

        return "\n".join(
            lines
        )

    # ==========================================================
    # STORAGE_MOUNT
    # ==========================================================

    def mount(
        self,
        mount_root=None,
    ):
        """
        DSL:
            STORAGE_MOUNT

        Optional:
            STORAGE_MOUNT /mnt/custom_root

        Default layout:

            /mnt/embite/
                PORT1/
                    partition1/
                        mountpoint1/
                    partition2/
                        mountpoint2/
        """

        targets = self._selected_targets()

        if mount_root:

            root = str(
                mount_root
            ).rstrip("/")

        else:

            root = self.DEFAULT_MOUNT_ROOT

        if not root.startswith(
            "/"
        ):

            raise ValueError(
                "STORAGE_MOUNT requires "
                "an absolute mount path."
            )

        for target in targets:

            self._validate_target_ownership(
                target
            )

        lines = [
            "[STORAGE MOUNT]"
        ]

        mountable_count = 0

        for target in targets:

            self._refresh_target_partitions(
                target
            )

            partitions = target.get(
                "partitions",
                {},
            )

            if len(lines) > 1:
                lines.append("")

            lines.append(
                f"[PORT{target['port']}]"
            )

            if not partitions:

                lines.append(
                    "No partitions detected."
                )

                continue

            for number in sorted(
                partitions
            ):

                partition = partitions[
                    number
                ]

                node = partition.get(
                    "node"
                )

                filesystem = (
                    partition.get(
                        "filesystem"
                    )
                    or
                    self._probe_filesystem(
                        node
                    )
                )

                if not filesystem:

                    lines.extend(
                        [
                            f"Partition  : {number}",
                            f"Node       : {node}",
                            "Status     : SKIPPED",
                            (
                                "Reason     : "
                                "No filesystem detected"
                            ),
                        ]
                    )

                    continue

                mountable_count += 1

                existing_mounts = (
                    self._get_mountpoints(
                        node
                    )
                )

                # Existing mount: record, don't remount.
                if existing_mounts:

                    mountpoint = (
                        existing_mounts[
                            0
                        ]
                    )

                    partition[
                        "mount_point"
                    ] = mountpoint

                    partition[
                        "mount_source"
                    ] = "EXISTING"

                    lines.extend(
                        [
                            f"Partition  : {number}",
                            f"Node       : {node}",
                            (
                                "Filesystem : "
                                f"{filesystem}"
                            ),
                            "Mounted    : YES",
                            (
                                "Mountpoint : "
                                f"{mountpoint}"
                            ),
                            "Source     : EXISTING",
                        ]
                    )

                    continue

                mountpoint = (
                    f"{root}/"
                    f"PORT{target['port']}/"
                    f"partition{number}/"
                    f"mountpoint{number}"
                )

                self._run_privileged_checked(
                    (
                        "mkdir -p -- "
                        + shlex.quote(
                            mountpoint
                        )
                    ),
                    (
                        "Unable to create mountpoint "
                        f"{mountpoint}"
                    ),
                )

                self._run_privileged_checked(
                    (
                        "mount -- "
                        + shlex.quote(
                            node
                        )
                        + " "
                        + shlex.quote(
                            mountpoint
                        )
                    ),
                    (
                        "Unable to mount "
                        f"{node}"
                    ),
                )

                actual_mounts = (
                    self._get_mountpoints(
                        node
                    )
                )

                if (
                    mountpoint
                    not in actual_mounts
                ):

                    raise RuntimeError(
                        "STORAGE_MOUNT verification failed: "
                        f"{node} is not mounted at "
                        f"{mountpoint}"
                    )

                partition[
                    "filesystem"
                ] = filesystem

                partition[
                    "mount_point"
                ] = mountpoint

                partition[
                    "mount_source"
                ] = "EMBITE"

                lines.extend(
                    [
                        f"Partition  : {number}",
                        f"Node       : {node}",
                        (
                            "Filesystem : "
                            f"{filesystem}"
                        ),
                        "Mounted    : YES",
                        (
                            "Mountpoint : "
                            f"{mountpoint}"
                        ),
                        "Source     : EMBITE",
                    ]
                )

        self._save_targets(
            targets
        )

        if mountable_count == 0:

            raise BlockedActionError(
                "STORAGE_MOUNT found no partition "
                "with a mountable filesystem."
            )

        return "\n".join(
            lines
        )

    # ==========================================================
    # PARTITION_LIST
    # ==========================================================

    def list_partitions(self):
        """
        DSL:
            PARTITION_LIST
        """

        targets = self._selected_targets()

        lines = [
            "[PARTITION LIST]"
        ]

        for target in targets:

            self._validate_target_ownership(
                target
            )

            self._refresh_target_partitions(
                target
            )

            partitions = target.get(
                "partitions",
                {},
            )

            if len(lines) > 1:
                lines.append("")

            lines.append(
                f"[PORT{target['port']}]"
            )

            lines.append(
                "Device : "
                + target[
                    "device_node"
                ]
            )

            if not partitions:

                lines.append(
                    "Partitions : None"
                )

                continue

            for number in sorted(
                partitions
            ):

                partition = partitions[
                    number
                ]

                lines.extend(
                    [
                        (
                            f"Partition  : {number}"
                        ),
                        (
                            "Node       : "
                            f"{partition.get('node')}"
                        ),
                        (
                            "Size       : "
                            f"{partition.get('size') or 'N/A'}"
                        ),
                        (
                            "Filesystem : "
                            f"{partition.get('filesystem') or 'None'}"
                        ),
                        (
                            "Mountpoint : "
                            f"{partition.get('mount_point') or 'None'}"
                        ),
                    ]
                )

        self._save_targets(
            targets
        )

        return "\n".join(
            lines
        )

    # ==========================================================
    # PARTITION_CREATE
    # ==========================================================

    def create_partition(
        self,
        table,
        number,
        size,
    ):
        """
        DSL:
            PARTITION_CREATE <table> <number> <size>

        Examples:
            PARTITION_CREATE gpt 1 2G
            PARTITION_CREATE gpt 2 1G
            PARTITION_CREATE gpt 3 remaining
        """

        targets = self._selected_targets()

        table = (
            self._normalize_partition_table(
                table
            )
        )

        try:

            partition_number = int(
                number
            )

        except (
            TypeError,
            ValueError,
        ) as exc:

            raise ValueError(
                "Partition number must "
                "be an integer."
            ) from exc

        if partition_number <= 0:

            raise ValueError(
                "Partition number must "
                "be greater than zero."
            )

        size_value = str(
            size
        ).strip()

        if not size_value:

            raise ValueError(
                "Partition size cannot be empty."
            )

        if size_value.lower() not in (
            "remaining",
            "rest",
            "all",
            "100%",
        ):

            self._size_to_mib(
                size_value
            )

        self._require_command(
            "parted"
        )

        self._require_command(
            "partprobe"
        )

        # ======================================================
        # PREFLIGHT ALL TARGETS
        # ======================================================

        preflight = []
        problems = []

        for target in targets:

            try:

                self._validate_target_ownership(
                    target
                )

                state = (
                    self._inspect_target_state(
                        target
                    )
                )

                prepared = bool(
                    target.get(
                        "prepared_by_embite",
                        False,
                    )
                )

                if not prepared:

                    if (
                        state.get(
                            "existing_content"
                        )
                        and
                        not self._allow_overwrite()
                    ):

                        raise BlockedActionError(
                            f"PORT{target['port']} "
                            f"({target['device_node']}) "
                            "contains existing storage content."
                        )

                    expected_number = 1

                else:

                    existing_numbers = sorted(
                        target.get(
                            "partitions",
                            {},
                        )
                    )

                    expected_number = (
                        self._next_partition_number(
                            existing_numbers
                        )
                    )

                    prepared_table = (
                        target.get(
                            "partition_table"
                        )
                    )

                    if (
                        prepared_table
                        and
                        prepared_table != table
                    ):

                        raise BlockedActionError(
                            f"PORT{target['port']} "
                            "was already prepared with "
                            f"partition table "
                            f"{prepared_table}. "
                            f"Requested table is {table}."
                        )

                if (
                    partition_number
                    != expected_number
                ):

                    raise BlockedActionError(
                        f"PORT{target['port']} expects "
                        f"partition number "
                        f"{expected_number}, "
                        f"but DSL requested "
                        f"{partition_number}. "
                        "EmbITE will not guess or overwrite "
                        "partition numbering."
                    )

                preflight.append(
                    {
                        "target": target,
                        "state": state,
                        "prepared": prepared,
                    }
                )

            except Exception as exc:

                problems.append(
                    f"PORT{target.get('port')} -> {exc}"
                )

        if problems:

            raise BlockedActionError(
                "PARTITION_CREATE preflight failed. "
                "No selected storage device was modified.\n"
                + "\n".join(
                    problems
                )
            )

        # ======================================================
        # EXECUTION
        # ======================================================

        results = []

        for item in preflight:

            target = item[
                "target"
            ]

            state = item[
                "state"
            ]

            prepared = item[
                "prepared"
            ]

            device = target[
                "device_node"
            ]

            # --------------------------------------------------
            # Initial preparation occurs only for partition 1.
            # --------------------------------------------------

            if not prepared:

                if (
                    state.get(
                        "mounted"
                    )
                    and
                    self._allow_overwrite()
                ):

                    self._sync()

                    self._unmount_target(
                        target
                    )

                    self._verify_target_unmounted(
                        target
                    )

                # --------------------------------------------------
                # Remove old filesystem/partition signatures.
                #
                # Child partitions are wiped first so residual
                # filesystem signatures do not reappear when a new
                # partition is created at the same offset.
                # --------------------------------------------------

                if (
                    state.get(
                        "existing_content"
                    )
                    and
                    self._allow_overwrite()
                ):

                    self._wipe_existing_signatures(
                        target
                    )

                # --------------------------------------------------
                # Create requested partition table.
                # --------------------------------------------------

                self._run_privileged_checked(
                    (
                        "parted -s "
                        + shlex.quote(
                            device
                        )
                        + " mklabel "
                        + shlex.quote(
                            table
                        )
                    ),
                    (
                        "Unable to create "
                        f"{table} partition table "
                        f"on {device}"
                    ),
                )

                target[
                    "prepared_by_embite"
                ] = True

                target[
                    "partition_table"
                ] = table

                target[
                    "partitions"
                ] = {}

                target[
                    "active_partition"
                ] = None

                self._settle_partitions(
                    device
                )

            # --------------------------------------------------
            # Determine correct next partition position.
            # --------------------------------------------------

            start_mib = (
                self._next_partition_start_mib(
                    device
                )
            )

            if size_value.lower() in (
                "remaining",
                "rest",
                "all",
                "100%",
            ):

                end_value = "100%"

            else:

                size_mib = (
                    self._size_to_mib(
                        size_value
                    )
                )

                end_mib = (
                    start_mib
                    + size_mib
                )

                end_value = (
                    f"{end_mib}MiB"
                )

            self._run_privileged_checked(
                (
                    "parted -s -a optimal "
                    + shlex.quote(
                        device
                    )
                    + " mkpart primary "
                    + f"{start_mib}MiB "
                    + shlex.quote(
                        end_value
                    )
                ),
                (
                    "PARTITION_CREATE failed "
                    f"on PORT{target['port']} "
                    f"({device})"
                ),
            )

            self._settle_partitions(
                device
            )

            partition_node = (
                self._find_partition_node(
                    target,
                    partition_number,
                )
            )

            if not partition_node:

                raise RuntimeError(
                    "Partition was created but Linux "
                    "did not expose partition number "
                    f"{partition_number} for {device}."
                )

            self._refresh_target_partitions(
                target
            )

            partition = (
                target[
                    "partitions"
                ].get(
                    partition_number,
                    {},
                )
            )

            partition[
                "created_by_embite"
            ] = True

            partition[
                "requested_size"
            ] = size_value

            target[
                "partitions"
            ][
                partition_number
            ] = partition

            target[
                "active_partition"
            ] = partition_number

            results.extend(
                [
                    "",
                    f"[PORT{target['port']}]",
                    f"Device     : {device}",
                    f"Table      : {table}",
                    (
                        "Partition  : "
                        f"{partition_number}"
                    ),
                    (
                        "Node       : "
                        f"{partition_node}"
                    ),
                    f"Size       : {size_value}",
                    "Status     : CREATED",
                ]
            )

        self._save_targets(
            targets
        )

        return "\n".join(
            [
                "[PARTITION CREATE]",
                *results,
            ]
        )

    # ==========================================================
    # FILESYSTEM_DETECT
    # ==========================================================

    def detect_filesystem(self):
        """
        DSL:
            FILESYSTEM_DETECT
        """

        targets = self._selected_targets()

        lines = [
            "[FILESYSTEM DETECT]"
        ]

        for target in targets:

            self._validate_target_ownership(
                target
            )

            rows = self._lsblk_rows(
                target[
                    "device_node"
                ]
            )

            self._refresh_target_partitions(
                target
            )

            if len(lines) > 1:
                lines.append("")

            lines.append(
                f"[PORT{target['port']}]"
            )

            found = False

            for row in rows:

                node = row.get(
                    "NAME"
                )

                if not node:
                    continue

                filesystem = (
                    row.get(
                        "FSTYPE"
                    )
                    or
                    self._probe_filesystem(
                        node
                    )
                )

                if not filesystem:
                    continue

                found = True

                mountpoints = (
                    self._get_mountpoints(
                        node
                    )
                )

                lines.extend(
                    [
                        f"Node       : {node}",
                        (
                            "Filesystem : "
                            f"{filesystem}"
                        ),
                        (
                            "Mountpoint : "
                            f"{mountpoints[0] if mountpoints else 'None'}"
                        ),
                    ]
                )

            if not found:

                lines.append(
                    "Filesystem : None"
                )

        self._save_targets(
            targets
        )

        return "\n".join(
            lines
        )

    # ==========================================================
    # FILESYSTEM_CREATE
    # ==========================================================

    def create_filesystem(
        self,
        filesystem_type,
    ):
        """
        DSL:
            FILESYSTEM_CREATE <filesystem>

        Examples:
            FILESYSTEM_CREATE ext4
            FILESYSTEM_CREATE vfat
            FILESYSTEM_CREATE btrfs
        """

        targets = self._selected_targets()

        filesystem = (
            self._normalize_filesystem(
                filesystem_type
            )
        )

        (
            mkfs_command,
            options,
        ) = self._filesystem_command(
            filesystem
        )

        self._require_command(
            mkfs_command
        )

        preflight = []
        problems = []

        for target in targets:

            try:

                self._validate_target_ownership(
                    target
                )

                (
                    partition_number,
                    partition,
                ) = self._resolve_active_partition(
                    target
                )

                node = partition[
                    "node"
                ]

                mountpoints = (
                    self._get_mountpoints(
                        node
                    )
                )

                existing_filesystem = (
                    partition.get(
                        "filesystem"
                    )
                    or
                    self._probe_filesystem(
                        node
                    )
                )

                created_by_embite = bool(
                    partition.get(
                        "created_by_embite",
                        False,
                    )
                )

                if (
                    not created_by_embite
                    and
                    not self._allow_overwrite()
                ):

                    raise BlockedActionError(
                        f"PORT{target['port']} "
                        f"partition {node} existed "
                        "before the current EmbITE run."
                    )

                if (
                    existing_filesystem
                    and
                    not self._allow_overwrite()
                ):

                    raise BlockedActionError(
                        f"PORT{target['port']} "
                        f"partition {node} already "
                        f"contains filesystem "
                        f"{existing_filesystem}."
                    )

                if (
                    mountpoints
                    and
                    not self._allow_overwrite()
                ):

                    raise BlockedActionError(
                        f"PORT{target['port']} "
                        f"partition {node} is mounted."
                    )

                preflight.append(
                    {
                        "target": target,
                        "number": partition_number,
                        "partition": partition,
                        "node": node,
                        "mountpoints": mountpoints,
                        "existing_filesystem": (
                            existing_filesystem
                        ),
                    }
                )

            except Exception as exc:

                problems.append(
                    f"PORT{target.get('port')} -> {exc}"
                )

        if problems:

            raise BlockedActionError(
                "FILESYSTEM_CREATE preflight failed. "
                "No selected partition was formatted.\n"
                + "\n".join(
                    problems
                )
            )

        results = []

        for item in preflight:

            target = item[
                "target"
            ]

            number = item[
                "number"
            ]

            partition = item[
                "partition"
            ]

            node = item[
                "node"
            ]

            mountpoints = item[
                "mountpoints"
            ]

            existing_filesystem = item[
                "existing_filesystem"
            ]

            if mountpoints:

                self._sync()

                self._unmount_node(
                    node
                )

                remaining = (
                    self._get_mountpoints(
                        node
                    )
                )

                if remaining:

                    raise RuntimeError(
                        f"Unable to unmount {node}: "
                        + ", ".join(
                            remaining
                        )
                    )

            if (
                existing_filesystem
                and
                self._allow_overwrite()
            ):

                self._require_command(
                    "wipefs"
                )

                self._run_privileged_checked(
                    (
                        "wipefs -a -- "
                        + shlex.quote(
                            node
                        )
                    ),
                    (
                        "Unable to clear existing "
                        f"filesystem signature on {node}"
                    ),
                )

            command = mkfs_command

            if options:

                command += (
                    " "
                    + options
                )

            command += (
                " "
                + shlex.quote(
                    node
                )
            )

            self._run_privileged_checked(
                command,
                (
                    "FILESYSTEM_CREATE failed "
                    f"for {node}"
                ),
            )

            self._udev_settle()

            detected = (
                self._probe_filesystem(
                    node
                )
            )

            if not detected:

                raise RuntimeError(
                    "Filesystem creation completed "
                    "but filesystem could not be detected "
                    f"on {node}."
                )

            partition[
                "filesystem"
            ] = detected

            partition[
                "mount_point"
            ] = None

            partition[
                "mount_source"
            ] = None

            target[
                "partitions"
            ][
                number
            ] = partition

            target[
                "active_partition"
            ] = number

            results.extend(
                [
                    "",
                    f"[PORT{target['port']}]",
                    f"Partition  : {number}",
                    f"Node       : {node}",
                    (
                        "Filesystem : "
                        f"{detected}"
                    ),
                    "Status     : CREATED",
                ]
            )

        self._save_targets(
            targets
        )

        return "\n".join(
            [
                "[FILESYSTEM CREATE]",
                *results,
            ]
        )

    # ==========================================================
    # SELECTED TARGET MANAGEMENT
    # ==========================================================

    def _selected_targets(self):

        targets = self.context.get(
            "storage.targets",
            [],
        )

        if not targets:

            raise BlockedActionError(
                "No storage target is selected. "
                "Run USB_DETECT and USB_SELECT first."
            )

        missing = []

        for target in targets:

            if not target.get(
                "device_node"
            ):

                missing.append(
                    f"PORT{target.get('port')}"
                )

        if missing:

            raise BlockedActionError(
                "Selected USB port(s) do not contain "
                "a storage block device: "
                + ", ".join(
                    missing
                )
            )

        return targets

    def _save_targets(
        self,
        targets,
    ):

        self.context.set(
            "storage.targets",
            targets,
        )

    # ==========================================================
    # TARGET OWNERSHIP SAFETY
    # ==========================================================

    def _validate_target_ownership(
        self,
        target,
    ):
        """
        Verify that the runtime block node still belongs to the
        originally selected USB device.
        """

        node = target.get(
            "device_node"
        )

        usb_path = target.get(
            "usb_path"
        )

        if not node:

            raise BlockedActionError(
                f"PORT{target.get('port')} "
                "has no storage node."
            )

        output, error = self._send_command(
            (
                "test -b "
                + shlex.quote(
                    node
                )
                + " && echo YES || echo NO"
            )
        )

        if output.strip() != "YES":

            raise BlockedActionError(
                f"Selected block device {node} "
                "no longer exists. "
                "Run USB_DETECT and USB_SELECT again."
            )

        output, error = self._send_command(
            (
                "lsblk -dn -o TRAN "
                + shlex.quote(
                    node
                )
                + " 2>/dev/null | xargs"
            )
        )

        transport = (
            output.strip().lower()
        )

        if transport != "usb":

            raise BlockedActionError(
                f"Safety check failed for {node}: "
                f"current transport is "
                f"'{transport or 'unknown'}', not USB."
            )

        output, error = self._send_command(
            (
                "udevadm info "
                "--query=path "
                "--name="
                + shlex.quote(
                    node
                )
                + " 2>/dev/null"
            )
        )

        device_path = (
            output.strip()
        )

        if not device_path:

            basename = node.rsplit(
                "/",
                1,
            )[-1]

            output, error = self._send_command(
                (
                    "readlink -f "
                    + shlex.quote(
                        f"/sys/class/block/"
                        f"{basename}/device"
                    )
                    + " 2>/dev/null"
                )
            )

            device_path = (
                output.strip()
            )

        if usb_path:

            path_match = (
                f"/{usb_path}/"
                in device_path
                or
                f"/{usb_path}:"
                in device_path
                or
                device_path.endswith(
                    f"/{usb_path}"
                )
            )

            if not path_match:

                raise BlockedActionError(
                    f"Safety check failed for {node}. "
                    "Device no longer belongs to "
                    f"selected USB topology path "
                    f"{usb_path}."
                )

        expected_serial = (
            target.get(
                "serial"
            )
            or ""
        ).strip()

        if expected_serial:

            output, error = self._send_command(
                (
                    "lsblk -dn -o SERIAL "
                    + shlex.quote(
                        node
                    )
                    + " 2>/dev/null | xargs"
                )
            )

            current_serial = (
                output.strip()
            )

            if (
                current_serial
                and
                current_serial
                != expected_serial
            ):

                raise BlockedActionError(
                    f"Safety check failed for "
                    f"PORT{target['port']}. "
                    f"Expected serial "
                    f"{expected_serial}, "
                    f"but current device reports "
                    f"{current_serial}."
                )

    # ==========================================================
    # TARGET INSPECTION
    # ==========================================================

    def _inspect_target_state(
        self,
        target,
    ):

        node = target[
            "device_node"
        ]

        rows = self._lsblk_rows(
            node
        )

        if not rows:

            raise RuntimeError(
                f"Unable to inspect {node}."
            )

        root = rows[
            0
        ]

        self._refresh_target_partitions(
            target
        )

        partitions = list(
            target.get(
                "partitions",
                {},
            ).values()
        )

        has_filesystem = False
        mounted = False
        signature_found = False

        for row in rows:

            row_node = row.get(
                "NAME"
            )

            if not row_node:
                continue

            filesystem = (
                row.get(
                    "FSTYPE"
                )
                or
                self._probe_filesystem(
                    row_node
                )
            )

            if filesystem:
                has_filesystem = True

            if self._get_mountpoints(
                row_node
            ):
                mounted = True

            if self._probe_signature(
                row_node
            ):
                signature_found = True

        partition_table = (
            root.get(
                "PTTYPE"
            )
            or
            self._probe_partition_table(
                node
            )
        )

        existing_content = bool(
            partition_table
            or
            partitions
            or
            has_filesystem
            or
            mounted
            or
            signature_found
        )

        return {
            "transport": (
                root.get(
                    "TRAN"
                )
                or
                target.get(
                    "transport"
                )
            ),
            "vendor": (
                root.get(
                    "VENDOR"
                )
                or
                target.get(
                    "vendor"
                )
            ),
            "model": (
                root.get(
                    "MODEL"
                )
                or
                target.get(
                    "model"
                )
            ),
            "serial": (
                root.get(
                    "SERIAL"
                )
                or
                target.get(
                    "serial"
                )
            ),
            "size": (
                root.get(
                    "SIZE"
                )
                or
                target.get(
                    "size"
                )
            ),
            "partition_table": (
                partition_table
            ),
            "partitions": partitions,
            "has_filesystem": (
                has_filesystem
            ),
            "mounted": mounted,
            "signature_found": (
                signature_found
            ),
            "existing_content": (
                existing_content
            ),
        }

    # ==========================================================
    # PARTITION DISCOVERY
    # ==========================================================

    def _refresh_target_partitions(
        self,
        target,
    ):

        device = target[
            "device_node"
        ]

        rows = self._lsblk_rows(
            device
        )

        previous = target.get(
            "partitions",
            {},
        )

        discovered = {}

        for row in rows:

            if row.get(
                "TYPE"
            ) != "part":

                continue

            node = row.get(
                "NAME"
            )

            if not node:
                continue

            number = (
                self._partition_number_from_row(
                    row,
                    node,
                )
            )

            if number is None:
                continue

            old = (
                previous.get(
                    number,
                    {},
                )
                or
                previous.get(
                    str(number),
                    {},
                )
                or {}
            )

            mountpoints = (
                self._get_mountpoints(
                    node
                )
            )

            mountpoint = (
                mountpoints[
                    0
                ]
                if mountpoints
                else None
            )

            if (
                mountpoint
                and
                mountpoint
                == old.get(
                    "mount_point"
                )
            ):

                mount_source = (
                    old.get(
                        "mount_source"
                    )
                )

            elif mountpoint:

                mount_source = "EXISTING"

            else:

                mount_source = None

            filesystem = (
                row.get(
                    "FSTYPE"
                )
                or
                self._probe_filesystem(
                    node
                )
            )

            discovered[
                number
            ] = {
                "number": number,
                "node": node,
                "size": row.get(
                    "SIZE"
                ),
                "filesystem": filesystem,
                "mount_point": mountpoint,
                "mount_source": (
                    mount_source
                ),
                "created_by_embite": (
                    old.get(
                        "created_by_embite",
                        False,
                    )
                ),
                "requested_size": (
                    old.get(
                        "requested_size"
                    )
                ),
            }

        target[
            "partitions"
        ] = discovered

        return discovered

    def _find_partition_node(
        self,
        target,
        number,
    ):

        self._refresh_target_partitions(
            target
        )

        partition = (
            target.get(
                "partitions",
                {},
            ).get(
                number
            )
        )

        if not partition:

            return None

        return partition.get(
            "node"
        )

    def _partition_number_from_row(
        self,
        row,
        node,
    ):
        """
        Partition numbers come from sysfs instead of guessing from
        device-node names.
        """

        basename = node.rsplit(
            "/",
            1,
        )[-1]

        output, error = self._send_command(
            (
                "cat "
                + shlex.quote(
                    f"/sys/class/block/"
                    f"{basename}/partition"
                )
                + " 2>/dev/null"
            )
        )

        value = (
            output.strip()
        )

        if value.isdigit():

            return int(
                value
            )

        return None

    # ==========================================================
    # ACTIVE PARTITION
    # ==========================================================

    def _resolve_active_partition(
        self,
        target,
    ):

        self._refresh_target_partitions(
            target
        )

        partitions = target.get(
            "partitions",
            {},
        )

        if not partitions:

            raise BlockedActionError(
                f"PORT{target['port']} "
                "contains no partition."
            )

        active = target.get(
            "active_partition"
        )

        if (
            active is not None
            and
            active in partitions
        ):

            return (
                active,
                partitions[
                    active
                ],
            )

        if len(partitions) == 1:

            number = next(
                iter(
                    partitions
                )
            )

            target[
                "active_partition"
            ] = number

            return (
                number,
                partitions[
                    number
                ],
            )

        raise BlockedActionError(
            f"PORT{target['port']} contains "
            "multiple partitions and no active "
            "partition is selected."
        )

    # ==========================================================
    # UNMOUNT HELPERS
    # ==========================================================

    def _unmount_target(
        self,
        target,
    ):

        rows = self._lsblk_rows(
            target[
                "device_node"
            ]
        )

        mount_entries = []

        for row in rows:

            node = row.get(
                "NAME"
            )

            if not node:
                continue

            for mountpoint in (
                self._get_mountpoints(
                    node
                )
            ):

                mount_entries.append(
                    (
                        node,
                        mountpoint,
                    )
                )

        mount_entries.sort(
            key=lambda item: len(
                item[
                    1
                ]
            ),
            reverse=True,
        )

        results = []

        for node, mountpoint in (
            mount_entries
        ):

            self._run_privileged_checked(
                (
                    "umount -- "
                    + shlex.quote(
                        mountpoint
                    )
                ),
                (
                    "Unable to unmount "
                    f"{node} from "
                    f"{mountpoint}"
                ),
            )

            results.append(
                f"Unmounted {node} "
                f"-> {mountpoint}"
            )

        return results

    def _unmount_node(
        self,
        node,
    ):

        mountpoints = (
            self._get_mountpoints(
                node
            )
        )

        mountpoints.sort(
            key=len,
            reverse=True,
        )

        for mountpoint in mountpoints:

            self._run_privileged_checked(
                (
                    "umount -- "
                    + shlex.quote(
                        mountpoint
                    )
                ),
                (
                    f"Unable to unmount "
                    f"{node} from "
                    f"{mountpoint}"
                ),
            )

    def _verify_target_unmounted(
        self,
        target,
    ):

        rows = self._lsblk_rows(
            target[
                "device_node"
            ]
        )

        remaining = []

        for row in rows:

            node = row.get(
                "NAME"
            )

            if not node:
                continue

            for mountpoint in (
                self._get_mountpoints(
                    node
                )
            ):

                remaining.append(
                    f"{node} -> {mountpoint}"
                )

        if remaining:

            raise BlockedActionError(
                "Target could not be fully "
                "unmounted:\n"
                + "\n".join(
                    remaining
                )
            )

    # ==========================================================
    # SIGNATURE CLEANUP
    # ==========================================================

    def _wipe_existing_signatures(
        self,
        target,
    ):
        """
        Wipe recognizable signatures from selected target.

        Child partitions are wiped first, followed by the parent disk.

        This prevents an old filesystem signature from reappearing
        after recreating a partition at the same disk offset.
        """

        self._require_command(
            "wipefs"
        )

        device = target[
            "device_node"
        ]

        rows = self._lsblk_rows(
            device
        )

        child_nodes = []

        for row in rows:

            if row.get(
                "TYPE"
            ) == "part":

                node = row.get(
                    "NAME"
                )

                if node:
                    child_nodes.append(
                        node
                    )

        # Wipe child filesystems first.
        for node in child_nodes:

            self._run_privileged_checked(
                (
                    "wipefs -a -- "
                    + shlex.quote(
                        node
                    )
                ),
                (
                    "Unable to clear existing "
                    f"signatures on {node}"
                ),
            )

        # Then wipe the disk-level partition table/signatures.
        self._run_privileged_checked(
            (
                "wipefs -a -- "
                + shlex.quote(
                    device
                )
            ),
            (
                "Unable to clear existing "
                f"signatures on {device}"
            ),
        )

        self._udev_settle()

    # ==========================================================
    # MOUNT DISCOVERY
    # ==========================================================

    def _get_mountpoints(
        self,
        node,
    ):

        output, error = self._send_command(
            (
                "findmnt -rn -S "
                + shlex.quote(
                    node
                )
                + " -o TARGET "
                "2>/dev/null"
            )
        )

        return [
            line.strip()
            for line
            in output.splitlines()
            if line.strip()
        ]

    # ==========================================================
    # LSBLK
    # ==========================================================

    def _lsblk_rows(
        self,
        node,
    ):
        """
        Uses portable lsblk columns.

        PARTN, FSVER and MOUNTPOINTS are deliberately not used.
        """

        output, error = self._send_command(
            (
                "lsblk -P -p "
                "-o NAME,TYPE,SIZE,TRAN,VENDOR,"
                "MODEL,SERIAL "
                + shlex.quote(
                    node
                )
            )
        )

        if error:

            raise RuntimeError(
                f"lsblk failed for "
                f"{node}: {error}"
            )

        rows = []

        for line in output.splitlines():

            if not line.strip():
                continue

            try:

                tokens = shlex.split(
                    line
                )

            except ValueError:

                continue

            row = {}

            for token in tokens:

                if "=" not in token:
                    continue

                key, value = token.split(
                    "=",
                    1,
                )

                row[
                    key
                ] = value

            row_node = row.get(
                "NAME"
            )

            if row_node:

                row[
                    "FSTYPE"
                ] = (
                    self._probe_filesystem(
                        row_node
                    )
                )

                row[
                    "PTTYPE"
                ] = (
                    self._probe_partition_table(
                        row_node
                    )
                )

            if row:

                rows.append(
                    row
                )

        return rows

    # ==========================================================
    # STORAGE METADATA PROBES
    # ==========================================================

    def _probe_filesystem(
        self,
        node,
    ):

        output, error = (
            self._send_readonly_privileged(
                (
                    "blkid -p "
                    "-s TYPE "
                    "-o value "
                    + shlex.quote(
                        node
                    )
                    + " 2>/dev/null"
                )
            )
        )

        return (
            output.strip()
        )

    def _probe_partition_table(
        self,
        node,
    ):

        output, error = (
            self._send_readonly_privileged(
                (
                    "blkid -p "
                    "-s PTTYPE "
                    "-o value "
                    + shlex.quote(
                        node
                    )
                    + " 2>/dev/null"
                )
            )
        )

        return (
            output.strip()
        )

    def _probe_signature(
        self,
        node,
    ):

        output, error = (
            self._send_readonly_privileged(
                (
                    "blkid -p "
                    + shlex.quote(
                        node
                    )
                    + " >/dev/null 2>&1 "
                    "&& echo YES || echo NO"
                )
            )
        )

        return (
            output.strip()
            == "YES"
        )

    # ==========================================================
    # NEXT PARTITION POSITION
    # ==========================================================

    def _next_partition_start_mib(
        self,
        device,
    ):
        """
        Determine the correct start location for the next partition.

        IMPORTANT:
            parted must inspect the raw block device using privileged
            read-only access.

        New disk:
            start = 1 MiB

        Existing partition:
            start = ceil(highest partition end) + 1 MiB

        EmbITE must never silently fall back to 1 MiB when existing
        partitions are present, because that could cause overlap.
        """

        command = (
            "parted -m -s "
            + shlex.quote(
                device
            )
            + " unit MiB print"
        )

        output, error = (
            self._send_readonly_privileged(
                command
            )
        )

        # A real parted error is not safe to ignore.
        if error.strip():

            raise RuntimeError(
                "Unable to inspect partition layout "
                f"for {device}: {error.strip()}"
            )

        maximum_end = 0.0
        partition_found = False

        for line in output.splitlines():

            line = line.strip()

            # Example:
            #
            # 1:1.00MiB:2049MiB:2048MiB::primary:;
            #
            if not re.match(
                r"^\d+:",
                line,
            ):

                continue

            fields = (
                line.rstrip(
                    ";"
                ).split(
                    ":"
                )
            )

            if len(fields) < 3:
                continue

            end_value = (
                fields[
                    2
                ].strip()
            )

            match = re.fullmatch(
                r"([0-9.]+)MiB",
                end_value,
            )

            if not match:

                raise RuntimeError(
                    "Unable to parse partition "
                    "end position from parted output: "
                    f"{line}"
                )

            partition_found = True

            maximum_end = max(
                maximum_end,
                float(
                    match.group(
                        1
                    )
                ),
            )

        if partition_found:

            return (
                math.ceil(
                    maximum_end
                )
                + 1
            )

        # ------------------------------------------------------
        # No partition records were returned.
        #
        # Confirm that lsblk also sees no existing partition.
        # Never assume an empty disk if another source sees parts.
        # ------------------------------------------------------

        rows = self._lsblk_rows(
            device
        )

        existing_partitions = [
            row
            for row in rows
            if row.get(
                "TYPE"
            ) == "part"
        ]

        if existing_partitions:

            raise RuntimeError(
                "Existing partitions were detected on "
                f"{device}, but EmbITE could not "
                "determine their end positions safely."
            )

        return 1

    # ==========================================================
    # PARTITION NUMBER
    # ==========================================================

    @staticmethod
    def _next_partition_number(
        existing_numbers,
    ):

        expected = 1

        for number in sorted(
            existing_numbers
        ):

            if number != expected:
                break

            expected += 1

        return expected

    # ==========================================================
    # SIZE CONVERSION
    # ==========================================================

    @staticmethod
    def _size_to_mib(
        value,
    ):

        text = str(
            value
        ).strip().upper()

        match = re.fullmatch(
            r"(\d+(?:\.\d+)?)\s*"
            r"(K|KB|KIB|"
            r"M|MB|MIB|"
            r"G|GB|GIB|"
            r"T|TB|TIB)?",
            text,
        )

        if not match:

            raise ValueError(
                "Invalid partition size: "
                f"{value}"
            )

        amount = float(
            match.group(
                1
            )
        )

        unit = (
            match.group(
                2
            )
            or "M"
        )

        factors = {

            "K": 1 / 1024,
            "KB": 1 / 1024,
            "KIB": 1 / 1024,

            "M": 1,
            "MB": 1,
            "MIB": 1,

            "G": 1024,
            "GB": 1024,
            "GIB": 1024,

            "T": 1024 * 1024,
            "TB": 1024 * 1024,
            "TIB": 1024 * 1024,
        }

        size_mib = int(
            amount
            * factors[
                unit
            ]
        )

        if size_mib <= 0:

            raise ValueError(
                "Partition size must be "
                "greater than zero."
            )

        return size_mib

    # ==========================================================
    # FILESYSTEM HELPERS
    # ==========================================================

    @staticmethod
    def _normalize_filesystem(
        filesystem,
    ):

        value = str(
            filesystem
        ).strip().lower()

        aliases = {
            "fat32": "vfat",
        }

        value = aliases.get(
            value,
            value,
        )

        supported = {
            "ext2",
            "ext3",
            "ext4",
            "vfat",
            "ntfs",
            "exfat",
            "xfs",
            "btrfs",
            "f2fs",
        }

        if value not in supported:

            raise ValueError(
                "Unsupported filesystem: "
                f"{filesystem}. "
                "Supported: "
                + ", ".join(
                    sorted(
                        supported
                    )
                )
            )

        return value

    @staticmethod
    def _filesystem_command(
        filesystem,
    ):

        commands = {

            "ext2": (
                "mkfs.ext2",
                "-F",
            ),

            "ext3": (
                "mkfs.ext3",
                "-F",
            ),

            "ext4": (
                "mkfs.ext4",
                "-F",
            ),

            "vfat": (
                "mkfs.vfat",
                "-F 32",
            ),

            "ntfs": (
                "mkfs.ntfs",
                "-F",
            ),

            "exfat": (
                "mkfs.exfat",
                "",
            ),

            "xfs": (
                "mkfs.xfs",
                "-f",
            ),

            "btrfs": (
                "mkfs.btrfs",
                "-f",
            ),

            "f2fs": (
                "mkfs.f2fs",
                "-f",
            ),
        }

        return commands[
            filesystem
        ]

    # ==========================================================
    # PARTITION TABLE
    # ==========================================================

    @staticmethod
    def _normalize_partition_table(
        table,
    ):

        value = str(
            table
        ).strip().lower()

        aliases = {
            "dos": "msdos",
            "mbr": "msdos",
        }

        value = aliases.get(
            value,
            value,
        )

        supported = {
            "gpt",
            "msdos",
        }

        if value not in supported:

            raise ValueError(
                "Unsupported partition table: "
                f"{table}. "
                "Supported: gpt, "
                "msdos/dos/mbr"
            )

        return value

    # ==========================================================
    # PARTITION SETTLE
    # ==========================================================

    def _settle_partitions(
        self,
        device,
    ):

        self._run_privileged_checked(
            (
                "partprobe "
                + shlex.quote(
                    device
                )
            ),
            (
                "Unable to refresh partition "
                f"table for {device}"
            ),
        )

        self._udev_settle()

    def _udev_settle(self):

        self._send_command(
            (
                "command -v udevadm "
                ">/dev/null 2>&1 "
                "&& udevadm settle "
                "|| true"
            )
        )

    # ==========================================================
    # STORAGE SAFETY
    # ==========================================================

    def _allow_overwrite(self):

        value = (
            self.safety_config.get(
                "allow_overwrite",
                False,
            )
        )

        if isinstance(
            value,
            bool,
        ):

            return value

        return (
            str(
                value
            )
            .strip()
            .lower()
            in {
                "true",
                "yes",
                "1",
                "on",
            }
        )

    # ==========================================================
    # NORMAL REMOTE COMMAND
    # ==========================================================

    def _send_command(
        self,
        command,
    ):

        wrapped = (
            "PATH="
            + shlex.quote(
                self.SYSTEM_PATH
            )
            + "; "
            + "export PATH; "
            + command
        )

        return self.board.send_command(
            wrapped
        )

    # ==========================================================
    # READ-ONLY PRIVILEGED COMMAND
    # ==========================================================

    def _send_readonly_privileged(
        self,
        command,
    ):
        """
        Execute a read-only storage inspection operation through sudo
        when the current SSH account is not root.
        """

        system_path = shlex.quote(
            self.SYSTEM_PATH
        )

        quoted_command = shlex.quote(
            command
        )

        wrapped = (
            "PATH="
            + system_path
            + "; "
            + "export PATH; "
            + 'if [ "$(id -u)" -eq 0 ]; then '
            + "sh -c "
            + quoted_command
            + "; "
            + "else "
            + "sudo -n env PATH="
            + system_path
            + " sh -c "
            + quoted_command
            + "; "
            + "fi"
        )

        output, error = (
            self.board.send_command(
                wrapped
            )
        )

        lowered_error = (
            error
            or ""
        ).lower()

        if (
            "sudo:" in lowered_error
            or
            "permission denied"
            in lowered_error
        ):

            raise BlockedActionError(
                "Unable to perform privileged "
                "read-only storage inspection: "
                + error.strip()
            )

        return (
            output,
            error,
        )

    # ==========================================================
    # REQUIRED COMMAND
    # ==========================================================

    def _require_command(
        self,
        command,
    ):

        output, error = self._send_command(
            (
                "command -v "
                + shlex.quote(
                    command
                )
                + " 2>/dev/null"
            )
        )

        resolved_path = (
            output.strip()
        )

        if not resolved_path:

            raise BlockedActionError(
                "Required DUT utility "
                f"'{command}' is not available. "
                "Checked PATH: "
                f"{self.SYSTEM_PATH}"
            )

        return resolved_path

    # ==========================================================
    # PRIVILEGED COMMAND WITH EXIT CODE
    # ==========================================================

    def _run_privileged_checked(
        self,
        command,
        error_message,
    ):
        """
        Run privileged operation and check the real exit status.

        stderr output alone does not indicate failure.
        """

        marker = (
            "__EMBITE_EXIT_CODE__"
        )

        system_path = shlex.quote(
            self.SYSTEM_PATH
        )

        quoted_command = shlex.quote(
            command
        )

        wrapped = (
            "PATH="
            + system_path
            + "; "
            + "export PATH; "
            + 'if [ "$(id -u)" -eq 0 ]; then '
            + "sh -c "
            + quoted_command
            + "; "
            + "rc=$?; "
            + "else "
            + "sudo -n env PATH="
            + system_path
            + " sh -c "
            + quoted_command
            + "; "
            + "rc=$?; "
            + "fi; "
            + "printf '\\n"
            + marker
            + "=%s\\n' \"$rc\""
        )

        output, error = (
            self.board.send_command(
                wrapped
            )
        )

        match = re.search(
            rf"{re.escape(marker)}=(\d+)",
            output,
        )

        if not match:

            details = []

            if output.strip():

                details.append(
                    output.strip()
                )

            if error.strip():

                details.append(
                    error.strip()
                )

            raise RuntimeError(
                f"{error_message}: "
                "unable to determine remote "
                "command exit status."
                + (
                    "\n"
                    + "\n".join(
                        details
                    )
                    if details
                    else ""
                )
            )

        exit_code = int(
            match.group(
                1
            )
        )

        cleaned_output = re.sub(
            rf"\n?{re.escape(marker)}=\d+\n?",
            "",
            output,
        ).strip()

        if exit_code != 0:

            details = []

            if cleaned_output:

                details.append(
                    cleaned_output
                )

            if error.strip():

                details.append(
                    error.strip()
                )

            detail_text = (
                "\n".join(
                    details
                )
                if details
                else
                (
                    "remote command exited "
                    f"with status {exit_code}"
                )
            )

            raise RuntimeError(
                f"{error_message}: "
                f"{detail_text}"
            )

        return cleaned_output

    # ==========================================================
    # SYNC
    # ==========================================================

    def _sync(self):

        output, error = self._send_command(
            "sync"
        )

        if error:

            raise RuntimeError(
                f"Storage sync failed: {error}"
            )
