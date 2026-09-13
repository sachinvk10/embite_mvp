"""
EmbITE MVP - USB Validation Library

File:
    lib/usb.py

Purpose:
    This module provides reusable USB discovery, enumeration, topology
    detection, physical/topology port selection, device metadata collection,
    driver discovery, and USB-storage block-device mapping for EmbITE.

    This module does NOT perform partitioning, filesystem creation,
    mounting, unmounting, or storage data operations.

    Those operations belong to:

        lib/storage.py

Architecture:

    USB_LIST
        ↓
    Enumerate all connected USB devices
        ↓
    Read USB metadata from Linux sysfs
        ↓
    Read interface class and bound kernel drivers
        ↓
    Display USB inventory


    USB_DETECT
        ↓
    Scan USB topology
        ↓
    Group connected devices by root USB topology port
        ↓
    Assign EmbITE runtime port numbers:
        PORT1
        PORT2
        PORT3
        ...
        ↓
    Resolve USB storage block nodes where available
        ↓
    Store complete information in RuntimeContext


    USB_SELECT 1 2
        ↓
    Select PORT1 and PORT2
        ↓
    Create active storage targets
        ↓
    PORT1 → dynamically discovered /dev/sdX
    PORT2 → dynamically discovered /dev/sdY
        ↓
    Store selected targets in RuntimeContext
        ↓
    Subsequent Storage APIs use those targets


Important Design Rule:
    Linux block device names such as:

        /dev/sda
        /dev/sdb
        /dev/sdc

    are NOT hard-coded anywhere in the DSL.

    They are discovered dynamically after USB port selection.

Example DSL:

    USB_LIST

    USB_DETECT

    USB_SELECT 1 2

    STORAGE_INSPECT

    PARTITION_CREATE gpt 1 2G

    FILESYSTEM_CREATE ext4

    STORAGE_MOUNT


RuntimeContext Keys:
    usb.devices
        Complete USB device inventory.

    usb.ports
        USB topology grouped into EmbITE PORT numbers.

    usb.selected_ports
        Currently selected USB ports.

    storage.targets
        Storage targets derived from the selected USB ports.


Example RuntimeContext after:

    USB_SELECT 1 2

    storage.targets = [

        {
            "port": 1,
            "usb_path": "3-1",
            "device_node": "/dev/sda",
            "transport": "usb",
            "vendor": "Sony",
            "model": "Storage Media",
            "serial": "...",
            "partitions": {},
        },

        {
            "port": 2,
            "usb_path": "3-2",
            "device_node": "/dev/sdc",
            "transport": "usb",
            "vendor": "SanDisk",
            "model": "Ultra",
            "serial": "...",
            "partitions": {},
        },
    ]


USB Port Numbering:
    Linux exposes USB topology using names such as:

        1-1
        1-2
        3-1
        3-2
        1-1.2

    EmbITE groups devices by the top-level/root USB topology path.

    Example:

        3-1
        3-1.1
        3-1.2

    all belong to the same top-level USB connection:

        3-1

    EmbITE then exposes these connections as:

        PORT1
        PORT2
        PORT3
        ...

    The actual Linux USB topology path is always retained internally.

    PORT numbering in the current MVP is a deterministic EmbITE runtime
    mapping of detected root USB topology paths. The user should use the
    USB_DETECT output to determine the PORT number for the current run.

Safety:
    USB_SELECT never performs destructive storage operations.

    It only identifies and stores the selected USB target.

    Storage safety, overwrite protection, partitioning, formatting,
    mounting, and unmounting are handled by lib/storage.py.
"""

import re
import shlex

from utility.exceptions import BlockedActionError


