from __future__ import print_function
import glob
import os
from pprint import pformat


# hard-coded debug flag (change to True to turn on print statements)
__DEBUG = False
def _debug(*msg, **kwargs):
    if __DEBUG:
        print(*msg, **kwargs)

__path = os.path.expanduser(__file__)
__path = os.path.realpath( os.path.abspath(__path) )
__path = os.path.dirname(__path)
__modules = glob.glob(u'{0}/*.py'.format(__path))
_debug('__path:', __path)
_debug('__modules:', pformat(__modules), sep='\n', end='\n\n')

# https://stackoverflow.com/a/32496999
__all__ = []
for module in __modules:
    module = str(module)
    _debug(module)
    if not module.endswith('__init__.py'):
        package_prefix = '{0}'.format(__name__)
        # get the filename
        module_name = os.path.basename(module).rsplit('.', 1)[0]
        __all__.append(module_name)
        _debug(
                '\timporting',
                '{0}.{1}'.format(package_prefix, module_name),
                '...',
        )
        imported_module = __import__(
                '{0}.{1}'.format(package_prefix, module_name),
                fromlist=[module],
        )

        # expose module attributes at this level
        # ie:
        #   >>> from src import database
        #   >>> dir(database)
        #   ['Database', 'FailedInit', ...]
        for attr in dir(imported_module):
            _debug('\t\t', attr)
            if attr in imported_module.__all__:
                _debug('\t\t\texposing ...')
                attr_obj = getattr(imported_module, attr)
                locals()[attr_obj.__name__] = attr_obj
                __all__.append(attr_obj.__name__)

