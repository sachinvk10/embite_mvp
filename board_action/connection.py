from abc import ABC, abstractmethod


class Connection(ABC):
    """Generic interface for connecting to a DUT."""

    @abstractmethod
    def connect(self):
        """Establish connection to the DUT."""
        pass

    @abstractmethod
    def execute(self, command):
        """Execute a command on the DUT."""
        pass

    @abstractmethod
    def disconnect(self):
        """Close the DUT connection."""
        pass

    @abstractmethod
    def is_connected(self):
        """Return True if connected to the DUT."""
        pass