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
    count = 0
    with DKBRobo(dkb_user=DKB_USER, dkb_password=DKB_PASSWORD, xvfb=True, unfiltered=True) as dkb:
        WANTED = {"bankAccountStatement", "creditCardStatement"}
        documents = dkb.download(path=None, download_all=False)
        logger.info("Total documents: %d", len(documents))
        for doc in documents.values():
            logger.info("Doc: %s type=%s", doc.filename(), doc.message.documentType if doc.message else "no-message")
            if not doc.message or doc.message.documentType not in WANTED:
                continue
            target = CONSUME_DIR / doc.filename()
            rcode = doc.download(dkb.wrapper.client, target)
            if rcode:
                doc.mark_read(dkb.wrapper.client, True)
                logger.info("Downloaded: %s", target.name)
                count += 1
    return count
