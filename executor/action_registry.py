"""
EmbITE Action Registry

Maps DSL actions to their implementation functions.
"""


class ActionRegistry:
    """Registry for EmbITE DSL actions."""

    def __init__(self, system_info):
        self.actions = {
            "GET_HOSTNAME": system_info.get_hostname,
        }

    def get_action(self, action_name):
        """
        Return the callable associated with an action name.
        """
        action = self.actions.get(action_name)

        if action is None:
            raise ValueError(
                f"Unsupported EmbITE action: {action_name}"
            )

        return action
