"""
Minimal Generalization Detector for correspondence sets.

For each correspondence set reflecting a single proto phoneme, finds the minimal
generalization that distinguishes that set from the others based on preceding
and following context in the protoform.
"""

from dataclasses import dataclass
from typing import NamedTuple, Optional, Union

import panphon

from correspondence import CorrespondenceSet, CognateSetInfo


# Initialize panphon feature table
_ft = panphon.FeatureTable()

# Type for feature specifications: dict mapping feature name to value (+1/-1)
# Special key '#' with value True indicates word boundary
FeatureSpec = dict[str, int | bool]

# Sentinel for word boundary
BOUNDARY_SPEC: FeatureSpec = {'#': True}


class Context(NamedTuple):
    """
    Minimal generalization context for a correspondence set.
    
    Each field is a feature specification (dict) representing a natural class,
    or None if no distinguishing context was found for that position.
    
    Special case: {'#': True} represents word boundary.
    
    Examples:
        Context(left={'#': True}, right={'hi': 1})  
            # word-initially, before high vowels
        Context(left={'sg': 1}, right=None)  
            # after aspirated consonants, any following context
        Context(left=None, right={'long': 1})  
            # any preceding, before long vowels
    """
    left: Optional[FeatureSpec]   # Preceding context (natural class or boundary)
    right: Optional[FeatureSpec]  # Following context (natural class or boundary)
    
    def describe(self) -> str:
        """Return a human-readable description of the context."""
        parts = []
        
        if self.left is not None:
            if self.left.get('#'):
                parts.append("word-initially")
            else:
                feat_desc = _describe_features(self.left)
                parts.append(f"after [{feat_desc}]")
        
        if self.right is not None:
            if self.right.get('#'):
                parts.append("word-finally")
            else:
                feat_desc = _describe_features(self.right)
                parts.append(f"before [{feat_desc}]")
        
        if not parts:
            return "no distinguishing context"
        
        return " ".join(parts)


def _describe_features(features: FeatureSpec) -> str:
    """Convert feature dict to readable string like '+hi, -back'."""
    parts = []
    for feat, val in sorted(features.items()):
        if feat == '#':
            continue
        sign = '+' if val == 1 else '-'
        parts.append(f"{sign}{feat}")
    return ', '.join(parts)


def _get_segment_features(phoneme: str) -> Optional[dict[str, int]]:
    """Get panphon features for a phoneme, or None if not found."""
    if not phoneme:
        return None
    segs = _ft.word_fts(phoneme)
    if segs:
        return dict(segs[0].data)
    return None


def _segment_matches_spec(features: dict[str, int], spec: FeatureSpec) -> bool:
    """Check if a segment's features match a feature specification."""
    if spec.get('#'):
        return False  # Segments don't match boundary spec
    for feat, val in spec.items():
        if features.get(feat, 0) != val:
            return False
    return True


def _get_protoform_segments(alignment: list[dict[str, str]], 
                            proto_lang: str) -> list[str]:
    """Extract proto phonemes from alignment, ignoring gaps."""
    return [col.get(proto_lang, '') for col in alignment if col.get(proto_lang, '')]


def _extract_raw_context(cognate_info: CognateSetInfo, 
                         proto_lang: str) -> tuple[Optional[str], Optional[str]]:
    """
    Extract raw left/right context phonemes for a cognate.
    
    Returns:
        (left_phoneme, right_phoneme) where None means word boundary
    """
    alignment = cognate_info.alignment
    col_idx = cognate_info.column_index
    
    segments = _get_protoform_segments(alignment, proto_lang)
    
    # Find position in segment list
    segment_pos = sum(1 for i in range(col_idx) if alignment[i].get(proto_lang, ''))
    
    # Left context
    if segment_pos == 0:
        left = None  # Word boundary
    else:
        left = segments[segment_pos - 1]
    
    # Right context
    if segment_pos >= len(segments) - 1:
        right = None  # Word boundary
    else:
        right = segments[segment_pos + 1]
    
    return (left, right)


