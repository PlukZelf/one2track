from datetime import timedelta
import logging

VERSION = "1.1.2"
DOMAIN = "one2track"
DEFAULT_PREFIX = "one2track"
DEFAULT_UPDATE_RATE_SEC = 60

CHECK_TIME_DELTA = timedelta(hours=1, minutes=00)

# Config keys
CONF_USER_NAME = "Username"
CONF_PASSWORD = "Password"
CONF_ID = "AccountID"

LOGGER = logging.getLogger(__package__)
