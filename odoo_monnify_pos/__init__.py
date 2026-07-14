try:
    from . import controllers
    from . import models
except ModuleNotFoundError:
    # Allows utility-only imports in lightweight test environments.
    pass
