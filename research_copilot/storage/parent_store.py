import json
import logging
import shutil
from research_copilot.config import settings as config
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)


class ParentStoreManager:
    __store_path: Path

    def __init__(self, store_path=config.PARENT_STORE_PATH):
        self.__store_path = Path(store_path) 
        self.__store_path.mkdir(parents=True, exist_ok=True)

    def save(self, parent_id: str, content: str, metadata: Dict) -> None:
        file_path = self.__store_path / f"{parent_id}.json"
        file_path.write_text(
            json.dumps({"page_content": content,"metadata": metadata}, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    def save_many(self, parents: List) -> None:
        for parent_id, doc in parents:
            self.save(parent_id, doc.page_content, doc.metadata)

    def load(self, parent_id: str) -> Dict:
        file_path = self.__store_path / (
            parent_id if parent_id.lower().endswith(".json") else f"{parent_id}.json"
        )
        return json.loads(file_path.read_text(encoding="utf-8"))
    
    def load_many(self, parent_ids: List[str]) -> List[Dict]:
        """Load parents in the order requested (the retrieval ranking), once each.

        Missing ids are skipped with a warning instead of failing the whole call,
        so one stale id from the vector index does not hide the other parents.
        Other read errors (corrupt JSON, permissions) still raise.
        """
        results = []
        for parent_id in dict.fromkeys(parent_ids):
            try:
                data = self.load(parent_id)
            except FileNotFoundError:
                logger.warning("Parent chunk %s is missing from the parent store; skipping it", parent_id)
                continue
            results.append({
                "content": data["page_content"],
                "parent_id": parent_id,
                "metadata": data["metadata"]
            })
        return results
    
    def clear_store(self) -> None:
        if self.__store_path.exists():
            shutil.rmtree(self.__store_path)
        self.__store_path.mkdir(parents=True, exist_ok=True)