from flask import Flask
from flask import request
from random import randint
from time import sleep
app = Flask(__name__)

@app.route("/api/python")
def hello_world():
    return "<p>Hello, World!</p>"

@app.route("/api/test")
def test_api():
    longitude = request.args.get('lon')
    latitude = request.args.get('lat')
    timestamp = request.args.get('t')
    # sleep(3)  # Simulate processing delay
    return {
        "level": randint(1, 5),
        "reason": "High threat detected due to multiple nearby incidents. Seek shelter immediately.",
    }
