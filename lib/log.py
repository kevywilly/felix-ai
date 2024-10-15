import logging
import sys


# Define a new level
logging.SUCCESS = 25  # between INFO and WARNING
logging.addLevelName(logging.SUCCESS, "SUCCESS")

# Add a success method to the logger
def success(self, message, *args, **kwargs):
    if self.isEnabledFor(logging.SUCCESS):
        self._log(logging.SUCCESS, message, args, **kwargs)


logging.Logger.success = success


class Logger:
    def __init__(self, name: str):
        self.name = name

    def info(self, msg, *args, **kwargs):
        print(f"[{self.name}] [info]: {msg}")

    def warning(self, msg, *args, **kwargs):
        print(f"[{self.name}] [warning]: {msg}")

    def error(self, msg, *args, **kwargs):
        print(f"[{self.name}] [error]: {msg}")

    def pretty(self, msg, *args, **kwargs):
        character = '-'
        charlen = max(len(msg),100)
        print(character * charlen)
        print(msg)
        print(character * charlen)
        for arg in args:
            print(f"\t-- {arg}")

        print("\n")


logger=Logger("felix")

#logging.basicConfig(stream=sys.stdout, level=logging.INFO)
#logger = logging.getLogger("felix")
#logger.addHandler(logging.StreamHandler(stream=sys.stdout))

