from flask import Flask, render_template, jsonify
from multiprocessing import Process

app = Flask(__name__)

DATA = [
    {"id": 1, "name": "Juan Dela Cruz", "email": "juan@email.com", "role": "Admin"},
    {"id": 2, "name": "Maria Santos", "email": "maria@email.com", "role": "User"},
    {"id": 3, "name": "Pedro Reyes", "email": "pedro@email.com", "role": "User"},
    {"id": 4, "name": "Ana Lopez", "email": "ana@email.com", "role": "Manager"},
]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/get-data", methods=["POST"])
def get_data():
    return jsonify({"data": DATA})


def run_app(port):
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    p1 = Process(target=run_app, args=(8087,))
    p2 = Process(target=run_app, args=(8088,))

    p1.start()
    p2.start()

    p1.join()
    p2.join()
