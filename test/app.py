from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Sample Data
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
    # You can access POST parameters like this:
    # request.form.get("example")

    return jsonify({
        "data": DATA
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8087, debug=True)

