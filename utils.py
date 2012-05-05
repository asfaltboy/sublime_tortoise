from os.path import join, isdir
from os import walk
from fnmatch import filter as ffilter


def search_file(filename, dirs):
    """Given directories path tuple, find a file and return first matching dir
    """
    match = None
    for path in dirs:
        if not isdir(path):
            continue
        for root, dirnames, filenames in walk(path):
            for filename in ffilter(filenames, 'git.exe'):
                match = join(root, filename)
                if match:
                    break
    return match
