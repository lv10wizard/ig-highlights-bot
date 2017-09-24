"""
Dynamic import helpers to expose sub-package modules at the top-level.
This eliminates the need to explicitly import sub-modules.

eg.
    root/
        main.py

        asdf/
            __init__.py
            foo.py
            bar.py

        qwerty/
            __init__.py
            blah.py

    -----

    asdf/__init__.py:
        ...
        __all__ = expose_modules( ... )

    qwerty/__init__.py:
        ...
        __all__ = expose_modules( ... )

    qwerty/blah.py:
        def blah(): ...

    main.py:
        import asdf
        from qwerty import *

        # this would have required 'import asdf.foo'
        asdf.foo.do_stuff()
        # this would have required 'from qwerty.blah import blah'
        blah()
"""

from __future__ import print_function
from glob import glob
import os
from pprint import pformat

from constants import __DEBUG__


# hard-coded debug flag (changed to True to turn on debugging print statements)
def _debug(*msg, **kwargs):
    if __DEBUG__:
        print(*msg, **kwargs)

def get_all_modules(path):
    """
    Returns all .py files in the directory pointed to by {path}.

    path (str) - either the directory path or file path where modules are stored
            If path is a directory, it is used; if path is a file, the
            containing directory is used.
    """
    resolved = os.path.expanduser(path)
    resolved = os.path.realpath( os.path.abspath(resolved) )
    if not os.path.isdir(resolved):
        resolved = os.path.dirname(resolved)
    modules = glob(u'{0}/*.py'.format(resolved))
    _debug('resolved:', resolved)
    _debug('modules:', pformat(modules), sep='\n', end='\n\n')
    return modules

def _submodule_attrs(path, prefix):
    """
    Iterates over the submodules in {path}

    Yields the tuple (imported_module, attr, attr_obj)
        imported_module - the imported module
        attr - an attribute string in the imported_module
        attr_obj - the corresponding attribute object
    """
    modules = get_all_modules(path)
    for module in modules:
        module = str(module)
        _debug(module)
        if not module.endswith('__init__.py'):
            package_prefix = '{0}'.format(prefix)
            # get the filename
            module_name = os.path.basename(module).rsplit('.', 1)[0]
            _debug(
                    '\timporting',
                    '{0}.{1}'.format(package_prefix, module_name),
                    '...',
            )
            imported_module = __import__(
                    '{0}.{1}'.format(package_prefix, module_name),
                    fromlist=[module],
            )
            for attr in dir(imported_module):
                _debug('\t\t', attr)
                attr_obj = getattr(imported_module, attr)
                yield imported_module, attr, attr_obj

def _attr_name(attr, obj):
    try:
        return obj.__name__
    except AttributeError:
        return attr

def expose_modules(path, prefix, locals, all_array=[]):
    """
    Exposes modules' (.py) __all__ elements by appending them to {all_array}

    path (str) - the path to where the modules are stored (see get_all_modules)
    prefix (str) - the __name__ variable of the caller module
    locals (dict) - the locals() dictionary of the caller module
    all_array (list, optional) - the __all__ list to expose modules under

    Returns {all_array}
    """
    for imported_module, attr, attr_obj in _submodule_attrs(path, prefix):
        # expose module attributes at this level
        # ie:
        #   >>> from src import database
        #   >>> dir(database)
        #   ['Database', 'FailedInit', ...]
        if imported_module.__name__ not in all_array:
            all_array.append(imported_module.__name__)
        if (
                hasattr(imported_module, '__all__')
                and attr in imported_module.__all__
        ):
            _debug('\t\t\texposing ...')
            attr_name = _attr_name(attr, attr_obj)
            locals[attr_name] = attr_obj
            all_array.append(attr_name)

    return all_array

def register_subclasses(path, prefix, base_class):
    """
    Collects subclasses of {base_class} defined in submodules of {path}

    path (str) - the path to where the submodules are stored
    prefix (str) - the __name__ variable of the caller module
    base_class (class) - the base class to register subclasses of

    Returns a dictionary {class_name: class} of registered subclasses
    """
    subclasses = {}
    for imported_module, attr, attr_obj in _submodule_attrs(path, prefix):
        if hasattr(attr_obj, '__bases__') and base_class in attr_obj.__bases__:
            _debug('\t\t\tregistering subclass ...')
            attr_name = _attr_name(attr, attr_obj)
            subclasses[attr_name] = attr_obj

    return subclasses

