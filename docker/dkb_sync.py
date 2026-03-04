import os
import logging
from pathlib import Path
from dkb_robo import DKBRobo

logger = logging.getLogger(__name__)

DKB_USER = os.environ["DKB_USER"]
DKB_PASSWORD = os.environ["DKB_PASSWORD"]
CONSUME_DIR = Path(os.environ.get("CONSUME_DIR", "/consume"))


def run_sync() -> int:
    CONSUME_DIR.mkdir(parents=True, exist_ok=True)
    with DKBRobo(dkb_user=DKB_USER, dkb_password=DKB_PASSWORD, xvfb=True) as dkb:
        result = dkb.download(path=CONSUME_DIR, download_all=False, mark_read=True)

    count = 0
    for category in result.values():
        for doc in category.get("documents", {}).values():
            rcode = doc.get("rcode")
            if rcode and rcode != "skipped":
                count += 1
    return count
