from dz.tasklib import (utils, taskconfig)
import os
import pwd
import shutil
import tempfile

CONTAINER_BIND_DIRS = ('/usr', '/bin', '/lib', '/lib64', '/etc')


class AlreadyDestroyed(Exception):
    """Indicates that this UE has already been destroyed and cannot be
    destroyed again."""
    pass


class UserEnv(object):
    """
    Represents an instance of a runtime environment for a specific user.
    """

    def __init__(self, username):
        self.username = username
        self.cust_dir = os.path.join(taskconfig.NR_CUSTOMER_DIR, username)
        self.container_dir = None
        self.destroyed = False
        self.initialize()

    def initialize(self):
        """
        Ensure this UserEnv is ready to use, by creating any required system
        state such as users, containers, etc.
        """
        self.container_dir = tempfile.mkdtemp(prefix='ctr-%s' % self.username)

        # must be 755 for many in-container programs to work
        os.chmod(self.container_dir, 0755)

        # chown to username
        utils.local_privileged(["project_chown", self.username,
                                self.container_dir])

        # bind directories
        for dirname in CONTAINER_BIND_DIRS:
            utils.local_privileged(["mount_bind", dirname,
                                    os.path.join(self.container_dir,
                                                 dirname.lstrip("/"))])

    def destroy(self):
        if self.destroyed:
            raise AlreadyDestroyed()

        self.destroyed = True

        for dirname in CONTAINER_BIND_DIRS:
            utils.local_privileged(["umount",
                                    os.path.join(self.container_dir,
                                                 dirname.lstrip("/"))])
        # chown to me
        utils.local_privileged(["project_chown",
                                pwd.getpwuid(os.geteuid()).pw_name,
                                self.container_dir])
        shutil.rmtree(self.container_dir)

    def subproc(self, command_list):
        """
        Run a subprocess under this userenv, and return the output.
        The command for the subprocess must be a list; the subprocess is not
        passed through a shell. This is for simplicity/security.
        """
        assert type(command_list) == list, ("UserEnv.subproc's command_list "
                                            "argument must be a list.")
        (stdout, stderr, p) = utils.local_privileged([
            "run_in_container", self.username, self.container_dir,
            ] + command_list,
            return_details=True)

        return stdout

    def open(self, filename, mode):
        """
        Work-alike function for the builtin python open(), but running
        within this user environment. Use this if you want to write a file
        as the environment's user.

        :param filename: path to file within the container.
        """
        pass
