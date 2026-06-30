"""
Phonetic-semantic embedding module for cognate detection.

Uses count-based TF-IDF vectors for phonetic embeddings (based on PWESuite)
and dense sentence-transformer embeddings for semantic similarity (captures synonymy).

Uses FAISS for fast approximate nearest neighbor search when available.
"""

# Set OpenMP/threading environment variables before importing numpy/sklearn
# This prevents pthread_mutex_init errors on macOS (especially Apple Silicon)
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import pickle
from pathlib import Path
from typing import Optional

import numpy as np
import panphon
from sklearn.decomposition import PCA
from sklearn.feature_extraction.text import TfidfVectorizer

# Try to use sentence-transformers for dense semantic embeddings
try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False

# Try to use FAISS for fast vector search, fall back to sklearn if unavailable
try:
    import faiss
    HAS_FAISS = True
except ImportError:
    from sklearn.metrics.pairwise import cosine_distances
    HAS_FAISS = False


class CognateEmbedder:
    """
    Computes phonetic and semantic embeddings for cognate detection.
    
    Phonetic embeddings use TF-IDF on IPA character n-grams (PWESuite count_based).
    Semantic embeddings use dense sentence-transformers (captures synonymy).
    
    Uses FAISS for fast approximate nearest neighbor search when available.
    """
    
    # Sentence transformer model for semantic embeddings (loaded lazily)
    _sentence_model: Optional["SentenceTransformer"] = None
    
    def __init__(
        self,
        phonetic_dim: int = 300,
        semantic_dim: int = 384,  # all-MiniLM-L6-v2 output dimension
        alpha: float = 0.4,  # Optimal value from cross-validation on 832 cognate sets
        use_pca: bool = True,
        use_dense_semantic: bool = True,  # Use sentence-transformers for semantic
    ):
        """
        Args:
            phonetic_dim: Dimension of phonetic embeddings
            semantic_dim: Dimension of semantic embeddings (384 for MiniLM, 300 for TF-IDF)
            alpha: Weight for phonetic similarity (1-alpha for semantic)
            use_pca: Whether to reduce TF-IDF dimensions with PCA (phonetic only)
            use_dense_semantic: Use sentence-transformers for semantic embeddings (captures synonymy)
        """
        self.phonetic_dim = phonetic_dim
        self.semantic_dim = semantic_dim
        self.alpha = alpha
        self.use_pca = use_pca
        self.use_dense_semantic = use_dense_semantic and HAS_SENTENCE_TRANSFORMERS
        
        self.ft = panphon.FeatureTable()
        
        # Vectorizers (fitted on corpus)
        self.phonetic_vectorizer: Optional[TfidfVectorizer] = None
        self.semantic_vectorizer: Optional[TfidfVectorizer] = None  # Fallback if no sentence-transformers
        
        # PCA transformers (optional, for phonetic only)
        self.phonetic_pca: Optional[PCA] = None
        self.semantic_pca: Optional[PCA] = None  # Fallback TF-IDF PCA
        
        # Cached embeddings for the lexicon
        self.phonetic_embeddings: Optional[np.ndarray] = None
        self.semantic_embeddings: Optional[np.ndarray] = None
        self.refids: Optional[list] = None
        
        # FAISS index for combined embeddings (built on first query or after fit)
        self._faiss_index = None
        self._combined_embeddings: Optional[np.ndarray] = None
        
        self._fitted = False
    
    @classmethod
    def _get_sentence_model(cls) -> "SentenceTransformer":
        """Get or load the sentence transformer model (singleton)."""
        if cls._sentence_model is None:
            print("Loading sentence-transformers model (all-MiniLM-L6-v2)...")
            cls._sentence_model = SentenceTransformer("all-MiniLM-L6-v2")
            print("Done.")
        return cls._sentence_model
    
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
        
        # Apply PCA to phonetic embeddings if requested
        if self.use_pca:
            n_phonetic = min(self.phonetic_dim, phonetic_matrix.shape[0], phonetic_matrix.shape[1])
            self.phonetic_pca = PCA(n_components=n_phonetic, whiten=True)
            phonetic_matrix = self.phonetic_pca.fit_transform(phonetic_matrix)
        
        self.phonetic_embeddings = phonetic_matrix
        
        # Semantic embeddings: use sentence-transformers if available (captures synonymy!)
        if self.use_dense_semantic:
            print(f"Computing dense semantic embeddings for {len(glosses)} glosses...")
            model = self._get_sentence_model()
            # Prepare glosses - handle empty/None values
            semantic_data = [g.lower().strip() if g else "unknown" for g in glosses]
            # Batch encode for efficiency
            semantic_matrix = model.encode(
                semantic_data,
                batch_size=128,
                show_progress_bar=True,
                normalize_embeddings=True,  # L2 normalize for cosine similarity
            )
            self.semantic_dim = semantic_matrix.shape[1]  # Update to actual model dimension
            print(f"Done. Semantic embedding dim: {self.semantic_dim}")
        else:
            # Fallback to TF-IDF (doesn't capture synonymy)
            print("Warning: Using TF-IDF for semantic embeddings (no synonymy support)")
            semantic_data = [g.lower() if g else "" for g in glosses]
            max_features = self.semantic_dim if not self.use_pca else 1024
            self.semantic_vectorizer = TfidfVectorizer(
                max_features=max_features,
                ngram_range=(1, 2),
                analyzer="word",
                min_df=1,
            )
            semantic_matrix = self.semantic_vectorizer.fit_transform(semantic_data)
            semantic_matrix = np.asarray(semantic_matrix.todense())
            
            if self.use_pca:
                n_semantic = min(self.semantic_dim, semantic_matrix.shape[0], semantic_matrix.shape[1])
                self.semantic_pca = PCA(n_components=n_semantic, whiten=True)
                semantic_matrix = self.semantic_pca.fit_transform(semantic_matrix)
        
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
        gloss = gloss.lower().strip() if gloss else "unknown"
        
        if self.use_dense_semantic:
            # Use sentence-transformers (captures synonymy!)
            model = self._get_sentence_model()
            vec = model.encode([gloss], normalize_embeddings=True)[0]
            return vec
        else:
            # Fallback to TF-IDF
            vec = self.semantic_vectorizer.transform([gloss])
            vec = np.asarray(vec.todense())
            if self.use_pca and self.semantic_pca is not None:
                vec = self.semantic_pca.transform(vec)
            return vec[0]
    
    def _build_faiss_index(self) -> None:
        """Build FAISS index for fast similarity search."""
        if not HAS_FAISS:
            return
        
        # Normalize embeddings for cosine similarity (FAISS uses inner product)
        phon_norm = self.phonetic_embeddings / (np.linalg.norm(self.phonetic_embeddings, axis=1, keepdims=True) + 1e-10)
        sem_norm = self.semantic_embeddings / (np.linalg.norm(self.semantic_embeddings, axis=1, keepdims=True) + 1e-10)
        
        # Concatenate and weight embeddings
        # Scale by sqrt of alpha so that inner product gives weighted sum
        self._combined_embeddings = np.hstack([
            phon_norm * np.sqrt(self.alpha),
            sem_norm * np.sqrt(1 - self.alpha)
        ]).astype(np.float32)
        
        # Build index - use IndexFlatIP for exact inner product (cosine after normalization)
        dim = self._combined_embeddings.shape[1]
        self._faiss_index = faiss.IndexFlatIP(dim)
        self._faiss_index.add(self._combined_embeddings)
    
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
        
        # Use FAISS if available and index is built
        if HAS_FAISS:
            # Build index on first query if not already built
            if self._faiss_index is None:
                self._build_faiss_index()
            
            # Normalize and combine query embedding
            q_phon_norm = q_phon / (np.linalg.norm(q_phon) + 1e-10)
            q_sem_norm = q_sem / (np.linalg.norm(q_sem) + 1e-10)
            q_combined = np.hstack([
                q_phon_norm * np.sqrt(self.alpha),
                q_sem_norm * np.sqrt(1 - self.alpha)
            ]).astype(np.float32).reshape(1, -1)
            
            # Search all items (we need all for filtering)
            k = len(self.refids)
            similarities, indices = self._faiss_index.search(q_combined, k)
            
            # Convert similarities to distances (1 - similarity for cosine)
            # Inner product of normalized vectors gives cosine similarity
            results = []
            for sim, idx in zip(similarities[0], indices[0]):
                if idx < 0:  # FAISS returns -1 for empty slots
                    continue
                refid = self.refids[idx]
                dist = 1.0 - sim  # Convert similarity to distance
                if exclude_langid is not None and langids is not None:
                    if langids[idx] == exclude_langid:
                        continue
                results.append((refid, float(dist)))
        else:
            # Fallback to sklearn cosine_distances
            from sklearn.metrics.pairwise import cosine_distances
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
    
    def update_embedding(self, refid: int, form: str, gloss: str) -> None:
        """
        Add or update an embedding for a single item.
        
        Args:
            refid: The reflex ID
            form: IPA form
            gloss: Gloss/meaning
        """
        if not self._fitted:
            raise RuntimeError("Embedder not fitted. Call fit() first.")
        
        # Compute embeddings for the new item
        phon_emb = self._embed_phonetic(form)
        sem_emb = self._embed_semantic(gloss)
        
        # Check if refid already exists
        if refid in self.refids:
            idx = self.refids.index(refid)
            self.phonetic_embeddings[idx] = phon_emb
            self.semantic_embeddings[idx] = sem_emb
        else:
            # Add new entry
            self.refids.append(refid)
            self.phonetic_embeddings = np.vstack([self.phonetic_embeddings, phon_emb])
            self.semantic_embeddings = np.vstack([self.semantic_embeddings, sem_emb])
        
        # Invalidate FAISS index so it gets rebuilt on next query
        self._faiss_index = None
        self._combined_embeddings = None
    
    def save(self, path: str) -> None:
        """Save fitted embedder to file."""
        data = {
            "phonetic_dim": self.phonetic_dim,
            "semantic_dim": self.semantic_dim,
            "alpha": self.alpha,
            "use_pca": self.use_pca,
            "use_dense_semantic": self.use_dense_semantic,
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
        
        # Handle legacy cache files without use_dense_semantic
        saved_dense_semantic = data.get("use_dense_semantic", False)
        
        # Check if cache was built with dense semantics but we don't have sentence-transformers
        # In this case, we need to signal that cache should be rebuilt
        if saved_dense_semantic and not HAS_SENTENCE_TRANSFORMERS:
            raise RuntimeError(
                "Cached embedder was built with sentence-transformers but the module is not "
                "available. Please install sentence-transformers or delete the cache to rebuild: "
                "pip install sentence-transformers"
            )
        
        # Check if cache was built without dense semantics but we don't have the vectorizer
        if not saved_dense_semantic and data.get("semantic_vectorizer") is None:
            raise RuntimeError(
                "Cached embedder has no semantic vectorizer. Please delete the cache to rebuild."
            )
        
        embedder = cls(
            phonetic_dim=data["phonetic_dim"],
            semantic_dim=data["semantic_dim"],
            alpha=data["alpha"],
            use_pca=data["use_pca"],
            use_dense_semantic=saved_dense_semantic,
        )
        embedder.phonetic_vectorizer = data["phonetic_vectorizer"]
        embedder.semantic_vectorizer = data["semantic_vectorizer"]
        embedder.phonetic_pca = data["phonetic_pca"]
        embedder.semantic_pca = data["semantic_pca"]
        embedder.phonetic_embeddings = data["phonetic_embeddings"]
        embedder.semantic_embeddings = data["semantic_embeddings"]
        embedder.refids = data["refids"]
        embedder._fitted = data["_fitted"]
        
        # Pre-build FAISS index for fast queries
        if HAS_FAISS and embedder._fitted:
            embedder._build_faiss_index()
        
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
