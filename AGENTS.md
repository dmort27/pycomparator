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

### IPA Normalization (June 2026)

The system normalizes transcriptions to canonical IPA using `ipa_normalize.py`:

1. **Tone removal**: NFD decomposition removes combining tone marks (´ ` ˆ ˇ etc.)
2. **Affricate ligatures**: ts→t͡s, dʒ→d͡ʒ, tʃ→t͡ʃ, etc.
3. **Double vowels**: aa→aː, ee→eː, etc.
4. **y→j conversion**: When not between consonants

**Database schema**: `ipaform` column stores normalized forms.

**Population**: `populate_ipaform.py` batch-updates all reflexes (42,570 total, 110 empty).

**Usage**: ipaform is used throughout for phonetic operations:
- `comparator.py`: /findpotcogs, /alignment, /addnewreflex, /updatereflex, /addnewset
- `correspondence.py`: extract_correspondence_sets_for_protolang() uses ipaform for alignment
- `embeddings.py`: build_embedder_from_db() uses ipaform for TF-IDF vectorization

### Future Improvements

- [x] Learn optimal alpha from ground-truth cognate sets (reflex_of table) ✓ Done: alpha=0.4
- [x] IPA normalization for consistent phonetic matching ✓ Done: ipaform column
- [x] Data upload feature for importing lexicon files ✓ Done: June 2026
- [ ] Optional: sentence-transformers for higher-quality semantic embeddings
- [ ] Optional: FAISS index for sub-linear search if lexicon grows large

## Data Upload Feature (June 2026)

### Overview

Allows users to upload lexicon data files (CSV/TSV) with automatic IPA normalization and syllabification.

### Components

- **form_processor.py**: Form processing module
  - `process_form(form)`: Normalize IPA, remove existing hyphens, re-syllabify
  - `parse_lexicon_file(content)`: Parse CSV/TSV with gloss and form columns
  - `detect_delimiter(content)`: Auto-detect tab vs comma delimiter
  - Uses `syllabiphon` for syllabification

- **templates/upload_data_dialog.jinja2**: Upload dialog template
  - Language name input
  - Proto-language selection (multiple select)
  - File input with preview support

- **Flask routes in comparator.py**:
  - `GET /upload_dialog`: Render upload dialog with proto-language options
  - `POST /preview_upload`: Preview file processing (first 10 entries)
  - `POST /upload_data`: Full upload with database insertion

- **JavaScript handlers in comparator.js**:
  - Upload dialog with Preview/Upload/Cancel buttons
  - File preview showing original vs processed forms
  - Progress indicator during upload
  - Auto-reload reflexes table after successful upload

### Usage

1. Click "Upload Data" button in toolbar
2. Enter language name
3. Select parent proto-language(s)
4. Choose CSV/TSV file (gloss in col 1, form in col 2)
5. Click "Preview" to verify processing
6. Click "Upload" to insert into database

### Test Data

- `data/khunggoi.tsv`: 430 entries (uploaded as langid=70)
- `data/phadang.tsv`: 399 entries (uploaded as langid=71)
