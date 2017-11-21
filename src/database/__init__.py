from ._database import Database
from src.util.modules import (
        expose_modules,
        register_subclasses,
)


__all__ = expose_modules(__file__, __name__, locals())

SUBCLASSES = register_subclasses(__file__, __name__, Database)
__all__.append('SUBCLASSES')

def get_class_from_name(db_name):
    db_class = None
    try:
        db_class = SUBCLASSES[db_name]
    except KeyError:
        from src.util import logger

        logger.info('Unrecognized database: \'{db_name}\'',
                db_name=db_name,
        )

    return db_class

