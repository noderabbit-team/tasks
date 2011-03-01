import ast
import os
import re

import taskconfig
from dz.tasklib import utils
from dz.tasklib.common_steps import checkout_code


def get_settings_files(zoomdb, repodir):
    settings_files = []
    py_files = []

    for root, dirnames, filenames in os.walk(repodir):
        for fn in filenames:

            full_filepath = os.path.join(root, fn)
            repo_filepath = full_filepath[len(repodir):].lstrip("/")

            if (fn.endswith("settings.py")
                or (fn.startswith("settings")
                    and fn.endswith(".py"))):
                #job.log("Possible settings file: %s" % (repo_filepath))

                try:
                    parsetree = ast.parse(file(full_filepath).read())
                except:
                    zoomdb.log("Note -- ignoring possible settings " +
                               " file %s due to parse error." % repo_filepath)
                    continue

                settings_files.append((repo_filepath, parsetree))

            if fn.endswith(".py"):
                py_files.append(repo_filepath)

    # sort settings_files by shortest-first
    settings_files.sort(key=lambda x: len(x[0]))

    return (settings_files, py_files)


def extract_string_setting(parsetree, setting_name):
    for part in parsetree.body:
        # look for assignments
        if not isinstance(part, ast.Assign):
            continue

        target0 = part.targets[0]

        if not isinstance(target0, ast.Name):
            continue

        setname = target0.id

        if isinstance(part.value, ast.Name):
            setvalue = part.value.id
        elif isinstance(part.value, ast.Str):
            setvalue = part.value.s
        else:
            #logfunc("Ignored setting: %s = %s" % (setname, part.value))
            continue

        if setname == setting_name:
            return setvalue


def guess_from_settings(zoomdb, path, parsetree, py_files,
                        is_primary=False):
    """
    Guess the following project settings based on the repo layout:

    1. base_python_package
    2. django_project_name <--- will become unused - just need settings module
    3. django_settings_module
    4. additional_python_path_dirs

    """
    guesses = []

    def _addguess(fld, val):
        guesses.append(dict(field=fld,
                            value=val,
                            is_primary=is_primary,
                            basis=path))

    root_urlconf = extract_string_setting(parsetree, "ROOT_URLCONF")
    zoomdb.log("Setting: BASIS: %s ROOT_URLCONF = %s" % (
            path, root_urlconf,))

    if not root_urlconf:
        return []

    root_urlconf_parts = root_urlconf.split(".")

    # STRATEGY 1: look for the urlconf nested somewhere in the tree
    # e.g. if it's my.app.urls, look for *my/app/urls.py"
    root_urlconf_filesuffix = "/".join(root_urlconf_parts) + ".py"

    for found_url in filter(lambda f: f.endswith(root_urlconf_filesuffix),
                            py_files):

        pydir = found_url[:-len(root_urlconf_filesuffix)].rstrip("/")
        # pydir will be e.g. path/to

        # print "&&& FOUND suffix %s in  %s --> pydir=%s" % (
        #     root_urlconf_filesuffix,
        #     found_url,
        #     pydir)

        # also put the path that contains urls.py into
        # additional_python_path_dirs
        if len(root_urlconf_parts) > 1:
            project_base_dir = os.path.join(pydir,
                                            "/".join(root_urlconf_parts[0:-1]))
            addl_pydirs = pydir + "\n" + project_base_dir
        else:
            addl_pydirs = pydir

        _addguess("base_python_package", "")
        _addguess("additional_python_path_dirs", addl_pydirs)

        # determine path to this settings module
        if path.startswith(pydir):
            shortpath = path[len(pydir):][:-3].lstrip("/")
            _addguess("django_settings_module",
                      shortpath.replace("/", "."))
        else:
            _addguess("django_settings_module",
                      os.path.join(pydir, "settings.py"))

        return guesses

    # STRATEGY 2: see if there's a mysite.urls (or whatever) file somewhere
    # in the project... creep up the chain:
    # 0: foo.bar.urls
    # 1: bar.urls (foo = basepkg)
    # 2: urls (foo.bar = basepkg)
    for divide_at in xrange(len(root_urlconf_parts)):
        base_part = ".".join(root_urlconf_parts[:divide_at])
        #repo_part = ".".join(root_urlconf_parts[divide_at:])

        repo_path = os.path.join(*root_urlconf_parts[divide_at:]) + ".py"

        if repo_path in py_files:
            # print "FOUND: base=%s repomod=%s repofile=%s" % (base_part,
            #                                                  repo_part,
            #                                                  repo_path)
            _addguess("base_python_package", base_part)
            _addguess("django_settings_module",
                      base_part + "." + path.replace("/", ".")[:-3])
            # no extra python path dirs needed
            return guesses

    # just the base case:
    root_urlconf_file = root_urlconf.replace(".", "/") + ".py"
    matching_files = [f for f in py_files if f.endswith(root_urlconf_file)]

    for mf in matching_files:
        zoomdb.log("MATCHING URL FILE: %s" % mf)

    _addguess("django_settings_module", path.rsplit("/", 1)[-1][:-3])

    urlmod_parts = root_urlconf.rsplit(".", 1)

    # if len(urlmod_parts) != 2:
    #   logfunc("Unexpected single-part ROOT_URLCONF value: %r" % root_urlconf)
    #   continue

    # is the ROOT_URLCONF module directly accessible with
    # only the repo root on the search path?
    # Cool, then there's no base package.
    if (os.path.exists(root_urlconf.replace(".",  "/") + ".py")
        or os.path.exists(root_urlconf.replace(".", "/") + "/__init__.py")):
        base_pkg = ""

    # maybe it's in the root and implies a base_pkg?
    elif os.path.exists(urlmod_parts[-1] + ".py"):
        base_pkg = urlmod_parts[0]

    # OK, if that didn't work it must be somewhere on
    # the search path. That's too complicated to deal
    # with right now.
    else:
        base_pkg = None

    if base_pkg is not None:
        #logfunc("Guessed base package: %s" % base_pkg)
        _addguess("base_python_package", base_pkg)

    return guesses


def inspect_code_settings(zoomdb, opts):
    CO_DIR = opts["CO_DIR"]

    (settings_files, py_files) = get_settings_files(zoomdb, CO_DIR)

    os.chdir(CO_DIR)

    have_some_guesses = False

    for i, (path, parsetree) in enumerate(settings_files):
        is_primary = not have_some_guesses

        guesses = guess_from_settings(zoomdb,
                                      path,
                                      parsetree,
                                      py_files,
                                      is_primary)
        for g in guesses:
            have_some_guesses = True
            zoomdb.add_config_guess(**g)

    if have_some_guesses:
        # if we made any successful guesses at all, let's also guess a title
        t = "Untitled Project"
        reg = re.compile(r'[/\.]')
        for part in reversed(reg.split(opts["SRC_URL"])):
            if not part.startswith("git"):
                t = part.replace("_", " ").title()
                break

        zoomdb.add_config_guess("title", t,
                                is_primary=True,
                                basis="")


def check_repo(zoomdb, app_id, src_url):

    opts = {"CO_DIR":
                os.path.join(taskconfig.NR_CUSTOMER_DIR, app_id, "src"),
            "SRC_URL": src_url,
            "APP_ID": app_id,
            }

    utils.run_steps(zoomdb, opts, (
            checkout_code,
            inspect_code_settings))
