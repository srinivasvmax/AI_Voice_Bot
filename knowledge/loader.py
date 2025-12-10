"""Knowledge base loader."""
import json
from pathlib import Path
from typing import Optional
from loguru import logger

from .schemas import KnowledgeBase, KnowledgeEntry


class KnowledgeBaseLoader:
    """Loads and manages knowledge base from JSON file."""
    
    def __init__(self, file_path: str):
        """
        Initialize knowledge base loader.
        
        Args:
            file_path: Path to knowledge base JSON file
        """
        self.file_path = Path(file_path)
        self._knowledge_base: Optional[KnowledgeBase] = None
    
    def load(self) -> KnowledgeBase:
        """
        Load knowledge base from file.
        
        Returns:
            KnowledgeBase instance
            
        Raises:
            FileNotFoundError: If knowledge base file not found
            ValueError: If JSON is invalid
        """
        if not self.file_path.exists():
            logger.warning(f"Knowledge base file not found: {self.file_path}")
            return KnowledgeBase(entries=[])
        
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Parse entries
            entries = []
            if isinstance(data, list):
                # Array of entries
                for item in data:
                    entries.append(KnowledgeEntry(**item))
            elif isinstance(data, dict):
                # Object with entries key
                if 'entries' in data:
                    for item in data['entries']:
                        entries.append(KnowledgeEntry(**item))
                else:
                    # Single entry
                    entries.append(KnowledgeEntry(**data))
            
            metadata = data.get('metadata', {}) if isinstance(data, dict) else {}
            
            self._knowledge_base = KnowledgeBase(entries=entries, metadata=metadata)
            logger.info(f"Loaded {len(entries)} knowledge base entries from {self.file_path}")
            
            return self._knowledge_base
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in knowledge base file: {e}")
            return KnowledgeBase(entries=[])
        except Exception as e:
            logger.error(f"Failed to load knowledge base: {e}")
            return KnowledgeBase(entries=[])
    
    def reload(self) -> KnowledgeBase:
        """Reload knowledge base from file."""
        return self.load()
    
    @property
    def knowledge_base(self) -> KnowledgeBase:
        """Get loaded knowledge base (lazy load)."""
        if self._knowledge_base is None:
            self._knowledge_base = self.load()
        return self._knowledge_base


# Global knowledge base loader instance
_loader: Optional[KnowledgeBaseLoader] = None


def load_knowledge_base(file_path: str) -> KnowledgeBase:
    """
    Load knowledge base from file (singleton pattern).
    
    Args:
        file_path: Path to knowledge base JSON file
        
    Returns:
        KnowledgeBase instance
    """
    global _loader
    
    if _loader is None or _loader.file_path != Path(file_path):
        _loader = KnowledgeBaseLoader(file_path)
    
    return _loader.knowledge_base
