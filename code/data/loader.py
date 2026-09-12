import os
import pandas as pd
from typing import Dict, Any

class DataLoader:
    def __init__(self, dataset_dir: str = "dataset"):
        self.dataset_dir = dataset_dir
        self.profiles_df = pd.DataFrame()
        self.events_df = pd.DataFrame()
        self.rates_df = pd.DataFrame()
        self.requests_df = pd.DataFrame()
        self.payment_options_df = pd.DataFrame()
        self.messages_df = pd.DataFrame()
        self.images_df = pd.DataFrame()
        self.load_data()

    def load_data(self):
        self.profiles_df = pd.read_csv(os.path.join(self.dataset_dir, "financial_profiles.csv"))
        self.events_df = pd.read_csv(os.path.join(self.dataset_dir, "financial_events.csv"))
        self.rates_df = pd.read_csv(os.path.join(self.dataset_dir, "exchange_rates.csv"))
        self.requests_df = pd.read_csv(os.path.join(self.dataset_dir, "requests.csv"))
        self.payment_options_df = pd.read_csv(os.path.join(self.dataset_dir, "request_payment_options.csv"))
        self.messages_df = pd.read_csv(os.path.join(self.dataset_dir, "messages.csv"))
        self.images_df = pd.read_csv(os.path.join(self.dataset_dir, "images.csv"))

        # Pre-index profiles by user_id
        self.profiles_by_user: Dict[str, Dict[str, Any]] = {}
        for _, row in self.profiles_df.iterrows():
            self.profiles_by_user[row["user_id"]] = row.to_dict()

        # Pre-group events by user_id
        self.events_by_user: Dict[str, pd.DataFrame] = {}
        for user_id, group in self.events_df.groupby("user_id"):
            self.events_by_user[user_id] = group.copy()

        # Pre-group payment options by request_id
        self.payment_options_by_request: Dict[str, pd.DataFrame] = {}
        for req_id, group in self.payment_options_df.groupby("request_id"):
            self.payment_options_by_request[req_id] = group.copy()

        # Pre-group messages by user_id, request_id, related_event_id
        self.messages_by_user: Dict[str, pd.DataFrame] = {}
        for user_id, group in self.messages_df.groupby("user_id"):
            self.messages_by_user[user_id] = group.copy()

        self.messages_by_request: Dict[str, pd.DataFrame] = {}
        for req_id, group in self.messages_df.dropna(subset=["request_id"]).groupby("request_id"):
            self.messages_by_request[req_id] = group.copy()

        self.messages_by_event: Dict[str, pd.DataFrame] = {}
        for event_id, group in self.messages_df.dropna(subset=["related_event_id"]).groupby("related_event_id"):
            self.messages_by_event[event_id] = group.copy()

        # Pre-index images by related_event_id and request_id
        self.images_by_event: Dict[str, Dict[str, Any]] = {}
        for _, row in self.images_df.dropna(subset=["related_event_id"]).iterrows():
            self.images_by_event[row["related_event_id"]] = row.to_dict()

        self.images_by_request: Dict[str, Dict[str, Any]] = {}
        for _, row in self.images_df.dropna(subset=["request_id"]).iterrows():
            self.images_by_request[row["request_id"]] = row.to_dict()

    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        return self.profiles_by_user.get(user_id, {})

    def get_user_events(self, user_id: str) -> pd.DataFrame:
        return self.events_by_user.get(user_id, pd.DataFrame())

    def get_request_payment_options(self, request_id: str) -> pd.DataFrame:
        return self.payment_options_by_request.get(request_id, pd.DataFrame())

    def get_user_messages(self, user_id: str) -> pd.DataFrame:
        return self.messages_by_user.get(user_id, pd.DataFrame())

    def get_request_messages(self, request_id: str) -> pd.DataFrame:
        return self.messages_by_request.get(request_id, pd.DataFrame())

    def get_event_messages(self, event_id: str) -> pd.DataFrame:
        return self.messages_by_event.get(event_id, pd.DataFrame())
