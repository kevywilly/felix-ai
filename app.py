#!/usr/bin/env python3
#!/usr/bin/env python3

import logging
import os
from flask_cors import CORS
from flask import Flask


#from felix.nodes.tof_cluster import TOFCluster


logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))

app = Flask(__name__)

log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)

CORS(app)

CORS(app, resources={r"/generate": {"origins": "*"}})


@app.route("/healthcheck")
def healthcheck():
    return {"status": "ok"}




if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
   