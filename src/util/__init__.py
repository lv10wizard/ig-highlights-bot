from errno import EEXIST
import os


def mkdirs(path):
    # https://stackoverflow.com/a/20667049
    try:
        os.makedirs(path, exist_ok=True) # python > 3.2
    except TypeError: # python <= 3.2
        try:
            os.makedirs(path)
        except OSError as e: # python > 2.5
            if e.errno == EEXIST and os.path.isdir(path):
                pass
            else:
                raise

def choose_filename(dirname, name, ext):
    """
    Returns the full path (ie, os.path.join(dirname, name+'.'+ext))
    if it does not exist. If it does exist, then this function will return the
    the full path with an incrementing integer appended after name and before
    ext (eg. {dirname}/{name}.{i}.{ext})
    """
    resolved_dirname = resolve_path(dirname)
    i = 0
    path = None
    while not path or os.path.exists(path):
        filename = [name]
        if i > 0:
            filename.append(str(i))
        filename.append(ext)
        path = os.path.join(resolved_dirname, '.'.join(filename))
        i += 1
    return path

