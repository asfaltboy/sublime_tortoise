import importlib
import os.path
import re
import subprocess
import threading
import time

import sublime
import sublime_plugin


PACKAGE_ROOT = ".".join(__name__.split(".")[:-1])  # last dot leads to the current module

try:
    search_file = importlib.__import__(PACKAGE_ROOT + ".utils", globals(), locals(), ["search_file"]).search_file
except ImportError:
    from utils import search_file


class RepositoryNotFoundError(Exception):
    pass


class NotFoundError(Exception):
    pass


file_status_cache = {}


class TortoiseCommand():
    def get_path(self, paths):
        if paths is True:
            return self.window.active_view().file_name()
        return paths[0] if paths else self.window.active_view().file_name()

    def get_vcs(self, path):
        settings = sublime.load_settings('Tortoise.sublime-settings')

        if path is None:
            raise NotFoundError('Unable to run commands on an unsaved file')
        vcs = None

        try:
            vcs = TortoiseSVN(settings.get('svn_tortoiseproc_path'), path)
        except (RepositoryNotFoundError):
            pass

        try:
            vcs = TortoiseGit(settings.get('git_tortoiseproc_path'), path)
        except (RepositoryNotFoundError):
            pass

        try:
            vcs = TortoiseHg(settings.get('hg_hgtk_path'), path)
        except (RepositoryNotFoundError):
            pass

        if vcs is None:
            raise NotFoundError('The current file does not appear to be in an ' +
                                'SVN, Git or Mercurial working copy')

        return vcs

    def menus_enabled(self):
        settings = sublime.load_settings('Tortoise.sublime-settings')
        return settings.get('enable_menus', True)


def handles_not_found(fn):
    def handler(self, *args, **kwargs):
        try:
            fn(self, *args, **kwargs)
        except (NotFoundError) as exception:
            sublime.error_message('Tortoise: ' + str(exception))
    return handler


def invisible_when_not_found(fn):
    def handler(self, *args, **kwargs):
        try:
            res = fn(self, *args, **kwargs)
            if res is not None:
                return res
            return True
        except (NotFoundError):
            return False
    return handler


class TortoiseExploreCommand(sublime_plugin.WindowCommand, TortoiseCommand):
    @handles_not_found
    def run(self, paths=None):
        path = self.get_path(paths)
        self.get_vcs(path).explore(path if paths else None)


class TortoiseCommitCommand(sublime_plugin.WindowCommand, TortoiseCommand):
    @handles_not_found
    def run(self, paths=None):
        path = self.get_path(paths)
        self.get_vcs(path).commit(path if os.path.isdir(path) else None)

    @invisible_when_not_found
    def is_visible(self, paths=None):
        if not self.menus_enabled():
            return False
        path = self.get_path(paths)
        if not path:
            return False
        self.get_vcs(path)
        return os.path.isdir(path)


class TortoiseStatusCommand(sublime_plugin.WindowCommand, TortoiseCommand):
    @handles_not_found
    def run(self, paths=None):
        path = self.get_path(paths)
        self.get_vcs(path).status(path if os.path.isdir(path) else None)

    @invisible_when_not_found
    def is_visible(self, paths=None):
        if not self.menus_enabled():
            return False
        path = self.get_path(paths)
        if not path:
            return False
        self.get_vcs(path)
        return os.path.isdir(path)


class TortoiseSyncCommand(sublime_plugin.WindowCommand, TortoiseCommand):
    @handles_not_found
    def run(self, paths=None):
        path = self.get_path(paths)
        self.get_vcs(path).sync(path if os.path.isdir(path) else None)

    @invisible_when_not_found
    def is_visible(self, paths=None):
        if not self.menus_enabled():
            return False
        path = self.get_path(paths)
        if not path:
            return False
        self.get_vcs(path)
        return os.path.isdir(path)


class TortoiseLogCommand(sublime_plugin.WindowCommand, TortoiseCommand):
    @handles_not_found
    def run(self, paths=None):
        path = self.get_path(paths)
        self.get_vcs(path).log(path if paths else None)

    @invisible_when_not_found
    def is_visible(self, paths=None):
        if not self.menus_enabled():
            return False
        path = self.get_path(paths)
        vcs = self.get_vcs(path)
        if os.path.isdir(path):
            return True
        return path and vcs.get_status(path) in \
            ['A', '', 'M', 'R', 'C', 'U']

    @invisible_when_not_found
    def is_enabled(self, paths=None):
        path = self.get_path(paths)
        if os.path.isdir(path):
            return True
        return path and self.get_vcs(path).get_status(path) in \
            ['', 'M', 'R', 'C', 'U']


