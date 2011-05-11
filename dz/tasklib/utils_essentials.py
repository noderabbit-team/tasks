import os
import subprocess
import tempfile

import taskconfig


class ExternalServiceException(Exception):
    """
    Exception indicating a problem outside of DjangoZoom, such as failure
    to fetch an externally-hosted required module.
    """


def subproc(command, null_stdin=True, stdin_string=None,
            redir_stderr_to_stdout=False):
    """
    Run a command locally, using the subprocess module and optionally
    providing a closed stdin filehandle.

    Unlike the fabric-based `local` function also in this module, subproc()
    will capture both stdout and stderr, and will not issue a warning or
    error if the underlying command fails. Therefore, you probably want to
    use check p.returncode to verify the command exited successfully.

    :param stdin_string: if provided, sends the given string on stdin to the
    subprocess.

    :returns: stdout, stderr, p: output strings and Popen obj of the command.
    """
    p_args = dict(shell=isinstance(command, basestring),
                  stdout=subprocess.PIPE,
                  stderr=subprocess.PIPE)

    tempfile_name = None

    if stdin_string:
        # must be written to a temp file (or at least something with a
        # filehandle) so can redirect.
        (fd, tempfile_name) = tempfile.mkstemp(prefix='tmp_subproc')
        f = file(tempfile_name, "w")
        f.write(stdin_string)
        f.close()

        p_args["stdin"] = file(tempfile_name)

    elif null_stdin:
        p_args["stdin"] = open("/dev/null")

    if redir_stderr_to_stdout:
        p_args["stderr"] = subprocess.STDOUT

    #print "subprocess.Popen(%r, %r)" % (command, p_args)
    p = subprocess.Popen(command, **p_args)
    (stdout, stderr) = p.communicate()

    if tempfile_name:
        os.remove(tempfile_name)

    return stdout, stderr, p


def privileged_program_cmd(cmdargs):
    assert isinstance(cmdargs, list)
    privileged_program = cmdargs.pop(0)
    assert "/" not in privileged_program, ("Privileged programs can only "
                                           "be run from the designated "
                                           "directory. Paths are not allowed.")
    privileged_program_path = os.path.join(taskconfig.PRIVILEGED_PROGRAMS_PATH,
                                           privileged_program)
    assert os.path.isfile(privileged_program_path), (
        ("Command %r is not available as a privileged program "
         "(no privileged file found).") % privileged_program)
    fullcmd = ["sudo", privileged_program_path] + cmdargs
    return fullcmd


def local_privileged(cmdargs, return_details=False, stdin_string=None):
    fullcmd = privileged_program_cmd(cmdargs)
    #print "Running local_privileged command: %r" % fullcmd
    stdout, stderr, p = subproc(fullcmd, null_stdin=True,
                                stdin_string=stdin_string)
    if return_details:
        return stdout, stderr, p
    else:
        if p.returncode != 0:
            raise ExternalServiceException((
                "Error attempting to run LP command %r. "
                "Output:\n %s\n%s") % (cmdargs, stdout, stderr))

        return stdout
