from utils.json_manager import load_json


def load_auto_responses():
    return load_json("data/server_data.json")
