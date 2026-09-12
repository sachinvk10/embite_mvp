class ActionRegistry:
    """Maps EmbITE DSL actions to framework implementation methods."""

    def __init__(self, board_actions):
        self.board_actions = board_actions

        self.actions = {
            "GET_HOSTNAME": self.board_actions.get_hostname,
            "GET_IP_ADDRESS": self.board_actions.get_ip_address,
            "GET_OS": self.board_actions.get_os,
            "GET_KERNEL": self.board_actions.get_kernel,
            "GET_ARCHITECTURE": self.board_actions.get_architecture,
            "GET_MEMORY": self.board_actions.get_memory,
        }

    def get_action(self, action_name):
        action = self.actions.get(action_name)

        if action is None:
            raise ValueError(
                f"Unsupported EmbITE action: {action_name}"
            )

        return action
