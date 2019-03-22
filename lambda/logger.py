import logging
import os


def get_console_logger():
    """
    Creates a console logging object that is formatted nicely for lambda functions
    :return: logging object configured the way we want it
    """

    # Configure logger level
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    if 'DEBUG' in os.environ:
        if str(os.environ['DEBUG']).lower() == "true" or str(os.environ['DEBUG']) == "1":
            logger.setLevel(logging.DEBUG)
    # Configure logger to format logs to include module and function name (troubleshooting much easier)
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter('%(levelname)s %(module)s.%(funcName)s %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger
