"""Knowledge base schemas and models."""
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class KnowledgeEntry(BaseModel):
    """Single knowledge base entry (Q&A pair)."""
    question: str = Field(..., description="Question or query")
    answer: str = Field(..., description="Answer or response")
    category: Optional[str] = Field(None, description="Category or topic")
    language: Optional[str] = Field(None, description="Language code")
    keywords: List[str] = Field(default_factory=list, description="Search keywords")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        frozen = False


class KnowledgeBase(BaseModel):
    """Knowledge base container."""
    entries: List[KnowledgeEntry] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def search(self, query: str, language: Optional[str] = None, limit: int = 5) -> List[KnowledgeEntry]:
        """
        Search knowledge base for relevant entries.
        
        Args:
            query: Search query
            language: Filter by language code
            limit: Maximum number of results
            
        Returns:
            List of matching knowledge entries
        """
        query_lower = query.lower()
        results = []
        
        for entry in self.entries:
            # Filter by language if specified
            if language and entry.language and entry.language != language:
                continue
            
            # Simple keyword matching
            score = 0
            if query_lower in entry.question.lower():
                score += 10
            
            for keyword in entry.keywords:
                if keyword.lower() in query_lower:
                    score += 5
            
            if score > 0:
                results.append((score, entry))
        
        # Sort by score and return top results
        results.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in results[:limit]]
    
    def get_by_category(self, category: str) -> List[KnowledgeEntry]:
        """Get all entries in a category."""
        return [entry for entry in self.entries if entry.category == category]
    
    def get_by_language(self, language: str) -> List[KnowledgeEntry]:
        """Get all entries for a language."""
        return [entry for entry in self.entries if entry.language == language]
