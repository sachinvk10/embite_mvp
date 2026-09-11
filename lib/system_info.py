"""
EmbITE System Information Library

Provides reusable DUT system information actions.
"""


class SystemInfo:
    """System information actions for the DUT."""

    def __init__(self, command_executor):
        self.command_executor = command_executor

    def get_hostname(self):
        """
        Get the hostname of the DUT.

        Returns:
            str: DUT hostname
        """
        output, error = self.command_executor.execute("hostname")

        if error:
            raise RuntimeError(
                f"Failed to get DUT hostname: {error}"
            )

        return output
