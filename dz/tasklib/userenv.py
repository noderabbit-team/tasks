# Per-User environment / container handling

class UserEnv(object):
    """
    Represents an instance of a runtime environment for a specific user.
    """

    def __init__(self, username):
        self.username = username
        self.initialize()

    def initialize(self):
        """
        Ensure this UserEnv is ready to use, by creating any required system
        state such as users, containers, etc.
        """

    def open(self, filename, mode):
        """
        Work-alike function for the builtin python open(), but running within this
        user environment. Use this if you want to write a file as the environment's
        user.
        """
        pass


    #def subproc(self, command, null_stdin=True, ...)
