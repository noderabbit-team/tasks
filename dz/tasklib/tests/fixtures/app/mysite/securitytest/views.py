from django.http import HttpResponse
import subprocess


def _subproc(command):
    """
    Run a shell command and return its output.
    """
    p = subprocess.Popen(command, stdin=open("/dev/null"),
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdout, stderr) = p.communicate()
    return stdout + stderr


def index(request):
    result = ["SECURITY TEST RESULTS"]

    result.append("whoami: " + _subproc('whoami').strip())
    result.append("ls /: " + ",".join(sorted(
        _subproc(['ls', '/']).splitlines())))
    return HttpResponse("\n".join(result), mimetype="text/plain")
