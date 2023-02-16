import os

# retry settings
MP_EO_IO_RETRY_SETTINGS = {
    "tries": int(os.environ.get("MP_EO_IO_RETRY_TRIES", 3)),
    "delay": int(os.environ.get("MP_EO_RETRY_DELAY", 1)),
    "backoff": int(os.environ.get("MP_EO_IO_RETRY_BACKOFF", 1)),
}