class TortoiseBlameCommand(sublime_plugin.WindowCommand, TortoiseCommand):
    @handles_not_found
    def run(self, paths=None):
        path = self.get_path(paths)
        self.get_vcs(path).blame(path if paths else None)

    @invisible_when_not_found
    def is_visible(self, paths=None):
        if not self.menus_enabled():
            return False
        path = self.get_path(paths)
        if os.path.isdir(path):
            return False
        vcs = self.get_vcs(path)
        return path and vcs.get_status(path) in \
            ['A', '', 'M', 'R', 'C', 'U']

    @invisible_when_not_found
    def is_enabled(self, paths=None):
        path = self.get_path(paths)
        if os.path.isdir(path):
            return False
        return path and self.get_vcs(path).get_status(path) in \
            ['A', '', 'M', 'R', 'C', 'U']


class TortoiseDiffCommand(sublime_plugin.WindowCommand, TortoiseCommand):
    @handles_not_found
    def run(self, paths=None):
        path = self.get_path(paths)
        self.get_vcs(path).diff(path if paths else None)

    @invisible_when_not_found
    def is_visible(self, paths=None):
        if not self.menus_enabled():
            return False
        path = self.get_path(paths)
        vcs = self.get_vcs(path)
        if os.path.isdir(path):
            return True
        return vcs.get_status(path) in \
            ['A', '', 'M', 'R', 'C', 'U']

    @invisible_when_not_found
    def is_enabled(self, paths=None):
        path = self.get_path(paths)
        if os.path.isdir(path):
            return True
        vcs = self.get_vcs(path)
        if isinstance(vcs, TortoiseHg):
            return vcs.get_status(path) in ['M']
        else:
            return vcs.get_status(path) in ['A', 'M', 'R', 'C', 'U']


class TortoiseAddCommand(sublime_plugin.WindowCommand, TortoiseCommand):
    @handles_not_found
    def run(self, paths=None):
        path = self.get_path(paths)
        self.get_vcs(path).add(path)

    @invisible_when_not_found
    def is_visible(self, paths=None):
        if not self.menus_enabled():
            return False
        path = self.get_path(paths)
        return self.get_vcs(path).get_status(path) in ['D', '?']


class TortoiseRemoveCommand(sublime_plugin.WindowCommand, TortoiseCommand):
    @handles_not_found
    def run(self, paths=None):
        path = self.get_path(paths)
        self.get_vcs(path).remove(path)

    @invisible_when_not_found
    def is_visible(self, paths=None):
        if not self.menus_enabled():
            return False
        path = self.get_path(paths)
        return self.get_vcs(path).get_status(path) in \
            ['A', '', 'M', 'R', 'C', 'U']

    @invisible_when_not_found
    def is_enabled(self, paths=None):
        path = self.get_path(paths)
        if os.path.isdir(path):
            return True
        return self.get_vcs(path).get_status(path) in ['']


class TortoiseRevertCommand(sublime_plugin.WindowCommand, TortoiseCommand):
    @handles_not_found
    def run(self, paths=None):
        path = self.get_path(paths)
        self.get_vcs(path).revert(path)

    @invisible_when_not_found
    def is_visible(self, paths=None):
        if not self.menus_enabled():
            return False
        path = self.get_path(paths)
        return self.get_vcs(path).get_status(path) in \
            ['A', '', 'M', 'R', 'C', 'U']

    @invisible_when_not_found
    def is_enabled(self, paths=None):
        path = self.get_path(paths)
        if os.path.isdir(path):
            return True
        return self.get_vcs(path).get_status(path) in \
            ['A', 'M', 'R', 'C', 'U']


class ForkGui():
    def __init__(self, cmd, cwd):
        subprocess.Popen(
            cmd, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=cwd)


