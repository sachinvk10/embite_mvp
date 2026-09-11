import paramiko

from board_action.connection import Connection


class SSHConnection(Connection):
    """SSH connection implementation for DUT communication."""

    def __init__(self, host, port, username, password=None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.client = None

    def connect(self):
        """Establish SSH connection to the DUT."""
        self.client = paramiko.SSHClient()

        self.client.set_missing_host_key_policy(
            paramiko.AutoAddPolicy()
        )

        self.client.connect(
            hostname=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
        )

        return True

    def execute(self, command):
        """Execute a command on the DUT."""
        if not self.is_connected():
            raise RuntimeError("SSH connection is not established.")

        stdin, stdout, stderr = self.client.exec_command(command)

        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()

        return output, error

    def disconnect(self):
        """Close the SSH connection."""
        if self.client:
            self.client.close()
            self.client = None

    def is_connected(self):
        """Return True if SSH connection is active."""
        if self.client is None:
            return False

        transport = self.client.get_transport()

        return transport is not None and transport.is_active()