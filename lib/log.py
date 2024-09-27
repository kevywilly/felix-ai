import logging
import sys

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger("felix")
#logger.addHandler(logging.StreamHandler(stream=sys.stdout))

