from errno import EEXIST
import os


def format_repeat_each_character_pattern(text):
    """
    Returns a regex pattern matching the given text and any variation of it that
            repeats any character. eg. 'blah' -> 'b+l+a+h+' => matches 'blaaaah'
    """
    # remove repeating characters
    cleaned_text = []
    seen = ''
    for c in text:
        c = c.lower()
        if c != seen.lower():
            cleaned_text.append(c)
            seen = c
    cleaned_text = ''.join(cleaned_text)

    return ''.join( map(lambda c: '{0}+'.format(c), cleaned_text) )

def get_padding(num):
    """
    Returns padding string length for the given number
    """
    padding = 0
    while num > 0:
        padding += 1
        num //= 10
    return padding if padding > 0 else 1

def remove_duplicates(seq):
    """
    Removes duplicate elements from the list

    https://stackoverflow.com/a/480227

    Returns a list
    """
    seen = set()
    seen_add = seen.add
    return [x for x in seq if not (x in seen or seen_add(x))]

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

def readline(path, comment_chars='#', debug=False):
    """
    Reads the text file at the specified path ignoring any character
    in comment_chars and empty lines. This assumes the path is a text
    file.

    path (str) - the path to the file
    comment_chars (iterable, optional) - set of characters which denote a
            comment; Default: '#'
    debug (bool, optional) - whether to log debug statements

    Yields tuples(line_nr, line) where
            line_nr (int) - the line number of the line
            line (str) - the line that was read, stripping comments and
                    excluding empty lines
    """
    from src.config import resolve_path

    path = resolve_path(path)

    def debug_log(msg, *args, **kwargs):
        if debug:
            from src.util import logger
            logger.id(logger.debug, path, msg, *args, **kwargs)

    try:
        with open(path, 'r') as fd:
            for i, line in enumerate(fd):
                # determine the start of the comment on the line, if any
                comment_idx = -1
                for c in comment_chars:
                    try:
                        comment_idx = line.index(c)
                    except ValueError:
                        pass
                if comment_idx < 0:
                    comment_idx = len(line)

                whole_line = line
                comment = line[comment_idx:].strip()
                line = line[:comment_idx].strip()

                if whole_line.strip():
                    debug_log('[#{i}] {line}', i=i+1, line=whole_line)
                else:
                    debug_log('[#{i}] Skipping empty line', i=i+1)

                if comment:
                    debug_log('\tSkipping comment: \'{comment}\'',
                            comment=comment,
                    )

                if line:
                    yield i, line

    except (IOError, OSError):
        from src.util import logger
        logger.id(logger.exception, path,
                'Failed to read \'{path}\'!',
                path=path,
        )