def _collect_contexts(corr_set: CorrespondenceSet, 
                      proto_lang: str) -> tuple[list[Optional[str]], list[Optional[str]]]:
    """
    Collect all raw context phonemes for a correspondence set.
    
    Returns:
        (left_phonemes, right_phonemes) where None entries are word boundaries
    """
    lefts = []
    rights = []
    
    for cognate_info in corr_set.cognate_sets:
        left, right = _extract_raw_context(cognate_info, proto_lang)
        lefts.append(left)
        rights.append(right)
    
    return (lefts, rights)


def _find_minimal_features(positive_phonemes: list[Optional[str]],
                           negative_phonemes: list[Optional[str]]) -> Optional[FeatureSpec]:
    """
    Find minimal feature specification that covers all positive but excludes all negative.
    
    Args:
        positive_phonemes: Phonemes to cover (None = word boundary)
        negative_phonemes: Phonemes to exclude (None = word boundary)
    
    Returns:
        Feature specification, or None if no distinguishing features found
    """
    # Check for word boundary distinction
    pos_has_boundary = None in positive_phonemes
    neg_has_boundary = None in negative_phonemes
    pos_segments = [p for p in positive_phonemes if p is not None]
    neg_segments = [p for p in negative_phonemes if p is not None]
    
    # Case 1: All positive are boundaries, no negative are boundaries
    if pos_has_boundary and not neg_has_boundary and not pos_segments:
        return BOUNDARY_SPEC
    
    # Case 2: Only positive has boundaries (mixed case) - boundary is distinguishing
    if pos_has_boundary and not neg_has_boundary:
        return BOUNDARY_SPEC
    
    # Case 3: Need to find features that distinguish segments
    if not pos_segments:
        return None
    
    # Get features for positive segments
    pos_features = []
    for p in pos_segments:
        fts = _get_segment_features(p)
        if fts:
            pos_features.append(fts)
    
    if not pos_features:
        return None
    
    # Get features for negative segments
    neg_features = []
    for p in neg_segments:
        fts = _get_segment_features(p)
        if fts:
            neg_features.append(fts)
    
    # Find features consistent across all positive segments
    all_feature_names = set()
    for fts in pos_features:
        all_feature_names.update(fts.keys())
    
    consistent = {}
    for feat in all_feature_names:
        values = [fts.get(feat, 0) for fts in pos_features]
        if len(set(values)) == 1 and values[0] != 0:
            consistent[feat] = values[0]
    
    if not consistent:
        return None
    
    # Find minimal subset that excludes all negative segments
    # Try single features first (most minimal)
    for feat in consistent:
        spec = {feat: consistent[feat]}
        if _spec_excludes_all(spec, neg_features):
            return spec
    
    # Try pairs
    feat_list = list(consistent.keys())
    for i, f1 in enumerate(feat_list):
        for f2 in feat_list[i+1:]:
            spec = {f1: consistent[f1], f2: consistent[f2]}
            if _spec_excludes_all(spec, neg_features):
                return spec
    
    # Try all consistent features
    if _spec_excludes_all(consistent, neg_features):
        return consistent
    
    return None


def _spec_excludes_all(spec: FeatureSpec, neg_features: list[dict[str, int]]) -> bool:
    """Check if spec excludes all negative segments."""
    for neg_fts in neg_features:
        if _segment_matches_spec(neg_fts, spec):
            return False
    return True


def find_minimal_generalization(set1: CorrespondenceSet,
                                 set2: CorrespondenceSet,
                                 proto_lang: str) -> Optional[Context]:
    """
    Find minimal context that distinguishes set1 from set2.
    
    Returns:
        Context with minimal feature specifications, or None if indistinguishable
    """
    lefts1, rights1 = _collect_contexts(set1, proto_lang)
    lefts2, rights2 = _collect_contexts(set2, proto_lang)
    
    # Find distinguishing features for left context
    left_spec = _find_minimal_features(lefts1, lefts2)
    
    # Find distinguishing features for right context
    right_spec = _find_minimal_features(rights1, rights2)
    
    if left_spec is None and right_spec is None:
        return None
    
    return Context(left=left_spec, right=right_spec)


