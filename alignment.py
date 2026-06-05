"""
Cognate set alignment module.

Aligns phoneme sequences from cognate sets using phonological feature distance.
Produces column-by-column mappings of corresponding phonemes across languages.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

import numpy as np
import panphon
import panphon.distance


# Module-level singletons for efficiency
_feature_table: Optional[panphon.FeatureTable] = None
_distance: Optional[panphon.distance.Distance] = None

# Maximum distance for unknown segments (higher than any real phoneme pair)
MAX_DISTANCE = 100.0

# Default gap cost (tunable)
# Must be higher than typical substitution costs (weighted_feature_edit_distance)
# to prefer alignment over gaps for similar sounds. Typical substitution costs:
#   - Similar sounds (k/t, a/e, m/n): 1-2
#   - Different sounds (ʔ/k, k/g): 4-7
DEFAULT_GAP_COST = 6.0


def _get_feature_table() -> panphon.FeatureTable:
    """Get or create the singleton FeatureTable."""
    global _feature_table
    if _feature_table is None:
        _feature_table = panphon.FeatureTable()
    return _feature_table


def _get_distance() -> panphon.distance.Distance:
    """Get or create the singleton Distance calculator."""
    global _distance
    if _distance is None:
        _distance = panphon.distance.Distance()
    return _distance


@lru_cache(maxsize=10000)
def phoneme_distance(seg1: str, seg2: str) -> float:
    """
    Compute the weighted feature edit distance between two phonemes.
    
    Uses caching for efficiency. Unknown segments receive MAX_DISTANCE.
    
    Args:
        seg1: First phoneme (IPA)
        seg2: Second phoneme (IPA)
        
    Returns:
        Distance value (0 = identical, higher = more different)
    """
    if seg1 == seg2:
        return 0.0
    
    ft = _get_feature_table()
    
    # Check if segments are known
    if not ft.seg_known(seg1) or not ft.seg_known(seg2):
        return MAX_DISTANCE
    
    d = _get_distance()
    return d.weighted_feature_edit_distance(seg1, seg2)


def segment_ipa(form: str) -> list[str]:
    """
    Segment an IPA string into individual phonemes.
    
    Args:
        form: IPA string
        
    Returns:
        List of phoneme segments
    """
    ft = _get_feature_table()
    return ft.ipa_segs(form)


def extract_morpheme(form: str, morph_index: int) -> str:
    """
    Extract a specific morpheme from a compound form.
    
    Morphemes are separated by '-' or ' '.
    
    Args:
        form: Full form (possibly compound)
        morph_index: Index of morpheme to extract (0-based)
        
    Returns:
        The extracted morpheme, or full form if index out of range
    """
    # Split on both hyphen and space
    import re
    morphemes = re.split(r'[-\s]+', form)
    morphemes = [m for m in morphemes if m]  # Remove empty strings
    
    if not morphemes:
        return form
    
    if 0 <= morph_index < len(morphemes):
        return morphemes[morph_index]
    
    # Fallback to full form if index out of range
    return form


def pairwise_align(
    seq1: list[str],
    seq2: list[str],
    gap_cost: float = DEFAULT_GAP_COST
) -> tuple[list[str], list[str]]:
    """
    Align two phoneme sequences using Needleman-Wunsch algorithm.
    
    Args:
        seq1: First sequence of phonemes
        seq2: Second sequence of phonemes
        gap_cost: Cost of inserting a gap
        
    Returns:
        Tuple of (aligned_seq1, aligned_seq2) with '' for gaps
    """
    n, m = len(seq1), len(seq2)
    
    # Handle empty sequences
    if n == 0:
        return [''] * m, list(seq2)
    if m == 0:
        return list(seq1), [''] * n
    
    # DP matrix for costs
    dp = np.full((n + 1, m + 1), np.inf)
    dp[0, 0] = 0.0
    
    # Initialize first row and column (gap costs)
    for i in range(1, n + 1):
        dp[i, 0] = dp[i-1, 0] + gap_cost
    for j in range(1, m + 1):
        dp[0, j] = dp[0, j-1] + gap_cost
    
    # Fill DP matrix
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            subst_cost = phoneme_distance(seq1[i-1], seq2[j-1])
            dp[i, j] = min(
                dp[i-1, j-1] + subst_cost,  # substitution/match
                dp[i-1, j] + gap_cost,       # gap in seq2
                dp[i, j-1] + gap_cost        # gap in seq1
            )
    
    # Traceback to get alignment
    aligned1, aligned2 = [], []
    i, j = n, m
    
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            subst_cost = phoneme_distance(seq1[i-1], seq2[j-1])
            if dp[i, j] == dp[i-1, j-1] + subst_cost:
                aligned1.append(seq1[i-1])
                aligned2.append(seq2[j-1])
                i -= 1
                j -= 1
                continue
        
        if i > 0 and dp[i, j] == dp[i-1, j] + gap_cost:
            aligned1.append(seq1[i-1])
            aligned2.append('')
            i -= 1
        elif j > 0:
            aligned1.append('')
            aligned2.append(seq2[j-1])
            j -= 1
    
    # Reverse since we traced back from end
    aligned1.reverse()
    aligned2.reverse()
    
    return aligned1, aligned2


def find_center_sequence(sequences: list[list[str]]) -> int:
    """
    Find the sequence with minimum total distance to all others.
    
    Used when no protoform is available to select a center for star alignment.
    
    Args:
        sequences: List of phoneme sequences
        
    Returns:
        Index of the center sequence
    """
    if len(sequences) <= 1:
        return 0
    
    n = len(sequences)
    total_distances = []
    
    for i in range(n):
        total = 0.0
        for j in range(n):
            if i != j:
                # Quick approximation: sum of pairwise phoneme distances
                seq_i, seq_j = sequences[i], sequences[j]
                min_len = min(len(seq_i), len(seq_j))
                max_len = max(len(seq_i), len(seq_j))
                
                # Distance for aligned portion
                for k in range(min_len):
                    total += phoneme_distance(seq_i[k], seq_j[k])
                
                # Gap penalty for length difference
                total += (max_len - min_len) * DEFAULT_GAP_COST
        
        total_distances.append(total)
    
    return int(np.argmin(total_distances))


def star_align(
    sequences: list[list[str]],
    center_idx: int,
    gap_cost: float = DEFAULT_GAP_COST
) -> list[list[str]]:
    """
    Perform star (center-based) multiple sequence alignment.
    
    All sequences are aligned to the center sequence, then gaps are
    propagated to create a consistent alignment.
    
    Args:
        sequences: List of phoneme sequences
        center_idx: Index of the center sequence
        gap_cost: Cost of inserting a gap
        
    Returns:
        List of aligned sequences (same order as input)
    """
    if len(sequences) == 0:
        return []
    
    if len(sequences) == 1:
        return [list(sequences[0])]
    
    center = sequences[center_idx]
    n_seqs = len(sequences)
    
    # Align each sequence to center
    pairwise_alignments = []
    for i, seq in enumerate(sequences):
        if i == center_idx:
            pairwise_alignments.append((list(center), list(center)))
        else:
            aligned_center, aligned_seq = pairwise_align(center, seq, gap_cost)
            pairwise_alignments.append((aligned_center, aligned_seq))
    
    # Find all gap positions in center across all alignments
    # Build a "master" center with all gaps inserted
    master_center = []
    center_positions = []  # Maps master position to original center position (or -1 for gap)
    
    # Merge all aligned centers to find gap positions
    max_len = max(len(ac) for ac, _ in pairwise_alignments)
    
    # Use a position-tracking approach
    # For each alignment, track where gaps are inserted in the center
    gap_insertions = []  # List of (position_in_original, n_gaps_before) per alignment
    
    for aligned_center, _ in pairwise_alignments:
        insertions = {}
        orig_pos = 0
        for i, seg in enumerate(aligned_center):
            if seg == '':
                # Gap in center - this means insertion in the other sequence
                # Track how many gaps appear before each original position
                if orig_pos not in insertions:
                    insertions[orig_pos] = 0
                insertions[orig_pos] += 1
            else:
                orig_pos += 1
        gap_insertions.append(insertions)
    
    # Compute maximum gaps needed at each position
    max_gaps_at_pos = {}
    for insertions in gap_insertions:
        for pos, n_gaps in insertions.items():
            max_gaps_at_pos[pos] = max(max_gaps_at_pos.get(pos, 0), n_gaps)
    
    # Build master alignment length
    master_len = len(center) + sum(max_gaps_at_pos.values())
    
    # Now build aligned sequences
    aligned_sequences = []
    
    for seq_idx, (aligned_center, aligned_seq) in enumerate(pairwise_alignments):
        # Rebuild this sequence to match master alignment
        new_aligned = []
        orig_center_pos = 0
        align_pos = 0
        
        for master_pos in range(master_len):
            # Determine what should be at this master position
            # Calculate how many gaps should precede orig_center_pos in master
            gaps_before = sum(max_gaps_at_pos.get(p, 0) for p in range(orig_center_pos + 1) if p in max_gaps_at_pos and p <= orig_center_pos)
            expected_master_pos = orig_center_pos + sum(max_gaps_at_pos.get(p, 0) for p in range(orig_center_pos))
            
            # This is getting complex - let's use a simpler approach
            pass
        
        aligned_sequences.append(new_aligned)
    
    # Simpler approach: rebuild from scratch using gap position info
    return _star_align_simple(sequences, center_idx, gap_cost)


def _star_align_simple(
    sequences: list[list[str]],
    center_idx: int,
    gap_cost: float = DEFAULT_GAP_COST
) -> list[list[str]]:
    """
    Simpler star alignment implementation.
    
    1. Align each sequence to center
    2. Build master center with all gap positions
    3. Re-align each sequence to master center
    """
    if len(sequences) == 0:
        return []
    
    if len(sequences) == 1:
        return [list(sequences[0])]
    
    center = sequences[center_idx]
    
    # Step 1: Pairwise align all sequences to center
    alignments = []
    for i, seq in enumerate(sequences):
        if i == center_idx:
            alignments.append((list(center), list(center)))
        else:
            alignments.append(pairwise_align(center, seq, gap_cost))
    
    # Step 2: Build master center by merging all aligned centers
    # Track gap positions relative to original center
    # For each position in original center, track max gaps inserted BEFORE it
    gaps_before = [0] * (len(center) + 1)
    
    for aligned_center, _ in alignments:
        orig_pos = 0
        gap_count = 0
        for seg in aligned_center:
            if seg == '':
                gap_count += 1
            else:
                gaps_before[orig_pos] = max(gaps_before[orig_pos], gap_count)
                gap_count = 0
                orig_pos += 1
        # Gaps at the end
        gaps_before[orig_pos] = max(gaps_before[orig_pos], gap_count)
    
    # Build master center
    master_center = []
    for i, seg in enumerate(center):
        master_center.extend([''] * gaps_before[i])
        master_center.append(seg)
    master_center.extend([''] * gaps_before[len(center)])
    
    # Step 3: Map each aligned sequence to master center positions
    result = []
    for seq_idx, (aligned_center, aligned_seq) in enumerate(alignments):
        new_seq = []
        orig_pos = 0
        align_idx = 0
        
        for master_idx in range(len(master_center)):
            if master_center[master_idx] == '':
                # This is a gap position in master center
                # Check if this alignment has content here
                if align_idx < len(aligned_center) and aligned_center[align_idx] == '':
                    # This alignment also has a gap here - use the other sequence's content
                    new_seq.append(aligned_seq[align_idx])
                    align_idx += 1
                else:
                    # This alignment doesn't have a gap here - insert gap
                    new_seq.append('')
            else:
                # This is a real segment in master center
                # Find corresponding position in this alignment
                while align_idx < len(aligned_center) and aligned_center[align_idx] == '':
                    # Skip gaps until we find the matching segment
                    # But we need to handle these gaps properly
                    new_seq.append(aligned_seq[align_idx])
                    align_idx += 1
                
                if align_idx < len(aligned_seq):
                    new_seq.append(aligned_seq[align_idx])
                    align_idx += 1
                else:
                    new_seq.append('')
        
        result.append(new_seq)
    
    return result


def align_cognate_set(
    forms: list[tuple[str, str, int]],
    protoform: Optional[tuple[str, str]] = None,
    gap_cost: float = DEFAULT_GAP_COST
) -> list[dict[str, str]]:
    """
    Align a cognate set and return column-wise phoneme mappings.
    
    Args:
        forms: List of (language_name, form, morph_index) tuples for daughter languages
        protoform: Optional (language_name, form) tuple for the protoform.
                   If provided, used as center for alignment.
        gap_cost: Cost of inserting a gap
        
    Returns:
        List of dicts mapping language_name -> phoneme ('' for gaps)
    """
    if not forms and not protoform:
        return []
    
    # Prepare sequences
    lang_names = []
    sequences = []
    
    # Add protoform first if present
    if protoform:
        proto_lang, proto_form = protoform
        lang_names.append(proto_lang)
        sequences.append(segment_ipa(proto_form))
    
    # Add daughter forms (extract relevant morpheme)
    for lang_name, form, morph_index in forms:
        morpheme = extract_morpheme(form, morph_index)
        lang_names.append(lang_name)
        sequences.append(segment_ipa(morpheme))
    
    if len(sequences) == 0:
        return []
    
    if len(sequences) == 1:
        # Single sequence - no alignment needed
        return [{lang_names[0]: seg} for seg in sequences[0]]
    
    # Determine center
    if protoform:
        center_idx = 0  # Protoform is first
    else:
        center_idx = find_center_sequence(sequences)
    
    # Perform star alignment
    aligned = _star_align_simple(sequences, center_idx, gap_cost)
    
    # Convert to list of dicts
    if not aligned or not aligned[0]:
        return []
    
    alignment_length = len(aligned[0])
    result = []
    
    for pos in range(alignment_length):
        column = {}
        for i, lang_name in enumerate(lang_names):
            if i < len(aligned) and pos < len(aligned[i]):
                column[lang_name] = aligned[i][pos]
            else:
                column[lang_name] = ''
        result.append(column)
    
    return result


@dataclass
class CognateSetAlignment:
    """Result of aligning a cognate set."""
    prefid: Optional[int]
    proto_lang: Optional[str]
    proto_form: Optional[str]
    alignment: list[dict[str, str]]
    languages: list[str]
    
    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            'prefid': self.prefid,
            'proto_lang': self.proto_lang,
            'proto_form': self.proto_form,
            'alignment': self.alignment,
            'languages': self.languages
        }


class CognateAligner:
    """
    Aligner for cognate sets from the database.
    
    Handles fetching cognate set data and computing alignments.
    """
    
    def __init__(self, gap_cost: float = DEFAULT_GAP_COST):
        """
        Initialize the aligner.
        
        Args:
            gap_cost: Cost of inserting a gap in alignment
        """
        self.gap_cost = gap_cost
    
    def align_from_data(
        self,
        forms: list[tuple[str, str, int]],
        protoform: Optional[tuple[str, str]] = None,
        prefid: Optional[int] = None
    ) -> CognateSetAlignment:
        """
        Align a cognate set from provided data.
        
        Args:
            forms: List of (language_name, form, morph_index) tuples
            protoform: Optional (language_name, form) tuple
            prefid: Optional protoform ID for reference
            
        Returns:
            CognateSetAlignment with alignment results
        """
        alignment = align_cognate_set(forms, protoform, self.gap_cost)
        
        # Collect language names in order
        languages = []
        if protoform:
            languages.append(protoform[0])
        languages.extend(lang for lang, _, _ in forms)
        
        return CognateSetAlignment(
            prefid=prefid,
            proto_lang=protoform[0] if protoform else None,
            proto_form=protoform[1] if protoform else None,
            alignment=alignment,
            languages=languages
        )


# Convenience function for clearing the distance cache
def clear_distance_cache():
    """Clear the phoneme distance cache."""
    phoneme_distance.cache_clear()


def get_cache_info():
    """Get cache statistics."""
    return phoneme_distance.cache_info()
