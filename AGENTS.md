# PyComparator - Agent Memory

## Project Overview

Web application for building cognate sets and associating reconstructions with them in historical linguistics research.

## Key Components

- **comparator.py**: Flask web application (main entry point)
- **embeddings.py**: Cognate embedding module for fast similarity search
- **db/borderlands.sqlite3**: SQLite database with reflexes and cognate sets
- **db/embedder_cache.pkl**: Pre-computed embeddings cache (42,570 reflexes)

## Running the Application

```bash
cd /Users/mortensen/Projects/pycomparator
/Users/mortensen/miniforge3/bin/flask --app comparator run --port 5001
```

## Cognate Detection System (June 2026)

### Architecture

The cognate detection system uses pre-computed phonetic-semantic embeddings for fast similarity search:

1. **Phonetic Embeddings**: TF-IDF on IPA character n-grams (1-3 chars) via panphon segmentation
2. **Semantic Embeddings**: TF-IDF on gloss word n-grams (1-2 words)
3. **Combined Score**: `distance = α * phonetic_dist + (1-α) * semantic_dist`

### Key Parameters

- **alpha**: Weight for phonetic vs semantic (0=semantic only, 1=phonetic only, **optimal=0.4**)
- **Embedding dimensions**: 300 for both phonetic and semantic (PCA reduced from 1024)

### Alpha Optimization Results (832 cognate sets)

```
alpha   recall@5    recall@10    recall@20        MRR
----------------------------------------------------------------------
 0.00     0.1251       0.2208       0.4002     0.2908
 0.10     0.3411       0.4505       0.5622     0.5361
 0.20     0.3452       0.4547       0.5696     0.5400
 0.30     0.3514       0.4599       0.5757     0.5451
 0.40     0.3542       0.4672       0.5833     0.5485 <-- BEST
 0.50     0.3517       0.4667       0.5781     0.5466
 0.60     0.3053       0.3888       0.4760     0.5082
 0.70     0.2241       0.2887       0.3433     0.4229
 0.80     0.1592       0.2020       0.2423     0.3189
```

**Optimal alpha = 0.40** balances phonetic and semantic similarity:
- 58% of cognates found in top 20 results
- MRR of 0.55 (first correct cognate typically in top 2)

### Performance

- Query time: O(n) vector operations (fast) vs O(n) expensive feature edit distance (old)
- Pre-computation: ~1 second to load 42,570 reflexes
- Cache persistence: db/embedder_cache.pkl

### API Endpoints

- `GET /findpotcogs?langid=<id>&form=<ipa>&gloss=<text>&alpha=0.5` - Find potential cognates
- `GET /potcogs?start=0&length=10` - Retrieve ranked results

### Dependencies

- panphon (IPA segmentation and phonetic features)
- scikit-learn (TF-IDF, PCA, cosine distance)
- numpy
- flask

### Future Improvements

- [x] Learn optimal alpha from ground-truth cognate sets (reflex_of table) ✓ Done: alpha=0.4
- [ ] Optional: sentence-transformers for higher-quality semantic embeddings
- [ ] Optional: FAISS index for sub-linear search if lexicon grows large
