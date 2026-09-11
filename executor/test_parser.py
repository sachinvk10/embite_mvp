"""
EmbITE Test Parser

Reads .tst files and converts them into EmbITE actions.
"""


class TestParser:
    """Parser for EmbITE .tst files."""

    def parse(self, test_file):
        """
        Parse a .tst file and return a list of actions.

        Blank lines and comment lines starting with # are ignored.
        """
        actions = []

        with open(test_file, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()

                if not line:
                    continue

                if line.startswith("#"):
                    continue

                actions.append(line)

        return actions
