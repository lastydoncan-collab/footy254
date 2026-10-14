"""
FOOTY254 rate limiting.

One shared slowapi limiter, keyed by client IP. Applied to authentication and
payment-initiation endpoints, which are the highest-value abuse targets
(credential stuffing, STK-push spam).

Behind a reverse proxy the socket peer is the proxy, not the user, so every
visitor would share one bucket. Run uvicorn with ``--proxy-headers`` and
``--forwarded-allow-ips`` set to your proxy so ``request.client.host`` is the
real client address (the Dockerfile and README do this).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
