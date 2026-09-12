"""
EmbITE Board Actions

Common DUT abstraction for the EmbITE framework.

Current MVP capabilities:
- SSH connection
- Generic command execution
- DUT OS detection
- Shell detection
- System information DSL APIs

Serial connection support will be added next.
"""

import paramiko


class BoardActions:
    """Common interface between EmbITE and the DUT."""

    def __init__(self, dut_config, password=None):
        self.dut_config = dut_config
        self.connection_config = dut_config.get("connection", {})

        self.password = password

        self.connection_type = self.connection_config.get("type")

        self.client = None

        self.environment = {}

    # ==========================================================
    # CONNECTION
    # ==========================================================

    def connect(self):
        """
        Connect to the DUT using the configured connection type.
        """

        if self.connection_type == "ssh":
            return self.connect_ssh()

        raise ValueError(
            f"Unsupported connection type: {self.connection_type}"
        )

    def connect_ssh(self):
        """
        Establish an SSH connection to the DUT.
        """

        host = self.connection_config.get("host")
        port = self.connection_config.get("port", 22)
        username = self.connection_config.get("username")

        if not host:
            raise ValueError("SSH host is not configured.")

        if not username:
            raise ValueError("SSH username is not configured.")

        self.client = paramiko.SSHClient()

        self.client.set_missing_host_key_policy(
            paramiko.AutoAddPolicy()
        )

        self.client.connect(
            hostname=host,
            port=port,
            username=username,
            password=self.password,
        )

        return True

    def disconnect(self):
        """
        Disconnect from the DUT.
        """

        if self.client:
            self.client.close()
            self.client = None

    def reconnect(self):
        """
        Disconnect and reconnect to the DUT.
        """

        self.disconnect()

        return self.connect()

    def is_connected(self):
        """
        Return True if the DUT connection is active.
        """

        if self.client is None:
            return False

        transport = self.client.get_transport()

        return (
            transport is not None
            and transport.is_active()
        )

    # ==========================================================
    # GENERIC COMMAND EXECUTION
    # ==========================================================

    def send_command(self, command, timeout=None):
        """
        Execute a command on the DUT.

        Returns:
            tuple:
                stdout, stderr
        """

        self._validate_connection()

        if not command or not command.strip():
            raise ValueError(
                "Command cannot be empty."
            )

        stdin, stdout, stderr = (
            self.client.exec_command(
                command,
                timeout=timeout,
            )
        )

        output = (
            stdout.read()
            .decode("utf-8", errors="replace")
            .strip()
        )

        error = (
            stderr.read()
            .decode("utf-8", errors="replace")
            .strip()
        )

        return output, error

    # ==========================================================
    # DUT ENVIRONMENT DETECTION
    # ==========================================================

    def detect_environment(self):
        """
        Detect DUT OS, shell, and shell path.
        """

        operating_system = self.detect_os()
        shell_path = self.detect_shell_path()
        shell = self.detect_shell()

        self.environment = {
            "os": operating_system,
            "shell": shell,
            "shell_path": shell_path,
        }

        return self.environment

    def detect_os(self):
        """
        Detect operating system running on DUT.
        """

        output, error = self.send_command(
            "uname -s"
        )

        if error:
            raise RuntimeError(
                f"Failed to detect DUT OS: {error}"
            )

        return output

    def detect_shell_path(self):
        """
        Detect the default shell path on DUT.
        """

        output, error = self.send_command(
            'printf "%s" "$SHELL"'
        )

        if error:
            raise RuntimeError(
                f"Failed to detect DUT shell path: {error}"
            )

        if output:
            return output

        # Fallback for environments where $SHELL is not set.
        output, error = self.send_command(
            "getent passwd $(whoami) "
            "| cut -d: -f7"
        )

        if error:
            raise RuntimeError(
                f"Failed to detect DUT shell path: {error}"
            )

        return output

    def detect_shell(self):
        """
        Detect the shell name on DUT.
        """

        shell_path = self.detect_shell_path()

        if not shell_path:
            return "unknown"

        return shell_path.rsplit("/", 1)[-1]

    # ==========================================================
    # SYSTEM INFORMATION DSL ACTIONS
    # ==========================================================

    def get_hostname(self):
        """
        DSL: GET_HOSTNAME
        """

        return self._execute_value(
            "hostname",
            "DUT hostname",
        )

    def get_ip_address(self):
        """
        DSL: GET_IP_ADDRESS
        """

        return self._execute_value(
            "hostname -I",
            "DUT IP address",
        )

    def get_os(self):
        """
        DSL: GET_OS
        """

        return self._execute_value(
            "grep '^PRETTY_NAME=' /etc/os-release "
            "| cut -d= -f2- "
            "| tr -d '\"'",
            "DUT operating system",
        )

    def get_kernel(self):
        """
        DSL: GET_KERNEL
        """

        return self._execute_value(
            "uname -r",
            "DUT kernel version",
        )

    def get_architecture(self):
        """
        DSL: GET_ARCHITECTURE
        """

        return self._execute_value(
            "uname -m",
            "DUT architecture",
        )

    def get_memory(self):
        """
        DSL: GET_MEMORY
        """

        return self._execute_value(
            "free -h",
            "DUT memory information",
        )

    # ==========================================================
    # INTERNAL HELPERS
    # ==========================================================

    def _validate_connection(self):
        """
        Ensure a DUT connection is active.
        """

        if not self.is_connected():
            raise RuntimeError(
                "DUT connection is not established."
            )

    def _execute_value(
        self,
        command,
        description,
    ):
        """
        Execute a command used by a DSL API and return stdout.
        """

        output, error = self.send_command(
            command
        )

        if error:
            raise RuntimeError(
                f"Failed to get {description}: {error}"
            )

        return output