class Tortoise():
    def find_root(self, name, path, find_first=True):
        root_dir = None
        last_dir = None
        cur_dir = path if os.path.isdir(path) else os.path.dirname(path)
        while cur_dir != last_dir:
            if root_dir is not None and not os.path.exists(os.path.join(
                    cur_dir, name)):
                break
            if os.path.exists(os.path.join(cur_dir, name)):
                root_dir = cur_dir
                if find_first:
                    break
            last_dir = cur_dir
            cur_dir = os.path.dirname(cur_dir)

        if root_dir is None:
            raise RepositoryNotFoundError('Unable to find ' + name +
                                          ' directory')
        self.root_dir = root_dir

    def set_binary_path(self, path_suffix, binary_name, setting_name):
        root_drive = os.path.expandvars('%HOMEDRIVE%\\')

        possible_dirs = (
            os.environ.get("ProgramFiles(x86)", os.environ.get("ProgramFiles", '')),
        )

        # suggest user a search before starting it (available after ver 2187)
        # ver = int(sublime.version())
        # if ver >= 2187:
        #     search = sublime.ok_cancel_dialog('Unable to find ' +
        #                         self.__class__.__name__ + '.\n\n' +
        #                         'Would you like us to search for it in ' +
        #                         root_drive + '?')
        #     if search:
        # self.path = search_file(os.path.split(path_suffix)[-1], root_drive)
        # if self.path:
        #     return

        self.path = None
        normal_path = root_drive + possible_dirs[0] + path_suffix
        raise NotFoundError('Unable to find ' + self.__class__.__name__ +
                            '.\n\nPlease add the path to ' + binary_name +
                            ' to the setting "' + setting_name + '" in "' +
                            sublime.packages_path() +
                            '\\Tortoise\\Tortoise.sublime-settings".\n\n' +
                            'Example:\n\n' + '{"' + setting_name + '": r"' +
                            normal_path + '"}')

    def explore(self, path=None):
        if path is None:
            ForkGui('explorer.exe "' + self.root_dir + '"', None)
        else:
            ForkGui('explorer.exe "' + os.path.dirname(path) + '"', None)

    def process_status(self, vcs, path):
        global file_status_cache
        settings = sublime.load_settings('Tortoise.sublime-settings')
        if path in file_status_cache and file_status_cache[path]['time'] > \
                time.time() - settings.get('cache_length'):
            if settings.get('debug'):
                print('Fetching cached status for %s' % path)
            return file_status_cache[path]['status']

        if settings.get('debug'):
            start_time = time.time()

        status = None
        try:
            status = vcs.check_status(path)
        except (Exception) as exception:
            sublime.error_message(str(exception))

        file_status_cache[path] = {
            'time': time.time() + settings.get('cache_length'),
            'status': status
        }

        if settings.get('debug'):
            print('Fetching status for %s in %s seconds' % (path,
                  str(time.time() - start_time)))

        return status


class TortoiseProc(Tortoise):
    def status(self, path=None):
        path = self.root_dir if path is None else path
        path = os.path.relpath(path, self.root_dir)
        ForkGui('"' + self.path + '" /command:repostatus /path:"%s"' % path,
                self.root_dir)

    def commit(self, path=None):
        path = self.root_dir if path is None else path
        path = os.path.relpath(path, self.root_dir)
        ForkGui('"' + self.path + '" /command:commit /path:"%s"' % path,
                self.root_dir)

    def log(self, path=None):
        path = self.root_dir if path is None else path
        path = os.path.relpath(path, self.root_dir)
        ForkGui('"' + self.path + '" /command:log /path:"%s"' % path,
                self.root_dir)

    def blame(self, path=None):
        path = self.root_dir if path is None else path
        path = os.path.relpath(path, self.root_dir)
        ForkGui('"' + self.path + '" /command:blame /path:"%s"' % path,
                self.root_dir)

    def diff(self, path):
        path = os.path.relpath(path, self.root_dir)
        ForkGui('"' + self.path + '" /command:diff /path:"%s"' % path,
                self.root_dir)

    def add(self, path):
        path = os.path.relpath(path, self.root_dir)
        ForkGui('"' + self.path + '" /command:add /path:"%s"' % path,
                self.root_dir)

    def remove(self, path):
        path = os.path.relpath(path, self.root_dir)
        ForkGui('"' + self.path + '" /command:remove /path:"%s"' % path,
                self.root_dir)

    def revert(self, path):
        path = os.path.relpath(path, self.root_dir)
        ForkGui('"' + self.path + '" /command:revert /path:"%s"' % path,
                self.root_dir)


class TortoiseSVN(TortoiseProc):
    def __init__(self, binary_path, file):
        self.find_root('.svn', file, False)
        if binary_path is not None:
            self.path = binary_path
        else:
            self.set_binary_path('TortoiseSVN\\bin\\TortoiseProc.exe',
                                 'TortoiseProc.exe', 'svn_tortoiseproc_path')

    def sync(self, path=None):
        path = self.root_dir if path is None else path
        path = os.path.relpath(path, self.root_dir)
        ForkGui('"' + self.path + '" /command:update /path:"%s"' % path,
                self.root_dir)

    def get_status(self, path):
        svn = SVN(self.root_dir)
        return self.process_status(svn, path)


