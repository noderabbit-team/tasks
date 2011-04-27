from dz.tasklib import (utils, taskconfig)
import os
import pwd
import shutil
import tempfile
from cStringIO import StringIO

CONTAINER_BIND_DIRS = ('/usr', '/bin', '/lib', '/lib64', '/etc')


class AlreadyDestroyed(Exception):
    """Indicates that this UE has already been destroyed and cannot be
    destroyed again."""
    pass


class ErrorInsideEnvironment(Exception):
    """Indicates an error running something inside the UserEnv."""
    pass


class UserEnvFile(object):
    """
    Behaves like a file object, but instead of being directly mapped to a file
    it writes to that file from inside of a UserEnv.
    """

    def __init__(self, userenv, filename):
        self.stringio = StringIO()
        self.userenv = userenv
        self.filename = filename

    def read(self, *args, **kwargs):
        self.stringio.read(*args, **kwargs)

    def readlines(self, *args, **kwargs):
        self.stringio.readlines(*args, **kwargs)

    def write(self, *args, **kwargs):
        self.stringio.write(*args, **kwargs)

    def writelines(self, *args, **kwargs):
        self.stringio.writelines(*args, **kwargs)

    def seek(self, *args, **kwargs):
        self.stringio.seek(*args, **kwargs)

    def close(self):
        self.userenv.write_string_to_file(self.stringio.getvalue(), self.filename)
        self.userenv = None
        self.stringio.close()


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
        self.container_dir = tempfile.mkdtemp(prefix='ctr-%s-' % self.username)

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

        if p.returncode != 0:
            raise ErrorInsideEnvironment(("Command %r returned non-zero exit "
                                          "code %r.\nSTDERR:\n%s\nSTDOUT:\n%s")
                                         % (command_list,
                                            p.returncode,
                                            stderr, stdout))

        return stdout

    def open(self, filename, mode="r"):
        """
        Work-alike function for the builtin python open(), but running
        within this user environment. Use this if you want to write a file
        as the environment's user.

        :param filename: path to file within the container.
        """
        if mode == "w":
            # create a temp file that, when closed, copies into the env.
            return UserEnvFile(self, filename)

        elif mode == "r":
            # open the file as the env's user
            (stdout, stderr, p) = utils.local_privileged([
                "run_in_container", self.username, self.container_dir,
                "cat", filename],
                                                         return_details=True)
            if p.returncode != 0:
                raise OSError(stderr)

            return StringIO(stdout)

        else:
            raise ValueError("UserEnv.open does not support mode %s." % mode)

    def write_string_to_file(self, content, filename):
        """
        Write the provided content (a string) to the given filename
        (relative to the userenv's home). File will be owned by the
        userenv's user if it does not already exist.
        """
        (tmpfd, tmpfname) = tempfile.mkstemp(prefix="ctr-write-%s-" % self.username)
        tmpf = open(tmpfname, "w")
        tmpf.write(content)
        tmpf.close()
        utils.local_privileged(["move_into_container",
                                self.username,
                                self.container_dir,
                                tmpfname,
                                filename])

    def remove(self, filename):
        """
        Remove a file inside of the userenv.
        """
        (stdout, stderr, p) = utils.local_privileged(
            ["run_in_container", self.username, self.container_dir,
             "rm", filename], return_details=True)

        if p.returncode != 0:
            raise OSError(stdout + "\n" + stderr)

    def monkeypatch_pip_util_get_file_content(self):
        """Apply a monkeypatch to replace pip.util.get_file_content with
        an equivalent method that reads a file from inside this userenv."""
        import pip.util

        pip.util._ORIGINAL_get_file_content = pip.util.get_file_content

        # pip.util globals/imports
        import re
        import urllib
        import urllib2
        from pip.exceptions import InstallationError

        _scheme_re = re.compile(r'^(http|https|file):', re.I)
        _url_slash_drive_re = re.compile(r'/*([a-z])\|', re.I)

        def gfc_ue(url, comes_from=None):
            """Gets the content of a file; it may be a filename, file: URL, or
            http: URL.  Returns (location, content)"""
            match = _scheme_re.search(url)
            if match:
                scheme = match.group(1).lower()
                if (scheme == 'file' and comes_from
                    and comes_from.startswith('http')):
                    raise InstallationError(
                        'Requirements file %s references URL %s, which is local'
                        % (comes_from, url))
                if scheme == 'file':
                    path = url.split(':', 1)[1]
                    path = path.replace('\\', '/')
                    match = _url_slash_drive_re.match(path)
                    if match:
                        path = match.group(1) + ':' + path.split('|', 1)[1]
                    path = urllib.unquote(path)
                    if path.startswith('/'):
                        path = '/' + path.lstrip('/')
                    url = path
                else:
                    ## FIXME: catch some errors
                    resp = urllib2.urlopen(url)
                    return resp.geturl(), resp.read()

            f = self.open(url) ### This is the only change from stock
                               ### pip.util.get_file_content
            content = f.read()
            f.close()
            return url, content

        pip.util.get_file_content = gfc_ue

    def undo_monkeypatch_pip_util_get_file_content(self):
        """Undo the above monkeypatch."""
        import pip.util

        if not hasattr(pip.util, "_ORIGINAL_get_file_content"):
            raise ValueError("Error: monkeypatch not present on pip.util")

        pip.util.get_file_content = pip.util._ORIGINAL_get_file_content
        del pip.util._ORIGINAL_get_file_content
