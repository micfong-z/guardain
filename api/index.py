from flask import Flask
from flask import request
from random import randint
from time import sleep
import asyncio

from api.MCP_client import get_danger_and_description
app = Flask(__name__)

@app.route("/api/test")
def test_api():
    longitude = request.args.get('lon')
    latitude = request.args.get('lat')
    timestamp = request.args.get('t')
    # sleep(3)  # Simulate processing delay
    return {
        "level": randint(1, 5),
        "reason": "High threat detected due to multiple nearby incidents. Seek shelter immediately. High threat detected due to multiple nearby incidents. Seek shelter immediately. High threat detected due to multiple nearby incidents. Seek shelter immediately. High threat detected due to multiple nearby incidents. Seek shelter immediately.",
        "short_reason": "Multiple nearby incidents. Seek shelter.",
    }

@app.route("/api/mcp")
def mcp_api():
    longitude = request.args.get('lon')
    latitude = request.args.get('lat')
    level, reason, short_reason = asyncio.run(get_danger_and_description(longitude, latitude))
    return {
        "level": level,
        "reason": reason,
        "short_reason": short_reason,
    }
