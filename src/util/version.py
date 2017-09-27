import shlex
import subprocess

from six.moves import getcwd

from constants import ROOT_DIR
from src.util import logger


__VERSION__ = None

def run_cmd(cmd_str, fail_msg):
    output = None
    try:
        proc = subprocess.Popen(
                shlex.split(cmd_str),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
        )
    except (OSError, ValueError) as e:
        logger.warn(fail_msg, exc_info=True)
    else:
        output = proc.stdout.read().strip()
        if not output:
            logger.debug('{0} ({1})', fail_msg, proc.stderr.read().strip())
    return output

def get_version():
    """
    Determines the version string based on git tags and number of commits since
    the last version tag. The value is cached so git commits/tags that happen
    while the program is running will not affect the version.
    """

    global __VERSION__

    if __VERSION__:
        return __VERSION__

    stock_version = '0.1.0'

    cwd = getcwd()
    try:
        os.chdir(ROOT_DIR)

    except OSError as e:
        logger.warn('Could not determine version', exc_info=True)

    else:
        # https://stackoverflow.com/a/4277828
        __VERSION__ = run_cmd(
                'git describe --tags --abbrev=0 --match v*',
                'Could not determine latest tag version',
        )
        if __VERSION__:
            # https://stackoverflow.com/a/20526776
            num_commits_since_tag = run_cmd(
                    'git rev-list {0}.. --count'.format(__VERSION__),
                    'Could not determine number of commits since version'
                    ' \'{0}\''.format(__VERSION__),
            )
            if num_commits_since_tag:
                __VERSION__ = '{0}.{1}'.format(
                        __VERSION__,
                        num_commits_since_tag,
                )
            else:
                __VERSION__ = None
        # nothing in the program should rely on the cwd, but just in case ...
        os.chdir(cwd)

    if not __VERSION__:
        __VERSION__ = stock_version
        logger.debug('Using version = {0} ...', __VERSION__)

    return __VERSION__


__all__ = [
        'get_version',
]

