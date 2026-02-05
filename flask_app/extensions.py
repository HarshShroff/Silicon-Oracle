"""
Silicon Oracle - Flask Extensions
Centralized extension initialization to avoid circular imports.
"""

from flask_caching import Cache
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Initialize extensions without app
cache = Cache()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)
