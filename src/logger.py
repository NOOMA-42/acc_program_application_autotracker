import logging
import os
from pathlib import Path

def get_project_root() -> str:
    return str(Path(__file__).parent.parent)

logging.basicConfig(
    filename=os.path.join(get_project_root(), "app.log"),
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode="a",
    force=True,
)

logger = logging.getLogger("logger")


def get_logger():
    return logger