"""
Silicon Oracle - Flask Extensions
Centralized extension initialization to avoid circular imports.
"""

from flask_caching import Cache
from flask_wtf.csrf import CSRFProtect

# Initialize extensions without app
cache = Cache()
csrf = CSRFProtect()
