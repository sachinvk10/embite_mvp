"""
EmbITE MVP - Custom Framework Exceptions

File:
    utility/exceptions.py

Purpose:
    This module defines EmbITE-specific exception classes used across
    the framework.

    Custom exceptions allow the executor, logger, and main orchestration
    layer to distinguish between:

        - normal execution failures
        - intentional safety blocks
        - invalid framework/runtime states

Architecture:

    DSL API
        ↓
    Validation / Safety Check
        ↓
    Custom Exception
        ↓
    TestExecutor
        ↓
    Result Status
        ↓
    PASS / FAIL / BLOCKED


Why Custom Exceptions Are Needed
================================

A storage safety condition is not the same as a normal software failure.

Example:

    PARTITION_CREATE gpt 1 2G

If the selected device contains existing user data and:

    storage:
      safety:
        allow_overwrite: false

EmbITE should intentionally stop the operation.

That should be reported as:

    BLOCKED

not:

    FAIL

Because:
    - the framework behaved correctly
    - the device was protected
    - no destructive operation was performed
    - the user must explicitly enable overwrite if required


Current Exception Classes
=========================

BlockedActionError
    Used when an EmbITE action is intentionally prevented by a
    safety or policy condition.

    Typical cases:

        - existing data detected
        - overwrite disabled
        - multiple ambiguous storage devices
        - selected USB port has no storage
        - target device changed after USB_SELECT
        - required destructive prerequisite not satisfied
        - multiple partitions exist and no active partition is known


Future exceptions may be added here, for example:

    ConfigurationError
    ConnectionError
    DeviceDiscoveryError
    ValidationError
    UnsupportedActionError

Keeping custom framework exceptions in one module makes the
architecture easier to maintain and extend.
"""


class EmbITEError(Exception):
    """
    Base exception for EmbITE-specific framework errors.

    Purpose:
        Provides a common parent class for all custom EmbITE exceptions.

    Future code can catch all framework-specific errors using:

        except EmbITEError:
            ...

    without catching unrelated Python exceptions.
    """

    pass


class BlockedActionError(EmbITEError):
    """
    Raised when an EmbITE DSL action is intentionally blocked.

    This exception represents a controlled safety or policy condition,
    not an unexpected software failure.

    Example:

        Device:
            /dev/sda

        Existing filesystem:
            ext4

        Configuration:
            allow_overwrite: false

        Requested DSL:

            PARTITION_CREATE gpt 1 2G

    Result:

        raise BlockedActionError(
            "Device contains existing data. "
            "Destructive operation is blocked."
        )

    The TestExecutor should convert this exception into:

        {
            "status": "BLOCKED",
            ...
        }

    rather than:

        {
            "status": "FAIL",
            ...
        }


    Typical Usage
    =============

    Storage safety:

        if existing_content and not allow_overwrite:

            raise BlockedActionError(
                "Existing storage content detected."
            )


    USB selection safety:

        if multiple_storage_devices:

            raise BlockedActionError(
                "Multiple storage devices detected."
            )


    Runtime ownership safety:

        if selected_device_no_longer_matches_usb_port:

            raise BlockedActionError(
                "Selected device changed. "
                "Run USB_DETECT and USB_SELECT again."
            )
    """

    pass