class TortoiseGit(TortoiseProc):
    def __init__(self, binary_path, file):
        self.find_root('.git', file)
        if binary_path is not None:
            self.path = binary_path
        else:
            self.set_binary_path('TortoiseGit\\bin\\TortoiseProc.exe',
                                 'TortoiseProc.exe', 'git_tortoiseproc_path')

    def sync(self, path=None):
        path = self.root_dir if path is None else path
        path = os.path.relpath(path, self.root_dir)
        ForkGui('"' + self.path + '" /command:sync /path:"%s"' % path,
                self.root_dir)

    def get_status(self, path):
        git = Git(self.path, self.root_dir)
        return self.process_status(git, path)


class TortoiseHg(Tortoise):
    def __init__(self, binary_path, file):
        self.find_root('.hg', file)
        if binary_path is not None:
            self.path = binary_path
        else:
            try:
                self.set_binary_path('TortoiseHg\\thgw.exe',
                                     'thgw.exe', 'hg_hgtk_path')
            except (NotFoundError):
                self.set_binary_path(
                    'TortoiseHg\\hgtk.exe',
                    'thgw.exe (for TortoiseHg v2.x) or hgtk.exe (for ' +
                    'TortoiseHg v1.x)', 'hg_hgtk_path')

    def status(self, path=None):
        path = os.path.relpath(path, self.root_dir)
        args = [self.path, 'status', '--nofork', path]
        ForkGui(args, self.root_dir)

    def commit(self, path=None):
        path = os.path.relpath(path, self.root_dir)
        args = [self.path, 'commit', '--nofork', path]
        ForkGui(args, self.root_dir)

    def sync(self, path=None):
        path = os.path.relpath(path, self.root_dir)
        args = [self.path, 'synch', '--nofork', path]
        ForkGui(args, self.root_dir)

    def log(self, path=None):
        path = os.path.relpath(path, self.root_dir)
        args = [self.path, 'log', '--nofork', path]
        ForkGui(args, self.root_dir)

    def blame(self, path=None):
        path = os.path.relpath(path, self.root_dir)
        args = [self.path, 'blame', '--nofork', path]
        ForkGui(args, self.root_dir)

    def diff(self, path):
        path = os.path.relpath(path, self.root_dir)
        args = [self.path, 'vdiff', '--nofork', path]
        ForkGui(args, self.root_dir)

    def add(self, path):
        path = os.path.relpath(path, self.root_dir)
        args = [self.path, 'add', '--nofork', path]
        ForkGui(args, self.root_dir)

    def remove(self, path):
        path = os.path.relpath(path, self.root_dir)
        args = [self.path, 'remove', '--nofork', path]
        ForkGui(args, self.root_dir)

    def revert(self, path):
        path = os.path.relpath(path, self.root_dir)
        args = [self.path, 'revert', '--nofork', path]
        ForkGui(args, self.root_dir)

    def get_status(self, path):
        hg = Hg(self.path, self.root_dir)
        return self.process_status(hg, path)


class NonInteractiveProcess():
    def __init__(self, args, cwd=None):
        self.args = args
        self.cwd = cwd

    def run(self):
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        proc = subprocess.Popen(
            self.args, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            startupinfo=startupinfo, cwd=self.cwd)

        readout = proc.stdout.read().decode("utf-8")
        return readout.replace('\r\n', '\n').rstrip(' \n\r')


