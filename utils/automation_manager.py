import json

def load_auto_responses():
    try:
        with open("data/server_data.json") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}