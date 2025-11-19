"""
Manager for economy functions and features
"""

import json, os
from utils.cooldown_manager import *


class EconomyManager:
    def __init__(self, bot):
        self.bot = bot
        self.user_data_file = "data/user_data.json"
        self.user_data = self.load_user_data()

    def load_user_data(self):
        if os.path.exists(self.user_data_file):
            with open(self.user_data_file, "r") as f:
                return json.load(f)
        else:
            return {}

    def save_user_data(self):
        # write to temp file then replace
        tmp_path = f"{self.user_data_file}.tmp"
        with open(tmp_path, "w") as f:
            json.dump(self.user_data, f, indent=4)
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
        os.replace(tmp_path, self.user_data_file)

    def get_balance(self, user_id):
        user_id_str = str(user_id)
        if user_id_str not in self.user_data:
            self.user_data[user_id_str] = {"balance": 100}
            self.save_user_data()
        return self.user_data[user_id_str]["balance"]

    def update_balance(self, user_id, amount):
        user_id_str = str(user_id)
        if user_id_str not in self.user_data:
            self.user_data[user_id_str] = {"balance": 100}
        self.user_data[user_id_str]["balance"] += amount
        self.save_user_data()
    
    def set_balance(self, user_id, amount):
        user_id_str = str(user_id)
        if user_id_str not in self.user_data:
            self.user_data[user_id_str] = {"balance": 100}
        self.user_data[user_id_str]["balance"] = amount
        self.save_user_data()
    
    def get_all_balances(self):
        return {user_id: data["balance"] for user_id, data in self.user_data.items()}