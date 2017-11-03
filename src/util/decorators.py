# stackoverflow.com/questions/5189699/5191224#5191224
class ClassPropertyDesc(object):
    def __init__(self, fget, fset=None):
        self.fget = fget
        self.fset = fset

    def __get__(self, obj, class_=None):
        if class_ is None:
            class_ = type(obj)
        return self.fget.__get__(obj, class_)()

    def __set__(self, obj, val):
        if not self.fset:
            raise AttributeError(u'Cannot set attribute=\'{}\''.format(val))
        return self.fset.__get__(obj, type(obj))(value)

    def setter(self, func):
        if not isinstance(func, (classmethod, staticmethod)):
            func = classmethod(func)
        self.fset = func
        return self

def classproperty(func):
    if not isinstance(func, (classmethod, staticmethod)):
        func = classmethod(func)
    return ClassPropertyDesc(func)


__all__ = [
        'classproperty',
]

