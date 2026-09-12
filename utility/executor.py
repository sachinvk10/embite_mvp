"""
EmbITE Test Executor

Executes parsed EmbITE DSL actions using the Action Registry.
"""


class TestExecutor:
    """Execute EmbITE DSL actions."""

    def __init__(self, action_registry):
        self.action_registry = action_registry

    def execute(self, actions):
        """
        Execute a list of EmbITE actions.

        Returns:
            list: Execution results for each action.
        """
        results = []

        for action_name in actions:
            try:
                action = self.action_registry.get_action(action_name)
                output = action()

                results.append(
                    {
                        "action": action_name,
                        "status": "PASS",
                        "result": output,
                    }
                )

            except Exception as exc:
                results.append(
                    {
                        "action": action_name,
                        "status": "FAIL",
                        "error": str(exc),
                    }
                )

        return results