class SVN():
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.svn_paths = self.get_svn_paths()

    def check_errors(self, error):
        print(error)
        if error == "E155021":
            raise Exception("""
This client is too old to work with the working copy.
You need to get a newer Subversion client, and point your sublime tortoise "svn_path" setting to it's location.

For more details, see: http://subversion.apache.org/faq.html#working-copy-format-change
""")

    def get_svn_paths(self):
        paths = []
        settings = sublime.load_settings('Tortoise.sublime-settings')
        if "svn_path" in settings:
            paths.append(settings["svn_path"])
        packages_path = sublime.packages_path()
        paths.append(os.path.join(packages_path, PACKAGE_ROOT,
                     'svn', 'svn.exe'))
        return paths

    def check_svn_vs_path(self, svn_path, path):
        return NonInteractiveProcess([svn_path, 'status', path],
                                     cwd=self.root_dir)

    def check_status(self, path):
        for svn_path in self.svn_paths:
            proc = self.check_svn_vs_path(svn_path, path)
            result = proc.run().split('\n')
            if len(result) > 0 and result[0].startswith("svn: E"):
                self.check_errors(result[0].split(":")[1].strip())
            else:
                break

        for line in result:
            if len(line) < 1:
                continue

            path_without_root = path.replace(self.root_dir + '\\', '', 1)
            path_regex = re.escape(path_without_root) + '$'
            if self.root_dir != path and re.search(path_regex, line) is None:
                continue
            return line[0]
        return ''


class FileSearch(threading.Thread):
    def __init__(self, timeout, f, dirs=None):
        self.file = f
        self.dirs = dirs
        self.timeout = timeout
        self.result = None
        threading.Thread.__init__(self)

    def run(self):
        try:
            if not self.dirs:
                self.dirs = (
                    os.environ.get("ProgramFiles(x86)", os.environ.get("ProgramFiles", '')),
                )
            sublime.status_message("searching for path of " + self.file + " ...")
            file_path = search_file(self.file, self.dirs)
            if file_path:
                sublime.status_message("found " + self.file + " at {0}".format(file_path))
                self.result = file_path
                return
        except Exception:
            pass


def handle_threads(self, threads, i=0, dir=1):
        next_threads = []
        for thread in threads:
            if thread.is_alive():
                next_threads.append(thread)
                continue
            if thread.result is None:
                continue
            settings = sublime.load_settings('Tortoise.sublime-settings')
            settings.set('git_tgit_path', thread.result)
            TortoiseCommand()
        threads = next_threads

        if len(threads):
            # This animates a little activity indicator in the status area
            before = i % 8
            after = (7) - before
            if not after:
                dir = -1
            if not before:
                dir = 1
            i += dir
            self.view.set_status('tortoise', 'Tortoise [%s=%s]' %
                                 (' ' * before, ' ' * after))

            sublime.set_timeout(lambda: self.handle_threads(threads,
                                i, dir), 100)
            return

        self.view.erase_status('tortoise')
        sublime.status_message('Tortoise successfully completed search')


class Git():
    def __init__(self, tortoise_proc_path, root_dir):
        settings = sublime.load_settings('Tortoise.sublime-settings')
        self.git_path = settings.get('git_tgit_path') or (
            os.path.dirname(tortoise_proc_path) + '\\tgit.exe') or (
                os.path.dirname(tortoise_proc_path) + '\\git.exe')

        if not self.git_path:
            # search for git in a seperate thread (non-blocking)
            threads = []  # implement multiple searches (simultanious)
            thread = FileSearch(5, 'git.exe')
            threads.append(thread)
            thread.start()

        self.root_dir = root_dir

    def check_status(self, path):
        if os.path.isdir(path):
            proc = NonInteractiveProcess([self.git_path, 'log', '-1', path],
                                         cwd=self.root_dir)
            result = proc.run().strip().split('\n')
            if result == ['']:
                return '?'
            return ''

        proc = NonInteractiveProcess([self.git_path, 'status', '--short'],
                                     cwd=self.root_dir)
        result = proc.run().strip().split('\n')
        for line in result:
            if len(line) < 2:
                continue
            path_without_root = path.replace(self.root_dir + '\\', '', 1)
            path_regex = re.escape(path_without_root) + '$'
            if self.root_dir != path and re.search(path_regex, line) is None:
                continue

            if line[0] != ' ':
                res = line[0]
            else:
                res = line[1]
            return res.upper()
        return ''


class Hg():
    def __init__(self, tortoise_proc_path, root_dir):
        self.hg_path = os.path.dirname(tortoise_proc_path) + '\\hg.exe'
        self.root_dir = root_dir

    def check_status(self, path):
        if os.path.isdir(path):
            proc = NonInteractiveProcess([self.hg_path, 'log', '-l', '1',
                                         '"' + path + '"'], cwd=self.root_dir)
            result = proc.run().strip().split('\n')
            if result == ['']:
                return '?'
            return ''

        proc = NonInteractiveProcess([self.hg_path, 'status', path],
                                     cwd=self.root_dir)
        result = proc.run().split('\n')
        for line in result:
            if len(line) < 1:
                continue
            return line[0].upper()
        return ''
