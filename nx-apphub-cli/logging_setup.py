# nx_apphub/logging_setup.py

import logging
import sys

class ColoredFormatter(logging.Formatter):
    """Custom logging formatter to add colors based on log level."""
    COLOR_CODES = {
        'DEBUG': '\033[94m',     # Blue
        'INFO': '\033[92m',      # Green
        'WARNING': '\033[93m',   # Yellow
        'ERROR': '\033[91m',     # Red
        'CRITICAL': '\033[95m',  # Magenta
    }
    RESET_CODE = '\033[0m'

    def format(self, record):
        color = self.COLOR_CODES.get(record.levelname, self.RESET_CODE)
        message = super().format(record)
        return f"{color}{message}{self.RESET_CODE}"

def setup_logging(log_level):
    """Configures the logging system based on the provided log level."""
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        print(f"Invalid log level: {log_level}")
        sys.exit(1)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)
    formatter = ColoredFormatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)

    logging.basicConfig(
        level=numeric_level,
        handlers=[handler]
    )
