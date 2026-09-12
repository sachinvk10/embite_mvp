"""
EmbITE Action Registry

Maps DSL actions to their implementation functions.
"""


class ActionRegistry:
    """Registry for EmbITE DSL actions."""

    def __init__(self, system_info):
        self.actions = {
            "GET_HOSTNAME": system_info.get_hostname,
            "GET_IP_ADDRESS": system_info.get_ip_address,
            "GET_OS": system_info.get_os,
            "GET_KERNEL": system_info.get_kernel,
            "GET_ARCHITECTURE": system_info.get_architecture,
            "GET_MEMORY": system_info.get_memory,
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
