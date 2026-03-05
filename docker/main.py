import os
import threading
import logging
from datetime import datetime
from flask import Flask, jsonify
from dkb_sync import run_sync

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s:%(name)s:%(message)s", force=True)
logger = logging.getLogger(__name__)

sync_state = {
    "running": False,
    "last_sync": None,
    "last_count": 0,
    "last_error": None,
}


def do_sync():
    sync_state["running"] = True
    sync_state["last_error"] = None
    try:
        logger.info("Sync starting...")
        count = run_sync()
        sync_state["last_count"] = count
        sync_state["last_sync"] = datetime.now().strftime("%d.%m.%Y %H:%M")
        logger.info("Sync completed: %d new document(s)", count)
    except BaseException as e:
        sync_state["last_error"] = str(e) or repr(e)
        logger.error("Sync failed: %r", e)
    finally:
        sync_state["running"] = False


@app.route("/sync", methods=["POST"])
def trigger_sync():
    if sync_state["running"]:
        return jsonify({"status": "already_running"}), 409
    thread = threading.Thread(target=do_sync, daemon=True)
    thread.start()
    return jsonify({"status": "started"}), 202


@app.route("/status", methods=["GET"])
def status():
    return jsonify(sync_state)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8765")))
