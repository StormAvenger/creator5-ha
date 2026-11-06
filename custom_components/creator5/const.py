"""Integration constants."""

DOMAIN = "creator5"
CONF_SERIAL = "serial_number"
CONF_CHECK_CODE = "check_code"
# Last verified model, kept so entities can load while the printer is off.
CONF_MODEL = "model"
MODELS = ("Creator 5", "Creator 5 Pro")
# Last known states in which losing the connection is unexpected. Idle, completed
# and error states are excluded: power-off and auto-shutdown are normal there.
ACTIVE_STATES = ("printing", "paused", "pause", "heating", "calibrate_doing")
