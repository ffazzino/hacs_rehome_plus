from __future__ import annotations

DOMAIN = "rehome_plus"

DEFAULT_NAME = "ReHome Plus"
DEFAULT_BASE_URL = "http://www.radiaxweb.rehom.it:8080/EmptyApp13Web/rest/vc_service"
DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 30
MAX_SCAN_INTERVAL = 600

CONF_BASE_URL = "base_url"
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"

DATA_COORDINATOR = "coordinator"
PLATFORMS = ["climate", "sensor"]

ATTR_SYSTEM_STATUS = "system_status"
ATTR_STATUS_CODE = "status_code"
ATTR_ZONE_COUNT = "zone_count"

SYSTEM_STATUS_LABELS = {
    0: "off",
    1: "manual",
    2: "auto",
}
