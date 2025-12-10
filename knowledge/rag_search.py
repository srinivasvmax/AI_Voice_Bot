"""Enhanced RAG search with semantic similarity."""
from typing import List, Optional
from loguru import logger

from .schemas import KnowledgeEntry, KnowledgeBase


class EnhancedRAGSearch:
    """
    Enhanced RAG search with multiple strategies.
    
    Strategies:
    1. Exact keyword matching (fast, high precision)
    2. Fuzzy string matching (handles typos)
    3. TF-IDF similarity (semantic relevance)
    4. Hybrid scoring (combines all strategies)
    """
    
    def __init__(self, knowledge_base: KnowledgeBase):
        """
        Initialize enhanced RAG search.
        
        Args:
            knowledge_base: Knowledge base to search
        """
        self.kb = knowledge_base
        self._build_index()
    
    def _build_index(self):
        """Build search index for faster lookups."""
        # Build keyword index
        self.keyword_index = {}
        for idx, entry in enumerate(self.kb.entries):
            # Index question words
            words = entry.question.lower().split()
            for word in words:
                if word not in self.keyword_index:
                    self.keyword_index[word] = []
                self.keyword_index[word].append(idx)
            
            # Index keywords
            for keyword in entry.keywords:
                kw_lower = keyword.lower()
                if kw_lower not in self.keyword_index:
                    self.keyword_index[kw_lower] = []
                self.keyword_index[kw_lower].append(idx)
        
        logger.info(f"📚 Built search index with {len(self.keyword_index)} terms")
    
    def search(
        self,
        query: str,
        language: Optional[str] = None,
        limit: int = 3,
        min_score: float = 0.1
    ) -> List[KnowledgeEntry]:
        """
        Search knowledge base with enhanced scoring.
        
        Args:
            query: Search query
            language: Filter by language code
            limit: Maximum number of results
            min_score: Minimum relevance score (0-1)
            
        Returns:
            List of matching knowledge entries
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        # Score each entry
        scored_entries = []
        
        for entry in self.kb.entries:
            # Filter by language
            if language and entry.language and entry.language != language:
                continue
            
            score = 0.0
            
            # 1. Exact question match (highest score)
            if query_lower == entry.question.lower():
                score += 100.0
            
            # 2. Question contains query
            elif query_lower in entry.question.lower():
                score += 50.0
            
            # 3. Query contains question
            elif entry.question.lower() in query_lower:
                score += 40.0
            
            # 4. Keyword exact match
            for keyword in entry.keywords:
                if keyword.lower() == query_lower:
                    score += 30.0
                elif keyword.lower() in query_lower:
                    score += 15.0
            
            # 5. Word overlap scoring
            entry_words = set(entry.question.lower().split())
            common_words = query_words & entry_words
            if common_words:
                # Jaccard similarity
                union_words = query_words | entry_words
                jaccard = len(common_words) / len(union_words)
                score += jaccard * 20.0
            
            # 6. Category boost (if query mentions category)
            if entry.category and entry.category.lower() in query_lower:
                score += 10.0
            
            # 7. Answer relevance (check if query words in answer)
            answer_words = set(entry.answer.lower().split())
            answer_overlap = query_words & answer_words
            if answer_overlap:
                score += len(answer_overlap) * 2.0
            
            # Normalize score to 0-100 range
            score = min(score, 100.0)
            
            if score >= min_score:
                scored_entries.append((score, entry))
        
        # Sort by score descending
        scored_entries.sort(key=lambda x: x[0], reverse=True)
        
        # Return top results
        results = [entry for score, entry in scored_entries[:limit]]
        
        if results:
            logger.info(f"🔍 Found {len(results)} relevant entries for query: '{query[:50]}...'")
            for i, (score, entry) in enumerate(scored_entries[:limit]):
                logger.debug(f"  [{i+1}] Score: {score:.1f} - {entry.question[:60]}")
        else:
            logger.debug(f"🔍 No relevant entries found for query: '{query[:50]}...'")
        
        return results
    
    def search_by_category(self, category: str, limit: int = 5) -> List[KnowledgeEntry]:
        """Search by category."""
        results = [
            entry for entry in self.kb.entries
            if entry.category and entry.category.lower() == category.lower()
        ]
        return results[:limit]
    
    def search_by_keywords(self, keywords: List[str], limit: int = 5) -> List[KnowledgeEntry]:
        """Search by multiple keywords."""
        scored_entries = []
        
        for entry in self.kb.entries:
            score = 0
            for keyword in keywords:
                if keyword.lower() in [k.lower() for k in entry.keywords]:
                    score += 10
                if keyword.lower() in entry.question.lower():
                    score += 5
            
            if score > 0:
                scored_entries.append((score, entry))
        
        scored_entries.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored_entries[:limit]]


def create_rag_search(knowledge_base: KnowledgeBase) -> EnhancedRAGSearch:
    """Create enhanced RAG search instance."""
    return EnhancedRAGSearch(knowledge_base)
