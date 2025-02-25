import logging
import datetime as dt
import os

from wpp.config import get_wpp_log_dir


#
# Set up Logging
#
class StdOutFilter(logging.Filter):
    def filter(self, record):
        return record.levelno >= logging.INFO  # | record.levelno == logging.DEBUG


class StdErrFilter(logging.Filter):
    def filter(self, record):
        return not record.levelno == logging.INFO | record.levelno == logging.DEBUG


def get_log_file(module_name: str, log_file_name: str) -> logging.Logger:
    today = dt.datetime.today()
    os.makedirs(get_wpp_log_dir(), exist_ok=True)
    log_file = log_file_name.format(today.strftime("%Y-%m-%d"))

    # logFormatter = logging.Formatter("%(asctime)s - %(levelname)s: - %(message)s", "%Y-%m-%d %H:%M:%S")
    logFormatter = logging.Formatter(
        "%(asctime)s - %(levelname)s: - %(message)s", "%H:%M:%S"
    )

    # logging.basicConfig(filename=log_file, level=logging.WARNING)
    logger = logging.getLogger(module_name)
    # handler = logging.RotatingFileHandler(log_file), maxBytes=2000, backupCount=7)
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logFormatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logFormatter)
    stream_handler.addFilter(StdOutFilter())
    logger.addHandler(stream_handler)

    logger.setLevel(logging.INFO)

    return logger
