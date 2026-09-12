"""
EmbITE System Information Library

Provides reusable DUT system information actions.
"""


class SystemInfo:
    """System information actions for the DUT."""

    def __init__(self, command_executor):
        self.command_executor = command_executor

    def _execute(self, command, description):
        """
        Execute a system information command.

        Args:
            command: Command to execute on the DUT.
            description: Description used for error reporting.

        Returns:
            str: Command output.
        """
        output, error = self.command_executor.execute(command)

        if error:
            raise RuntimeError(
                f"Failed to get {description}: {error}"
            )

        return output

    def get_hostname(self):
        """Return DUT hostname."""
        return self._execute(
            "hostname",
            "DUT hostname",
        )

    def get_ip_address(self):
        """Return DUT IP address."""
        return self._execute(
            "hostname -I",
            "DUT IP address",
        )

    def get_os(self):
        """Return DUT operating system."""
        return self._execute(
            "grep '^PRETTY_NAME=' /etc/os-release | cut -d= -f2- | tr -d '\"'",
            "DUT operating system",
        )

    def get_kernel(self):
        """Return DUT kernel version."""
        return self._execute(
            "uname -r",
            "DUT kernel version",
        )

    def get_architecture(self):
        """Return DUT architecture."""
        return self._execute(
            "uname -m",
            "DUT architecture",
        )

    def get_memory(self):
        """Return DUT memory information."""
        return self._execute(
            "free -h",
            "DUT memory information",
        )
