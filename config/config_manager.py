from pathlib import Path

import yaml


class ConfigManager:
    """Loads and provides access to EmbITE configuration."""

    def __init__(self, config_file):
        self.config_file = Path(config_file)
        self.config = {}

    def load(self):
        """Load configuration from YAML file."""
        if not self.config_file.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_file}"
            )

        with self.config_file.open("r", encoding="utf-8") as file:
            self.config = yaml.safe_load(file) or {}

        return self.config

    def get_dut_config(self):
        """Return DUT configuration."""
        return self.config.get("dut", {})