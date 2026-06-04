"""
Learn optimal alpha weight for cognate detection from ground-truth cognate sets.

Uses the reflex_of table as ground truth and evaluates recall@k at different alpha values.
"""

import sqlite3
from collections import defaultdict

import numpy as np
from sklearn.metrics.pairwise import cosine_distances

from embeddings import CognateEmbedder


def load_cognate_sets(db_path: str) -> dict[int, list[tuple[int, int, str, str]]]:
    """
    Load cognate sets from database.
    
    Returns:
        Dict mapping prefid -> list of (refid, langid, form, gloss) tuples
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    c.execute('''
        SELECT ro.prefid, ro.refid, r.langid, r.form, r.gloss
        FROM reflex_of ro
        JOIN reflexes r ON r.refid = ro.refid
    ''')
    
    cognate_sets = defaultdict(list)
    for prefid, refid, langid, form, gloss in c.fetchall():
        cognate_sets[prefid].append((refid, langid, form or "", gloss or ""))
    
    conn.close()
    return dict(cognate_sets)


def evaluate_alpha_fast(
    embedder: CognateEmbedder,
    langids: list[int],
    cognate_sets: dict[int, list],
    alpha: float,
    k_values: list[int] = [5, 10, 20, 50],
    max_queries_per_set: int = 2,
) -> dict[str, float]:
    """
    Evaluate recall@k for a given alpha by working directly with pre-computed embeddings.
    
    Much faster than calling find_similar() repeatedly.
    """
    # Build refid -> index lookup
    refid_to_idx = {refid: i for i, refid in enumerate(embedder.refids)}
    
    recalls = {f"recall@{k}": [] for k in k_values}
    mrr_values = []
    
    max_k = max(k_values)
    
    # For each cognate set with >= 2 members
    for prefid, members in cognate_sets.items():
        if len(members) < 2:
            continue
        
        # Sample members to query
        query_members = members[:max_queries_per_set]
        
        for query_refid, query_langid, _, _ in query_members:
            if query_refid not in refid_to_idx:
                continue
            
            query_idx = refid_to_idx[query_refid]
            
            # Target cognates (same set, different language)
            target_idxs = {
                refid_to_idx[m[0]] for m in members 
                if m[0] != query_refid and m[1] != query_langid and m[0] in refid_to_idx
            }
            
            if not target_idxs:
                continue
            
            # Compute distances from query to all items using pre-computed embeddings
            q_phon = embedder.phonetic_embeddings[query_idx:query_idx+1]
            q_sem = embedder.semantic_embeddings[query_idx:query_idx+1]
            
            phon_dists = cosine_distances(q_phon, embedder.phonetic_embeddings)[0]
            sem_dists = cosine_distances(q_sem, embedder.semantic_embeddings)[0]
            combined_dists = alpha * phon_dists + (1 - alpha) * sem_dists
            
            # Exclude same language
            for i, lid in enumerate(langids):
                if lid == query_langid:
                    combined_dists[i] = float('inf')
            
            # Get top-k indices
            top_k_indices = np.argsort(combined_dists)[:max_k]
            
            # Compute recall@k
            for k in k_values:
                hits = len(target_idxs & set(top_k_indices[:k]))
                recall = hits / len(target_idxs)
                recalls[f"recall@{k}"].append(recall)
            
            # Compute MRR
            for rank, idx in enumerate(top_k_indices, 1):
                if idx in target_idxs:
                    mrr_values.append(1.0 / rank)
                    break
            else:
                mrr_values.append(0.0)
    
    metrics = {key: np.mean(values) if values else 0.0 for key, values in recalls.items()}
    metrics["mrr"] = np.mean(mrr_values) if mrr_values else 0.0
    metrics["n_queries"] = len(mrr_values)
    
    return metrics


def optimize_alpha(
    db_path: str = "db/borderlands.sqlite3",
    cache_path: str = "db/embedder_cache.pkl",
    alpha_range: tuple[float, float] = (0.0, 1.0),
    n_steps: int = 11,
) -> tuple[float, dict]:
    """
    Find optimal alpha via grid search.
    
    Returns:
        Tuple of (best_alpha, all_results)
    """
    print("Loading embedder...")
    embedder = CognateEmbedder.load(cache_path)
    
    # Load langids
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT refid, langid FROM reflexes")
    langid_map = {r[0]: r[1] for r in c.fetchall()}
    conn.close()
    langids = [langid_map.get(refid, -1) for refid in embedder.refids]
    
    print("Loading cognate sets...")
    cognate_sets = load_cognate_sets(db_path)
    print(f"  Found {len(cognate_sets)} cognate sets")
    
    # Grid search
    alphas = np.linspace(alpha_range[0], alpha_range[1], n_steps)
    results = {}
    
    print("\nEvaluating alpha values...")
    print(f"{'alpha':>6} {'recall@5':>10} {'recall@10':>10} {'recall@20':>10} {'MRR':>10}")
    print("-" * 50)
    
    best_alpha = 0.5
    best_mrr = 0.0
    
    for alpha in alphas:
        metrics = evaluate_alpha_fast(embedder, langids, cognate_sets, alpha)
        results[alpha] = metrics
        
        print(f"{alpha:6.2f} {metrics['recall@5']:10.4f} {metrics['recall@10']:10.4f} "
              f"{metrics['recall@20']:10.4f} {metrics['mrr']:10.4f}")
        
        if metrics["mrr"] > best_mrr:
            best_mrr = metrics["mrr"]
            best_alpha = alpha
    
    print("-" * 50)
    print(f"\nBest alpha: {best_alpha:.2f} (MRR={best_mrr:.4f})")
    
    return best_alpha, results


if __name__ == "__main__":
    best_alpha, results = optimize_alpha()
    
    print("\n" + "=" * 50)
    print(f"RECOMMENDATION: Set alpha = {best_alpha:.2f}")
    print("=" * 50)
