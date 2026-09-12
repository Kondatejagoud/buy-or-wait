import pandas as pd
from typing import Dict, Any, List, Optional
from code.finance.currency import CurrencyConverter
from code.evidence.image_parser import ImageParser

class EventResolver:
    def __init__(self, currency_converter: CurrencyConverter, image_parser: ImageParser):
        self.fx = currency_converter
        self.img_parser = image_parser

    def resolve_user_events(
        self,
        user_id: str,
        home_currency: str,
        events_df: pd.DataFrame,
        images_by_event: Dict[str, Dict[str, Any]],
        user_messages_df: pd.DataFrame
    ) -> List[Dict[str, Any]]:
        """
        Takes raw financial_events rows for a user, applies image evidence and message amendments,
        converts amounts to user's home_currency, and returns normalized resolved events.
        """
        resolved_events: List[Dict[str, Any]] = []

        if events_df.empty:
            return resolved_events

        # First pass: map messages to events if related_event_id is present
        message_updates_by_event: Dict[str, List[Dict[str, Any]]] = {}
        if not user_messages_df.empty:
            for _, msg in user_messages_df.iterrows():
                rel_id = msg.get("related_event_id")
                if pd.notna(rel_id):
                    rel_str = str(rel_id)
                    if rel_str not in message_updates_by_event:
                        message_updates_by_event[rel_str] = []
                    message_updates_by_event[rel_str].append(msg.to_dict())

        for _, row in events_df.iterrows():
            ev = row.to_dict()
            event_id = str(ev["event_id"])

            # Check if amount is blank/NaN and needs image extraction
            amt = ev.get("amount")
            ev_curr = str(ev.get("currency", home_currency))
            if pd.isna(ev_curr) or ev_curr == "nan":
                ev_curr = home_currency

            if pd.isna(amt):
                # Look up in images.csv / ImageParser
                img_info = images_by_event.get(event_id)
                if img_info:
                    img_id = img_info["image_id"]
                    extracted = self.img_parser.extract_fact(img_id)
                    if extracted and "amount" in extracted:
                        amt = float(extracted["amount"])
                        if "currency" in extracted:
                            ev_curr = extracted["currency"]

            if pd.isna(amt):
                # If still NaN and missing image, skip or set 0 conservatively
                amt = 0.0

            amt = float(amt)

            # Convert date fields
            ev_date = str(ev.get("event_date", ""))
            settle_date = str(ev.get("settlement_date", ev_date))
            if pd.isna(settle_date) or settle_date == "nan":
                settle_date = ev_date

            ref_date = settle_date if settle_date else ev_date
            if not ref_date or ref_date == "nan":
                ref_date = "2026-01-01"

            # Convert amount to home_currency using dated FX
            amt_home = self.fx.convert(amt, ev_curr, home_currency, ref_date)

            status = str(ev.get("status", "settled")).lower()
            direction = str(ev.get("direction", "debit")).lower()
            event_type = str(ev.get("event_type", "expense")).lower()
            category = str(ev.get("category", "other")).lower()
            flexibility = str(ev.get("flexibility", "fixed")).lower()
            min_allowed = ev.get("minimum_allowed_amount")
            if pd.notna(min_allowed):
                min_allowed_home = self.fx.convert(float(min_allowed), ev_curr, home_currency, ref_date)
            else:
                min_allowed_home = None

            # Apply message amendments if any
            if event_id in message_updates_by_event:
                for msg in message_updates_by_event[event_id]:
                    text = str(msg.get("message_text", "")).lower()
                    if "cancel" in text or "dibatalkan" in text or "void" in text:
                        status = "cancelled"
                    elif "settle" in text or "paid" in text or "lunas" in text:
                        status = "settled"

            resolved_events.append({
                "event_id": event_id,
                "user_id": user_id,
                "event_type": event_type,
                "description": str(ev.get("description", "")),
                "category": category,
                "direction": direction,
                "amount": amt_home,
                "original_amount": amt,
                "original_currency": ev_curr,
                "event_date": ev_date,
                "settlement_date": settle_date,
                "status": status,
                "linked_event_id": str(ev.get("linked_event_id", "")) if pd.notna(ev.get("linked_event_id")) else None,
                "flexibility": flexibility,
                "minimum_allowed_amount": min_allowed_home
            })

        return resolved_events
