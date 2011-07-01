import re
import os
import shutil

from dz.tasklib import (taskconfig,
                        utils)


REGISTERED_HANDLERS = {}


def register_handler(handlercls):
    REGISTERED_HANDLERS[handlercls.vcs_type] = handlercls()


def get_handler(vcs_type):
    return REGISTERED_HANDLERS[vcs_type]


def get_all_handlers():
    return REGISTERED_HANDLERS.values()


class BaseVCSHandler(object):
    """
    Base class for a VCS-specific handler.

    Each handler is instantiated ONCE (upon registration) and thus is
    effectively a singleton.
    """

    def get_current_checkout_source_url(self):
        """
        Returns the source_code_url of the code currently checked out in the
        current working directory. If you cannot identify this, return None
        and the path will be cleared before an update is checked out.

        Override me if the VCS supports incrementally updating an existing
        checkout.
        """
        return None

    def fresh_clone(self, source_code_url, dest_dir, log_func):
        """
        Gets a fresh checkout from source_code_url and puts it in the
        current working directory.

        Override me.
        """
        raise NotImplementedError("Each VCS handler must implement "
                                  "fresh_clone.")

    def update_checkout(self, log_func):
        """
        Updates the checkout in the current working directory.

        Override me if updates are possible. If updates are not possible,
        ensure that self.get_current_checkout_source_url() always returns
        None.
        """
        raise NotImplementedError("This VCS handler doesn't seem to support "
                                  "updating an existing checkout. Its "
                                  "get_current_checkout_source_url function "
                                  "should be changed to return None in all "
                                  "cases, to force a fresh checkout.")

    def get_revision_info(self, checkout_path):
        """
        Get a human-readable message about the revision currently stored in
        `checkout_path`.
        """
        raise NotImplementedError("This VCS handlers doesn't support "
                                  "getting the current revision info.")

    def canonicalize_url(self, url):
        """
        Given a URL string, canonicalize it such that if two URLs a and b
        refer to the same resource, then canonicalize_url(a) ==
        canonicalize_url(b).

        If you can't make heads or tails of url, just return url.

        Default implementation makes sense for most HTTP-based repo URLs.
        """
        if not hasattr(url, "rstrip"):
            return url
        return url.rstrip("/")

    def checkout_latest_matching_version(self,
                                         source_code_url,
                                         dest_dir,
                                         log_func=None):
        """
        Ensure the latest version matching the provided criteria is checked
        out in dest_dir locally.

        :param source_code_url: URL of the repo to clone/checkout from.
                                This URL is not validated.
        :param dest_dir: Local path to checkout into. If this exists and
                         contains a previous checkout, the handler may use
                         the VCS to only download incremental updates.
        """
        if not log_func:

            def logprint(msg):
                print msg
            log_func = logprint

        # made dest_dir if not exists
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)

        if source_code_url.startswith(taskconfig.TEST_REPO_URL_PREFIX):
            suffix = source_code_url[len(taskconfig.TEST_REPO_URL_PREFIX):]
            suffix = suffix.lstrip("/")
            assert "/" not in suffix, "Bad test repo path."
            assert ".." not in suffix, "Bad test repo path."
            repourl = os.path.join(taskconfig.TEST_REPO_DIR, suffix)
        else:
            repourl = source_code_url

        cur_dir = os.getcwd()
        try:
            os.chdir(dest_dir)

            current_checkout_url = self.get_current_checkout_source_url()
            if self.canonicalize_url(current_checkout_url) != \
                   self.canonicalize_url(source_code_url):
                # URL has changed -- clear the directory
                os.chdir(cur_dir)
                shutil.rmtree(dest_dir)
                os.makedirs(dest_dir)
                os.chdir(dest_dir)

                if current_checkout_url is None:
                    msg = "Cloning your repository."
                else:
                    msg = "Repository URL has changed, making a fresh clone."
                log_func(msg)

                self.fresh_clone(source_code_url, log_func)
            else:
                self.update_checkout(log_func)

        finally:
            os.chdir(cur_dir)

    def run_cmd(self, cmd, log_func):
        """
        Run an external command, calling log_func to log output.

        :param cmd: a command in list form, e.g. ["git", "clone", "http://..."]
        :param log_func: a callable that takes a string.

        :returns: ``stdout, stderr, p`` (from utils.subproc)
        """

        # tweak env to avoid Git prompting for passwords
        os.environ['GIT_ASKPASS'] = '/bin/echo'

        log_func("Running %s..." % " ".join(cmd))
        output, stderr, p = utils.subproc(cmd, null_stdin=True)
        if p.returncode != 0:
            raise utils.ProjectConfigurationException(
                "Error running command %r:\n%s\n%s" % (
                    cmd, output, stderr))
        else:
            log_func("Command output:\n%s\n%s" % (output, stderr))

        return output, stderr, p


@register_handler
class GitHandler(BaseVCSHandler):
    vcs_type = "git"
    vcs_verbose_name = "Git"

    def get_current_checkout_source_url(self):
        if not os.path.exists(".git"):
            return None

        gitdir = os.path.abspath(".git")
        output, stderr, p = utils.subproc(["git",
                                           "--git-dir=%s" % gitdir,
                                           "remote", "show", "origin"],
                                          redir_stderr_to_stdout=True)
        if p.returncode != 0:
            raise utils.InfrastructureException(
                "Error trying to determine current remote URL for repo: %s"
                % output)

        prefix = "  Fetch URL: "
        for line in output.splitlines():
            if line.startswith(prefix):
                return line[len(prefix):].strip()

        raise utils.InfrastructureException("Could not find remote origin URL "
                                            "in git output:\n%s" % output)

    def fresh_clone(self, source_code_url, log_func):
        #log_func("Cloning Git repository.")
        self.run_cmd(["git", "clone", "--recursive", source_code_url, "."],
                     log_func)

    def update_checkout(self, log_func):
        self.run_cmd(["git", "pull"], log_func)

    def get_revision_info(self, checkout_path):
        return utils.local("(cd %s; git log -n 1)" % checkout_path)


@register_handler
class HgHandler(BaseVCSHandler):
    vcs_type = "hg"
    vcs_verbose_name = "Mercurial"

    def get_current_checkout_source_url(self):
        if not os.path.exists(".hg"):
            return None

        output, stderr, p = utils.subproc(["hg", "showconfig",
                                           "paths.default"])
        return output.strip()

    def fresh_clone(self, source_code_url, log_func):
        self.run_cmd(["hg", "clone", source_code_url, "."], log_func)

    def update_checkout(self, log_func):
        self.run_cmd(["hg", "pull"], log_func)

    def get_revision_info(self, checkout_path):
        return utils.local("(cd %s; hg log -l 1)" % checkout_path)



@register_handler
class SvnHandler(BaseVCSHandler):
    vcs_type = "svn"
    vcs_verbose_name = "Subversion"

    def get_current_checkout_source_url(self):
        if not os.path.exists(".svn"):
            return None

        output, stderr, p = utils.subproc(["svn", "info", "--xml", "."])
        url_line_re = re.compile(r'^\s*<url>(.+)</url>\s*$')
        for line in output.splitlines():
            m = url_line_re.match(line)
            if m:
                return m.group(1)
        return None

    def fresh_clone(self, source_code_url, log_func):
        self.run_cmd(["svn", "checkout", source_code_url, "."], log_func)

    def update_checkout(self, log_func):
        self.run_cmd(["svn", "up"], log_func)

    def get_revision_info(self, checkout_path):
        return utils.local("svn info %s" % checkout_path)
