import json
import os
import logging

class ScrappageDataStore:
    """
    Data store (Model) for Scrappage Scheme.
    Manages state and extracted values from OpenAI.
    """
    
    def __init__(self, storage_path="scratch/scrappage_store.json"):
        self.storage_path = storage_path
        self.data = {
            "invoice": {},
            "disclaimer": {},
            "ledger": {},
            "cod": {},
            "oem": {},
            "relational": {}
        }
        self._load()

    def _load(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            except Exception as e:
                logging.error(f"Error loading scrappage store: {e}")

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            logging.error(f"Error saving scrappage store: {e}")

    def update_doc_data(self, doc_type, payload):
        """
        Updates the store for a specific document type.
        """
        if doc_type in self.data:
            self.data[doc_type].update(payload)
            self.save()
            
    def get_doc_data(self, doc_type):
        return self.data.get(doc_type, {})
