"""
Phonetic-semantic embedding module for cognate detection.

Uses count-based TF-IDF vectors for phonetic embeddings (based on PWESuite)
and optional semantic embeddings for gloss similarity.
"""

import pickle
from pathlib import Path
from typing import Optional

import numpy as np
import panphon
from sklearn.decomposition import PCA
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_distances


class CognateEmbedder:
    """
    Computes phonetic and semantic embeddings for cognate detection.
    
    Phonetic embeddings use TF-IDF on IPA character n-grams (PWESuite count_based).
    Semantic embeddings use TF-IDF on gloss words (simple but effective baseline).
    """
    
    def __init__(
        self,
        phonetic_dim: int = 300,
        semantic_dim: int = 300,
        alpha: float = 0.4,  # Optimal value from cross-validation on 832 cognate sets
        use_pca: bool = True,
    ):
        """
        Args:
            phonetic_dim: Dimension of phonetic embeddings
            semantic_dim: Dimension of semantic embeddings  
            alpha: Weight for phonetic similarity (1-alpha for semantic)
            use_pca: Whether to reduce TF-IDF dimensions with PCA
        """
        self.phonetic_dim = phonetic_dim
        self.semantic_dim = semantic_dim
        self.alpha = alpha
        self.use_pca = use_pca
        
        self.ft = panphon.FeatureTable()
        
        # Vectorizers (fitted on corpus)
        self.phonetic_vectorizer: Optional[TfidfVectorizer] = None
        self.semantic_vectorizer: Optional[TfidfVectorizer] = None
        
        # PCA transformers (optional)
        self.phonetic_pca: Optional[PCA] = None
        self.semantic_pca: Optional[PCA] = None
        
        # Cached embeddings for the lexicon
        self.phonetic_embeddings: Optional[np.ndarray] = None
        self.semantic_embeddings: Optional[np.ndarray] = None
        self.refids: Optional[list] = None
        
        self._fitted = False
    
    def _segment_ipa(self, form: str) -> str:
        """Convert IPA form to space-separated segments for TF-IDF."""
        try:
            segs = self.ft.ipa_segs(form)
            return " ".join(segs)
        except Exception:
            # Fallback: treat each character as a segment
            return " ".join(list(form))
    
    def fit(self, forms: list[str], glosses: list[str], refids: list[int]) -> "CognateEmbedder":
        """
        Fit the embedder on a corpus of forms and glosses.
        
        Args:
            forms: List of IPA forms
            glosses: List of glosses/meanings
            refids: List of reflex IDs (for lookup)
        """
        self.refids = list(refids)
        
        # Prepare phonetic data: IPA segmented
        phonetic_data = [self._segment_ipa(f) for f in forms]
        
        # Prepare semantic data: glosses as-is
        semantic_data = [g.lower() if g else "" for g in glosses]
        
        # Fit phonetic TF-IDF
        max_features = self.phonetic_dim if not self.use_pca else 1024
        self.phonetic_vectorizer = TfidfVectorizer(
            max_features=max_features,
            ngram_range=(1, 3),
            analyzer="char",
            min_df=1,
        )
        phonetic_matrix = self.phonetic_vectorizer.fit_transform(phonetic_data)
        phonetic_matrix = np.asarray(phonetic_matrix.todense())
        
        # Fit semantic TF-IDF
        max_features = self.semantic_dim if not self.use_pca else 1024
        self.semantic_vectorizer = TfidfVectorizer(
            max_features=max_features,
            ngram_range=(1, 2),
            analyzer="word",
            min_df=1,
        )
        semantic_matrix = self.semantic_vectorizer.fit_transform(semantic_data)
        semantic_matrix = np.asarray(semantic_matrix.todense())
        
        # Apply PCA if requested
        if self.use_pca:
            n_phonetic = min(self.phonetic_dim, phonetic_matrix.shape[0], phonetic_matrix.shape[1])
            self.phonetic_pca = PCA(n_components=n_phonetic, whiten=True)
            phonetic_matrix = self.phonetic_pca.fit_transform(phonetic_matrix)
            
            n_semantic = min(self.semantic_dim, semantic_matrix.shape[0], semantic_matrix.shape[1])
            self.semantic_pca = PCA(n_components=n_semantic, whiten=True)
            semantic_matrix = self.semantic_pca.fit_transform(semantic_matrix)
        
        self.phonetic_embeddings = phonetic_matrix
        self.semantic_embeddings = semantic_matrix
        self._fitted = True
        
        return self
    
    def _embed_phonetic(self, form: str) -> np.ndarray:
        """Compute phonetic embedding for a single form."""
        segmented = self._segment_ipa(form)
        vec = self.phonetic_vectorizer.transform([segmented])
        vec = np.asarray(vec.todense())
        if self.use_pca and self.phonetic_pca is not None:
            vec = self.phonetic_pca.transform(vec)
        return vec[0]
    
    def _embed_semantic(self, gloss: str) -> np.ndarray:
        """Compute semantic embedding for a single gloss."""
        gloss = gloss.lower() if gloss else ""
        vec = self.semantic_vectorizer.transform([gloss])
        vec = np.asarray(vec.todense())
        if self.use_pca and self.semantic_pca is not None:
            vec = self.semantic_pca.transform(vec)
        return vec[0]
    
    def find_similar(
        self,
        query_form: str,
        query_gloss: str,
        exclude_langid: Optional[int] = None,
        langids: Optional[list[int]] = None,
        top_k: Optional[int] = None,
    ) -> list[tuple[int, float]]:
        """
        Find similar items in the fitted corpus.
        
        Args:
            query_form: IPA form to match
            query_gloss: Gloss to match
            exclude_langid: Language ID to exclude from results
            langids: List of language IDs for each item (for filtering)
            top_k: Return only top k results (None for all)
            
        Returns:
            List of (refid, distance) tuples, sorted by distance ascending
        """
        if not self._fitted:
            raise RuntimeError("Embedder not fitted. Call fit() first.")
        
        # Compute query embeddings
        q_phon = self._embed_phonetic(query_form)
        q_sem = self._embed_semantic(query_gloss)
        
        # Compute distances to all items
        phon_dists = cosine_distances([q_phon], self.phonetic_embeddings)[0]
        sem_dists = cosine_distances([q_sem], self.semantic_embeddings)[0]
        
        # Combined distance (lower is better)
        combined_dists = self.alpha * phon_dists + (1 - self.alpha) * sem_dists
        
        # Build results with filtering
        results = []
        for i, (refid, dist) in enumerate(zip(self.refids, combined_dists)):
            if exclude_langid is not None and langids is not None:
                if langids[i] == exclude_langid:
                    continue
            results.append((refid, float(dist)))
        
        # Sort by distance
        results.sort(key=lambda x: x[1])
        
        if top_k is not None:
            results = results[:top_k]
        
        return results
    
    def save(self, path: str) -> None:
        """Save fitted embedder to file."""
        data = {
            "phonetic_dim": self.phonetic_dim,
            "semantic_dim": self.semantic_dim,
            "alpha": self.alpha,
            "use_pca": self.use_pca,
            "phonetic_vectorizer": self.phonetic_vectorizer,
            "semantic_vectorizer": self.semantic_vectorizer,
            "phonetic_pca": self.phonetic_pca,
            "semantic_pca": self.semantic_pca,
            "phonetic_embeddings": self.phonetic_embeddings,
            "semantic_embeddings": self.semantic_embeddings,
            "refids": self.refids,
            "_fitted": self._fitted,
        }
        with open(path, "wb") as f:
            pickle.dump(data, f)
    
    @classmethod
    def load(cls, path: str) -> "CognateEmbedder":
        """Load fitted embedder from file."""
        with open(path, "rb") as f:
            data = pickle.load(f)
        
        embedder = cls(
            phonetic_dim=data["phonetic_dim"],
            semantic_dim=data["semantic_dim"],
            alpha=data["alpha"],
            use_pca=data["use_pca"],
        )
        embedder.phonetic_vectorizer = data["phonetic_vectorizer"]
        embedder.semantic_vectorizer = data["semantic_vectorizer"]
        embedder.phonetic_pca = data["phonetic_pca"]
        embedder.semantic_pca = data["semantic_pca"]
        embedder.phonetic_embeddings = data["phonetic_embeddings"]
        embedder.semantic_embeddings = data["semantic_embeddings"]
        embedder.refids = data["refids"]
        embedder._fitted = data["_fitted"]
        
        return embedder


def build_embedder_from_db(db_path: str, alpha: float = 0.4) -> tuple[CognateEmbedder, list[int]]:
    """
    Build and fit an embedder from a SQLite database.
    
    Args:
        db_path: Path to the SQLite database
        alpha: Weight for phonetic vs semantic (higher = more phonetic)
        
    Returns:
        Tuple of (fitted embedder, list of langids for each reflex)
    """
    import sqlite3
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    # Use ipaform for phonetic embeddings (normalized IPA without tones)
    c.execute("SELECT refid, langid, ipaform, gloss FROM reflexes")
    rows = c.fetchall()
    conn.close()
    
    refids = [r[0] for r in rows]
    langids = [r[1] for r in rows]
    # Use ipaform for phonetic similarity; fallback to empty string if NULL
    forms = [r[2] or "" for r in rows]
    glosses = [r[3] or "" for r in rows]
    
    embedder = CognateEmbedder(alpha=alpha)
    embedder.fit(forms, glosses, refids)
    
    return embedder, langids
