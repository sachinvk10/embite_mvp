"""
EmbITE Command Executor

Provides a generic command execution layer over a DUT connection.
"""


class CommandExecutor:
    """Execute commands on a DUT using an active connection."""

    def __init__(self, connection):
        self.connection = connection

    def execute(self, command):
        """
        Execute a command on the DUT.

        Returns:
            tuple: (output, error)
        """
        if not self.connection.is_connected():
            raise RuntimeError(
                "Cannot execute command: DUT connection is not established."
            )

        if not command or not command.strip():
            raise ValueError("Command cannot be empty.")

        return self.connection.execute(command)
