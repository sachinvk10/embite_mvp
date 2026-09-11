class ShellDetector:
    """Detect the operating system and shell of the DUT."""

    def __init__(self, connection):
        self.connection = connection

    def detect(self):
        """Detect DUT OS and shell."""

        os_output, _ = self.connection.execute("uname -s")
        shell_output, _ = self.connection.execute("echo $SHELL")

        os_name = os_output.strip()
        shell_path = shell_output.strip()

        shell_name = shell_path.split("/")[-1] if shell_path else "unknown"

        return {
            "os": os_name,
            "shell": shell_name,
            "shell_path": shell_path,
        }