def analyze_correspondence_sets(correspondence_sets: list[CorrespondenceSet],
                                 proto_lang: str,
                                 proto_phoneme: str) -> dict:
    """
    Analyze correspondence sets for a proto phoneme and find minimal generalizations.
    
    Args:
        correspondence_sets: List of correspondence sets
        proto_lang: Name of the proto language
        proto_phoneme: The proto phoneme to analyze
        
    Returns:
        Dict with analysis results including pairwise minimal generalizations
    """
    # Filter to sets with this proto phoneme
    relevant_sets = [cs for cs in correspondence_sets 
                     if cs.pattern.phonemes.get(proto_lang) == proto_phoneme]
    
    if len(relevant_sets) < 2:
        return {
            'proto_phoneme': proto_phoneme,
            'num_sets': len(relevant_sets),
            'message': 'Need at least 2 correspondence sets to find distinctions',
            'pairwise': []
        }
    
    # Find pairwise minimal generalizations
    pairwise_results = []
    for i in range(len(relevant_sets)):
        for j in range(i + 1, len(relevant_sets)):
            set1 = relevant_sets[i]
            set2 = relevant_sets[j]
            
            # Find generalization for set1 vs set2
            ctx_1_vs_2 = find_minimal_generalization(set1, set2, proto_lang)
            # And reverse
            ctx_2_vs_1 = find_minimal_generalization(set2, set1, proto_lang)
            
            result = {
                'set1_index': i,
                'set2_index': j,
                'set1_pattern': {k: v for k, v in set1.pattern.phonemes.items() if v},
                'set2_pattern': {k: v for k, v in set2.pattern.phonemes.items() if v},
                'set1_count': set1.count,
                'set2_count': set2.count,
            }
            
            if ctx_1_vs_2:
                result['context_1_vs_2'] = {
                    'left': ctx_1_vs_2.left,
                    'right': ctx_1_vs_2.right,
                    'description': ctx_1_vs_2.describe()
                }
            else:
                result['context_1_vs_2'] = None
                
            if ctx_2_vs_1:
                result['context_2_vs_1'] = {
                    'left': ctx_2_vs_1.left,
                    'right': ctx_2_vs_1.right,
                    'description': ctx_2_vs_1.describe()
                }
            else:
                result['context_2_vs_1'] = None
            
            pairwise_results.append(result)
    
    return {
        'proto_phoneme': proto_phoneme,
        'num_sets': len(relevant_sets),
        'pairwise': pairwise_results
    }


if __name__ == '__main__':
    import sqlite3
    from correspondence import extract_correspondence_sets_for_protolang
    
    conn = sqlite3.connect('db/borderlands.sqlite3')
    c = conn.cursor()
    
    result = extract_correspondence_sets_for_protolang(c, 17, 'Proto-Tangkhulic')
    correspondence_sets, languages = result
    
    analysis = analyze_correspondence_sets(
        correspondence_sets, 'Proto-Tangkhulic', 'ʃ'
    )
    
    print(f"Analysis of Proto-Tangkhulic *ʃ")
    print(f"Number of correspondence sets: {analysis['num_sets']}")
    print()
    
    for pair in analysis['pairwise'][:10]:
        ctx1 = pair.get('context_1_vs_2')
        ctx2 = pair.get('context_2_vs_1')
        if ctx1 or ctx2:
            print(f"Set {pair['set1_index']+1} (n={pair['set1_count']}) vs Set {pair['set2_index']+1} (n={pair['set2_count']})")
            if ctx1:
                print(f"  Set 1: Context(left={ctx1['left']}, right={ctx1['right']})")
                print(f"         → {ctx1['description']}")
            if ctx2:
                print(f"  Set 2: Context(left={ctx2['left']}, right={ctx2['right']})")
                print(f"         → {ctx2['description']}")
            print()
    
    conn.close()