class USB:
    """
    Reusable EmbITE USB validation interface.

    Parameters:
        board_actions:
            BoardActions instance used to execute commands on the DUT.

        runtime_context:
            Shared RuntimeContext instance for the complete EmbITE run.

    All DUT communication goes through BoardActions.

    This library has no direct SSH or Serial dependency.
    """

    def __init__(
        self,
        board_actions,
        runtime_context,
    ):
        self.board = board_actions
        self.context = runtime_context

    # ==========================================================
    # PUBLIC DSL API
    # ==========================================================

    def list_devices(self):
        """
        DSL:
            USB_LIST

        Parameters:
            None

        Purpose:
            Enumerate all currently connected external USB devices.

        Information collected:
            - Linux USB topology path
            - Bus number
            - Device number
            - Vendor ID
            - Product ID
            - Manufacturer
            - Product
            - Serial number
            - USB version
            - Negotiated speed
            - Device class
            - Interface classes
            - Bound kernel drivers
            - EmbITE device classification

        Linux root hubs are not presented as external USB devices.

        Example output:

            [USB DEVICE 1]
            USB Path          : 3-1
            Bus               : 3
            Device            : 2
            Vendor ID         : 054c
            Product ID        : 05ba
            Manufacturer      : Sony
            Product           : Storage Media
            Serial            : ABC123
            USB Version       : 3.00
            Speed             : 5000 Mbps
            Device Class      : 00
            Interface Classes : 08
            Driver            : uas
            Type              : STORAGE
        """

        devices = self._enumerate_usb_devices()

        # Keep the current inventory available to later APIs.
        self.context.set(
            "usb.devices",
            devices,
        )

        if not devices:
            return "No external USB devices detected."

        lines = []

        for index, device in enumerate(
            devices,
            start=1,
        ):

            if lines:
                lines.append("")

            lines.extend(
                [
                    f"[USB DEVICE {index}]",
                    (
                        "USB Path          : "
                        f"{device.get('usb_path') or 'N/A'}"
                    ),
                    (
                        "Bus               : "
                        f"{device.get('bus') or 'N/A'}"
                    ),
                    (
                        "Device            : "
                        f"{device.get('device_number') or 'N/A'}"
                    ),
                    (
                        "Vendor ID         : "
                        f"{device.get('vendor_id') or 'N/A'}"
                    ),
                    (
                        "Product ID        : "
                        f"{device.get('product_id') or 'N/A'}"
                    ),
                    (
                        "Manufacturer      : "
                        f"{device.get('manufacturer') or 'N/A'}"
                    ),
                    (
                        "Product           : "
                        f"{device.get('product') or 'N/A'}"
                    ),
                    (
                        "Serial            : "
                        f"{device.get('serial') or 'N/A'}"
                    ),
                    (
                        "USB Version       : "
                        f"{device.get('version') or 'N/A'}"
                    ),
                    (
                        "Speed             : "
                        f"{self._format_speed(device.get('speed'))}"
                    ),
                    (
                        "Device Class      : "
                        f"{device.get('device_class') or 'N/A'}"
                    ),
                    (
                        "Interface Classes : "
                        f"{device.get('interface_classes') or 'N/A'}"
                    ),
                    (
                        "Driver            : "
                        f"{device.get('drivers') or 'N/A'}"
                    ),
                    (
                        "Type              : "
                        f"{device.get('type') or 'UNKNOWN'}"
                    ),
                ]
            )

        return "\n".join(lines)

    # ==========================================================
    # USB_DETECT
    # ==========================================================

    def detect_ports(self):
        """
        DSL:
            USB_DETECT

        Parameters:
            None

        Purpose:
            Detect occupied USB root topology ports and map connected
            devices to EmbITE PORT numbers.

        The API also discovers USB-backed block devices belonging to
        each detected USB port.

        Example:

            PORT1
                USB Path   : 1-1
                Device     : Logitech USB Keyboard
                Type       : HID
                Driver     : usbhid
                Block Node : None

            PORT2
                USB Path   : 3-1
                Device     : Sony Storage Media
                Type       : STORAGE
                Driver     : uas
                Block Node : /dev/sda

        The resulting topology is stored in RuntimeContext.

        RuntimeContext:
            usb.devices
            usb.ports

        Previous USB selections and storage targets are cleared because
        a new USB_DETECT operation represents a fresh topology scan.
        """

        devices = self._enumerate_usb_devices()

        self.context.set(
            "usb.devices",
            devices,
        )

        # A fresh USB detection invalidates previous selection state.
        self.context.set(
            "usb.selected_ports",
            [],
        )

        self.context.set(
            "storage.targets",
            [],
        )

        if not devices:

            self.context.set(
                "usb.ports",
                [],
            )

            raise RuntimeError(
                "USB_DETECT failed: "
                "no external USB devices detected."
            )

        # ------------------------------------------------------
        # Group USB devices by top-level/root topology path.
        #
        # Examples:
        #
        #   3-1       -> root path 3-1
        #   3-1.1     -> root path 3-1
        #   3-1.2     -> root path 3-1
        #
        # A USB hub connected to 3-1 may therefore expose several
        # child devices while remaining associated with one
        # top-level physical/topology connection.
        # ------------------------------------------------------

        grouped = {}

        for device in devices:

            usb_path = device.get(
                "usb_path",
                "",
            )

            if not usb_path:
                continue

            root_path = self._root_usb_path(
                usb_path
            )

            grouped.setdefault(
                root_path,
                [],
            ).append(
                device
            )

        root_paths = sorted(
            grouped.keys(),
            key=self._usb_path_sort_key,
        )

        ports = []

        # ------------------------------------------------------
        # Create EmbITE PORT mapping.
        # ------------------------------------------------------

        for port_number, root_path in enumerate(
            root_paths,
            start=1,
        ):

            port_devices = grouped[
                root_path
            ]

            storage_nodes = (
                self._get_storage_nodes_for_usb_root(
                    root_path
                )
            )

            storage_metadata = []

            for node in storage_nodes:

                metadata = (
                    self._get_block_metadata(
                        node
                    )
                )

                metadata[
                    "device_node"
                ] = node

                storage_metadata.append(
                    metadata
                )

            port = {
                "port": port_number,
                "usb_path": root_path,
                "status": "CONNECTED",
                "devices": port_devices,
                "storage_nodes": storage_nodes,
                "storage_devices": storage_metadata,
            }

            ports.append(
                port
            )

        self.context.set(
            "usb.ports",
            ports,
        )

        return self._format_detected_ports(
            ports
        )

    # ==========================================================
    # USB_SELECT
    # ==========================================================

    def select_ports(
        self,
        *port_arguments,
    ):
        """
        DSL:
            USB_SELECT <port1> [port2] [port3] ...

        Examples:
            USB_SELECT 1

            USB_SELECT 1 2

            USB_SELECT 1 2 3 4

        Purpose:
            Select one or more USB topology ports for subsequent
            validation.

        The API does NOT require the user to know Linux block-device
        names such as /dev/sda.

        Example:

            USB_DETECT

            PORT1 -> /dev/sda
            PORT2 -> /dev/sdc

            USB_SELECT 1 2

        RuntimeContext becomes conceptually:

            storage.targets = [
                {
                    "port": 1,
                    "device_node": "/dev/sda",
                    ...
                },
                {
                    "port": 2,
                    "device_node": "/dev/sdc",
                    ...
                },
            ]

        Subsequent APIs such as:

            STORAGE_INSPECT
            PARTITION_CREATE
            FILESYSTEM_CREATE
            STORAGE_MOUNT

        operate on those runtime targets.

        Notes:
            - USB_DETECT must be executed before USB_SELECT.
            - Selecting a non-storage USB port is allowed.
            - Storage APIs will later block if a selected port
              does not contain a storage device.
            - More than one USB storage disk under a single selected
              root port is treated as ambiguous in the MVP and blocked
              before destructive storage operations can occur.
        """

        if not port_arguments:

            raise ValueError(
                "USB_SELECT requires at least one port number. "
                "Example: USB_SELECT 1 2"
            )

        detected_ports = self.context.get(
            "usb.ports",
            [],
        )

        if not detected_ports:

            raise RuntimeError(
                "USB_SELECT cannot run because USB_DETECT "
                "has not discovered any USB ports. "
                "Run USB_DETECT first."
            )

        # ------------------------------------------------------
        # Parse and validate DSL parameters.
        # ------------------------------------------------------

        requested_ports = []

        for argument in port_arguments:

            try:

                port_number = int(
                    str(argument)
                )

            except ValueError as exc:

                raise ValueError(
                    "Invalid USB port number: "
                    f"{argument}"
                ) from exc

            if port_number <= 0:

                raise ValueError(
                    "USB port number must be greater than zero: "
                    f"{port_number}"
                )

            if port_number not in requested_ports:

                requested_ports.append(
                    port_number
                )

        port_lookup = {
            port["port"]: port
            for port in detected_ports
        }

        missing_ports = [
            number
            for number in requested_ports
            if number not in port_lookup
        ]

        if missing_ports:

            available = ", ".join(
                str(port["port"])
                for port in detected_ports
            )

            raise ValueError(
                "Requested USB port(s) not detected: "
                + ", ".join(
                    str(port)
                    for port in missing_ports
                )
                + ". Available detected PORT numbers: "
                + available
            )

        # ------------------------------------------------------
        # Build selected-port state.
        # ------------------------------------------------------

        selected_ports = [
            port_lookup[
                port_number
            ]
            for port_number in requested_ports
        ]

        # ------------------------------------------------------
        # Build storage targets.
        #
        # One target is created for every selected USB port.
        #
        # If the selected USB port is not a storage device,
        # device_node remains None.
        #
        # Storage APIs can therefore provide a meaningful
        # BLOCKED result rather than silently ignoring the port.
        # ------------------------------------------------------

        storage_targets = []

        for port in selected_ports:

            storage_nodes = port.get(
                "storage_nodes",
                [],
            )

            # Multiple block disks underneath the same USB root
            # connection are ambiguous for the current MVP.
            #
            # Example:
            #     USB hub / multi-LUN reader under one PORT.
            #
            # Never arbitrarily choose one disk.
            if len(storage_nodes) > 1:

                raise BlockedActionError(
                    f"PORT{port['port']} contains multiple USB "
                    "storage block devices: "
                    + ", ".join(storage_nodes)
                    + ". EmbITE will not select one automatically."
                )

            device_node = (
                storage_nodes[0]
                if storage_nodes
                else None
            )

            block_metadata = {}

            if device_node:

                block_metadata = (
                    self._get_block_metadata(
                        device_node
                    )
                )

            target = {
                "port": port["port"],
                "usb_path": port["usb_path"],
                "device_node": device_node,
                "transport": (
                    block_metadata.get(
                        "transport"
                    )
                    or (
                        "usb"
                        if device_node
                        else None
                    )
                ),
                "vendor": (
                    block_metadata.get(
                        "vendor"
                    )
                    or None
                ),
                "model": (
                    block_metadata.get(
                        "model"
                    )
                    or None
                ),
                "serial": (
                    block_metadata.get(
                        "serial"
                    )
                    or None
                ),
                "size": (
                    block_metadata.get(
                        "size"
                    )
                    or None
                ),
                "driver": (
                    block_metadata.get(
                        "driver"
                    )
                    or self._driver_for_port(
                        port
                    )
                ),

                # Runtime partition state.
                #
                # storage.py updates this dictionary dynamically.
                "partitions": {},

                # Most recently created or selected partition.
                "active_partition": None,
            }

            storage_targets.append(
                target
            )

        # ------------------------------------------------------
        # Save shared runtime state.
        # ------------------------------------------------------

        self.context.set(
            "usb.selected_ports",
            selected_ports,
        )

        self.context.set(
            "storage.targets",
            storage_targets,
        )

        # ------------------------------------------------------
        # Format selection result.
        # ------------------------------------------------------

        lines = [
            "[USB PORT SELECTION]"
        ]

        for target in storage_targets:

            lines.extend(
                [
                    "",
                    f"[PORT{target['port']}]",
                    (
                        "USB Path    : "
                        f"{target.get('usb_path') or 'N/A'}"
                    ),
                    (
                        "Storage     : "
                        f"{'YES' if target.get('device_node') else 'NO'}"
                    ),
                    (
                        "Block Node  : "
                        f"{target.get('device_node') or 'N/A'}"
                    ),
                    (
                        "Transport   : "
                        f"{target.get('transport') or 'N/A'}"
                    ),
                    (
                        "Vendor      : "
                        f"{target.get('vendor') or 'N/A'}"
                    ),
                    (
                        "Model       : "
                        f"{target.get('model') or 'N/A'}"
                    ),
                    (
                        "Serial      : "
                        f"{target.get('serial') or 'N/A'}"
                    ),
                    (
                        "Size        : "
                        f"{target.get('size') or 'N/A'}"
                    ),
                    (
                        "Driver      : "
                        f"{target.get('driver') or 'N/A'}"
                    ),
                ]
            )

        return "\n".join(lines)

    # ==========================================================
    # USB DEVICE ENUMERATION
    # ==========================================================

    def _enumerate_usb_devices(self):
        """
        Enumerate external USB devices directly from Linux sysfs.

        Source:
            /sys/bus/usb/devices/

        This is preferred over using only human-readable lsusb output
        because sysfs provides direct kernel/device information.

        Root hubs such as:

            usb1
            usb2
            usb3

        are automatically excluded.

        USB interfaces such as:

            3-1:1.0

        are not returned as separate devices.

        Their interface class and driver information is instead attached
        to the corresponding USB device:

            3-1
        """

        command = r'''
read_attr()
{
    file="$1"

    if [ -r "$file" ]; then
        tr '\t\r\n' '   ' < "$file" \
            | sed 's/[[:space:]]*$//'
    fi
}

for dev in /sys/bus/usb/devices/*; do

    [ -e "$dev" ] || continue

    name=$(basename "$dev")

    # USB devices look like:
    #
    #   1-1
    #   1-1.2
    #   3-1
    #
    # Exclude:
    #
    #   usb1
    #   usb2
    #   1-1:1.0
    #
    case "$name" in
        *:*)
            continue
            ;;
    esac

    echo "$name" | grep -Eq '^[0-9]+-[0-9]+(\.[0-9]+)*$' \
        || continue

    bus=$(read_attr "$dev/busnum")
    devnum=$(read_attr "$dev/devnum")
    vendor=$(read_attr "$dev/idVendor")
    product_id=$(read_attr "$dev/idProduct")
    manufacturer=$(read_attr "$dev/manufacturer")
    product=$(read_attr "$dev/product")
    serial=$(read_attr "$dev/serial")
    speed=$(read_attr "$dev/speed")
    version=$(read_attr "$dev/version")
    device_class=$(read_attr "$dev/bDeviceClass")

    drivers=""
    interface_classes=""

    for interface in /sys/bus/usb/devices/"$name":*; do

        [ -e "$interface" ] || continue

        class=$(read_attr "$interface/bInterfaceClass")

        if [ -n "$class" ]; then

            case ",$interface_classes," in
                *,"$class",*)
                    ;;
                *)
                    if [ -n "$interface_classes" ]; then
                        interface_classes="${interface_classes},${class}"
                    else
                        interface_classes="$class"
                    fi
                    ;;
            esac

        fi

        if [ -L "$interface/driver" ]; then

            driver=$(
                basename "$(
                    readlink -f "$interface/driver"
                )"
            )

            if [ -n "$driver" ]; then

                case ",$drivers," in
                    *,"$driver",*)
                        ;;
                    *)
                        if [ -n "$drivers" ]; then
                            drivers="${drivers},${driver}"
                        else
                            drivers="$driver"
                        fi
                        ;;
                esac

            fi

        fi

    done

    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$name" \
        "$bus" \
        "$devnum" \
        "$vendor" \
        "$product_id" \
        "$manufacturer" \
        "$product" \
        "$serial" \
        "$speed" \
        "$version" \
        "$device_class" \
        "$interface_classes" \
        "$drivers"

done | sort -V
'''

        output, error = self.board.send_command(
            command
        )

        if error:

            raise RuntimeError(
                "Unable to enumerate USB devices from sysfs: "
                f"{error}"
            )

        devices = []

        for line in output.splitlines():

            if not line.strip():
                continue

            fields = line.split(
                "\t"
            )

            # Ensure missing trailing fields do not cause
            # parsing errors.
            while len(fields) < 13:
                fields.append("")

            device = {
                "usb_path": fields[0].strip(),
                "bus": fields[1].strip(),
                "device_number": fields[2].strip(),
                "vendor_id": fields[3].strip(),
                "product_id": fields[4].strip(),
                "manufacturer": fields[5].strip(),
                "product": fields[6].strip(),
                "serial": fields[7].strip(),
                "speed": fields[8].strip(),
                "version": fields[9].strip(),
                "device_class": fields[10].strip(),
                "interface_classes": fields[11].strip(),
                "drivers": fields[12].strip(),
            }

            device[
                "type"
            ] = self._classify_usb_device(
                device
            )

            devices.append(
                device
            )

        return devices

    # ==========================================================
    # USB DEVICE CLASSIFICATION
    # ==========================================================

    @staticmethod
    def _classify_usb_device(
        device,
    ):
        """
        Classify a USB device using interface class, driver,
        and product metadata.

        USB interface class examples:

            01 = Audio
            02 = Communications
            03 = HID
            08 = Mass Storage
            09 = Hub
            0A = CDC Data
            0E = Video
            E0 = Wireless Controller
            FF = Vendor Specific

        The classification is informational.

        Storage block-device ownership is independently verified using
        Linux block transport/sysfs information.
        """

        classes = {
            item.strip().lower()
            for item in (
                device.get(
                    "interface_classes",
                    ""
                )
                or ""
            ).split(",")
            if item.strip()
        }

        drivers = (
            device.get(
                "drivers",
                ""
            )
            or ""
        ).lower()

        product = (
            device.get(
                "product",
                ""
            )
            or ""
        ).lower()

        # ------------------------------------------------------
        # Mass Storage
        # ------------------------------------------------------

        if (
            "08" in classes
            or "usb-storage" in drivers
            or "uas" in drivers
        ):
            return "STORAGE"

        # ------------------------------------------------------
        # Keyboard / Mouse / HID
        # ------------------------------------------------------

        if "03" in classes:

            if "keyboard" in product:
                return "KEYBOARD"

            if (
                "mouse" in product
                or "receiver" in product
            ):
                return "MOUSE/HID"

            return "HID"

        # ------------------------------------------------------
        # Hub
        # ------------------------------------------------------

        if "09" in classes:
            return "HUB"

        # ------------------------------------------------------
        # USB Serial
        # ------------------------------------------------------

        serial_drivers = (
            "ftdi_sio",
            "cp210x",
            "ch341",
            "pl2303",
            "cdc_acm",
        )

        if any(
            driver in drivers
            for driver in serial_drivers
        ):
            return "SERIAL"

        # ------------------------------------------------------
        # USB Network
        # ------------------------------------------------------

        network_drivers = (
            "r8152",
            "cdc_ether",
            "cdc_ncm",
            "asix",
            "ax88179_178a",
            "rndis_host",
        )

        if any(
            driver in drivers
            for driver in network_drivers
        ):
            return "NETWORK"

        # ------------------------------------------------------
        # Video
        # ------------------------------------------------------

        if (
            "0e" in classes
            or "uvcvideo" in drivers
        ):
            return "VIDEO"

        # ------------------------------------------------------
        # Audio
        # ------------------------------------------------------

        if (
            "01" in classes
            or "snd-usb-audio" in drivers
        ):
            return "AUDIO"

        # ------------------------------------------------------
        # Communications / Network-like
        # ------------------------------------------------------

        if (
            "02" in classes
            or "0a" in classes
        ):
            return "COMMUNICATION"

        # ------------------------------------------------------
        # Wireless
        # ------------------------------------------------------

        if "e0" in classes:
            return "WIRELESS"

        return "OTHER"

    # ==========================================================
    # STORAGE NODE DISCOVERY
    # ==========================================================

    def _get_storage_nodes_for_usb_root(
        self,
        root_usb_path,
    ):
        """
        Find Linux block disk nodes that belong to one USB root
        topology path.

        Example:

            root_usb_path:
                3-1

            Linux block node:
                /dev/sda

            Linux device path may contain:

                .../usb3/3-1/3-1:1.0/.../block/sda

        For a hub:

            .../usb3/3-1/3-1.2/3-1.2:1.0/.../block/sda

        Both still belong to top-level path:

            3-1

        Only block devices whose Linux transport is USB are considered.
        """

        quoted_root = shlex.quote(
            root_usb_path
        )

        command = f'''
root={quoted_root}

lsblk -dpno NAME,TYPE,TRAN 2>/dev/null \
| while read -r node type transport; do

    [ "$type" = "disk" ] || continue
    [ "$transport" = "usb" ] || continue

    devpath=$(
        udevadm info \
            --query=path \
            --name="$node" \
            2>/dev/null
    )

    if [ -z "$devpath" ]; then

        base=$(
            basename "$node"
        )

        devpath=$(
            readlink -f \
                "/sys/class/block/$base/device" \
                2>/dev/null
        )

    fi

    case "$devpath" in

        *"/$root/"*)
            echo "$node"
            ;;

        *"/$root:"*)
            echo "$node"
            ;;

    esac

done | sort -u
'''

        output, error = self.board.send_command(
            command
        )

        if error:
            return []

        return [
            line.strip()
            for line in output.splitlines()
            if line.strip()
        ]

    # ==========================================================
    # BLOCK DEVICE METADATA
    # ==========================================================

    def _get_block_metadata(
        self,
        node,
    ):
        """
        Collect block-device information for a USB storage node.

        Example node:
            /dev/sda

        Returned dictionary:

            {
                "transport": "usb",
                "vendor": "Sony",
                "model": "Storage Media",
                "serial": "...",
                "size": "7.2G",
                "driver": "uas",
            }
        """

        quoted_node = shlex.quote(
            node
        )

        command = (
            "lsblk -dnP "
            "-o TRAN,VENDOR,MODEL,SERIAL,SIZE "
            f"{quoted_node} 2>/dev/null"
        )

        output, error = self.board.send_command(
            command
        )

        metadata = {
            "transport": "",
            "vendor": "",
            "model": "",
            "serial": "",
            "size": "",
            "driver": "",
        }

        if output:

            try:

                tokens = shlex.split(
                    output.splitlines()[0]
                )

            except ValueError:

                tokens = []

            values = {}

            for token in tokens:

                if "=" not in token:
                    continue

                key, value = token.split(
                    "=",
                    1,
                )

                values[
                    key.upper()
                ] = value.strip()

            metadata.update(
                {
                    "transport": values.get(
                        "TRAN",
                        "",
                    ),
                    "vendor": values.get(
                        "VENDOR",
                        "",
                    ),
                    "model": values.get(
                        "MODEL",
                        "",
                    ),
                    "serial": values.get(
                        "SERIAL",
                        "",
                    ),
                    "size": values.get(
                        "SIZE",
                        "",
                    ),
                }
            )

        # ------------------------------------------------------
        # Resolve functional USB driver.
        #
        # udev may expose ID_USB_DRIVER.
        #
        # If not available, walk upward through sysfs until a
        # bound kernel driver is found.
        # ------------------------------------------------------

        driver_command = f'''
node={quoted_node}

props=$(
    udevadm info \
        --query=property \
        --name="$node" \
        2>/dev/null
)

driver=$(
    echo "$props" \
    | sed -n 's/^ID_USB_DRIVER=//p' \
    | head -1
)

if [ -z "$driver" ]; then

    base=$(
        basename "$node"
    )

    current=$(
        readlink -f \
            "/sys/class/block/$base/device" \
            2>/dev/null
    )

    while [ -n "$current" ] \
          && [ "$current" != "/" ]; do

        if [ -L "$current/driver" ]; then

            driver=$(
                basename "$(
                    readlink -f "$current/driver"
                )"
            )

            break

        fi

        current=$(
            dirname "$current"
        )

    done

fi

printf '%s\n' "$driver"
'''

        driver_output, driver_error = (
            self.board.send_command(
                driver_command
            )
        )

        if driver_output:

            metadata[
                "driver"
            ] = driver_output.strip()

        return metadata

    # ==========================================================
    # USB DETECT OUTPUT
    # ==========================================================

    def _format_detected_ports(
        self,
        ports,
    ):
        """
        Format USB_DETECT output.

        Each EmbITE PORT represents one top-level USB topology path.
        """

        if not ports:
            return "No connected USB ports detected."

        lines = []

        for port in ports:

            if lines:
                lines.append("")

            lines.extend(
                [
                    f"[PORT{port['port']}]",
                    (
                        "USB Root Path : "
                        f"{port.get('usb_path') or 'N/A'}"
                    ),
                    (
                        "Status        : "
                        f"{port.get('status') or 'N/A'}"
                    ),
                    (
                        "Devices       : "
                        f"{len(port.get('devices', []))}"
                    ),
                ]
            )

            # --------------------------------------------------
            # Connected devices beneath this root USB path.
            # --------------------------------------------------

            for device_index, device in enumerate(
                port.get(
                    "devices",
                    [],
                ),
                start=1,
            ):

                lines.extend(
                    [
                        (
                            f"Device {device_index} Path : "
                            f"{device.get('usb_path') or 'N/A'}"
                        ),
                        (
                            f"Device {device_index}      : "
                            f"{device.get('product') or 'Unknown'}"
                        ),
                        (
                            f"Device {device_index} Type : "
                            f"{device.get('type') or 'UNKNOWN'}"
                        ),
                        (
                            f"Device {device_index} VID  : "
                            f"{device.get('vendor_id') or 'N/A'}"
                        ),
                        (
                            f"Device {device_index} PID  : "
                            f"{device.get('product_id') or 'N/A'}"
                        ),
                        (
                            f"Device {device_index} Driver: "
                            f"{device.get('drivers') or 'N/A'}"
                        ),
                    ]
                )

            storage_nodes = port.get(
                "storage_nodes",
                [],
            )

            if storage_nodes:

                lines.append(
                    "Storage Nodes : "
                    + ", ".join(
                        storage_nodes
                    )
                )

            else:

                lines.append(
                    "Storage Nodes : None"
                )

        return "\n".join(lines)

    # ==========================================================
    # PORT DRIVER HELPER
    # ==========================================================

    @staticmethod
    def _driver_for_port(
        port,
    ):
        """
        Return a combined driver summary for a USB port.

        Used mainly when the selected USB port is not a storage device.
        """

        drivers = []

        for device in port.get(
            "devices",
            [],
        ):

            device_drivers = (
                device.get(
                    "drivers",
                    ""
                )
                or ""
            )

            for driver in device_drivers.split(
                ","
            ):

                driver = driver.strip()

                if (
                    driver
                    and driver not in drivers
                ):

                    drivers.append(
                        driver
                    )

        return ",".join(
            drivers
        )

    # ==========================================================
    # USB TOPOLOGY HELPERS
    # ==========================================================

    @staticmethod
    def _root_usb_path(
        usb_path,
    ):
        """
        Return the top-level USB topology path.

        Examples:

            3-1
                -> 3-1

            3-1.1
                -> 3-1

            3-1.2.3
                -> 3-1

            1-2
                -> 1-2
        """

        return usb_path.split(
            ".",
            1,
        )[0]

    @staticmethod
    def _usb_path_sort_key(
        usb_path,
    ):
        """
        Generate a numeric sort key for Linux USB topology paths.

        Examples:

            1-1
            1-2
            3-1
            3-2

        Numeric sorting avoids lexical ordering issues such as:

            1-10 appearing before 1-2
        """

        numbers = re.findall(
            r"\d+",
            usb_path,
        )

        return tuple(
            int(number)
            for number in numbers
        )

    # ==========================================================
    # FORMATTING HELPERS
    # ==========================================================

    @staticmethod
    def _format_speed(
        speed,
    ):
        """
        Format USB negotiated speed.

        Linux sysfs commonly reports Mbps.

        Examples:
            1.5
            12
            480
            5000
            10000
        """

        if not speed:
            return "N/A"

        return f"{speed} Mbps"
