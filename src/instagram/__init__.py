from src.util.modules import expose_modules


def _init():
    """
    Interpreter testing initialize()
    """
    from .instagram import initialize
    from src import config

    initialize(config.Config(), '/u/igHighlightsBot')

__all__ = expose_modules(__file__, __name__, locals())

