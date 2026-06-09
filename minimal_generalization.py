"""
Minimal Generalization Detector for correspondence sets.

For each correspondence set reflecting a single proto phoneme, finds the minimal
generalization that distinguishes that set from the others based on preceding
and following context in the protoform.
"""

from dataclasses import dataclass
from typing import NamedTuple, Optional, FrozenSet, Union

import panphon
from panphon.segment import Segment

from correspondence import CorrespondenceSet, CognateSetInfo


# Initialize panphon feature table
_ft = panphon.FeatureTable()


class HashableSegment:
    """A hashable wrapper around panphon Segment for use in sets."""
    
    def __init__(self, segment: Segment, phoneme: str = ''):
        self._segment = segment
        self._phoneme = phoneme  # Original IPA string
        self._hash = hash(tuple(sorted(segment.data.items())))
    
    @property
    def segment(self) -> Segment:
        return self._segment
    
    @property
    def phoneme(self) -> str:
        return self._phoneme
    
    def __hash__(self):
        return self._hash
    
    def __eq__(self, other):
        if not isinstance(other, HashableSegment):
            return False
        return self._segment.data == other._segment.data
    
    def __repr__(self):
        if self._phoneme:
            return f"Seg({self._phoneme})"
        return f"Seg({self._segment})"
    
    def get(self, feature: str, default=None):
        """Get a feature value from the underlying segment."""
        return self._segment.data.get(feature, default)
    
    def matches_features(self, features: dict[str, int]) -> bool:
        """Check if this segment matches all the given feature constraints."""
        for feat, val in features.items():
            if self._segment.data.get(feat, 0) != val:
                return False
        return True


class WordBoundary:
    """Represents a word boundary (#) in context."""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __hash__(self):
        return hash('#')
    
    def __eq__(self, other):
        return isinstance(other, WordBoundary)
    
    def __repr__(self):
        return "#"
    
    @property
    def phoneme(self) -> str:
        return '#'


WORD_BOUNDARY = WordBoundary()

# Type alias for context elements
ContextElement = Union[HashableSegment, WordBoundary]


class Context(NamedTuple):
    """
    Context of a correspondence set in protoforms.
    
    Each field is a frozenset of HashableSegment objects (or WordBoundary) 
    representing the disjunctive contexts that predict this correspondence set.
    
    For example, if left = {k, g} and right = {i, e}, the correspondence set
    occurs when preceded by /k/ OR /g/ AND followed by /i/ OR /e/.
    """
    left: FrozenSet[ContextElement]   # Preceding segments
    right: FrozenSet[ContextElement]  # Following segments


def phoneme_to_segment(phoneme: str) -> Optional[HashableSegment]:
    """Convert an IPA phoneme string to a HashableSegment."""
    if not phoneme:
        return None
    segs = _ft.word_fts(phoneme)
    if segs:
        return HashableSegment(segs[0], phoneme)
    return None


@dataclass 
class Generalization:
    """A generalization over contexts that distinguishes correspondence sets."""
    # Feature constraints on left (preceding) context (None = any)
    left_features: Optional[dict[str, int]] = None
    # Feature constraints on right (following) context (None = any)
    right_features: Optional[dict[str, int]] = None
    # Specific left phoneme string (if more specific than features)
    left_phoneme: Optional[str] = None
    # Specific right phoneme string (if more specific than features)
    right_phoneme: Optional[str] = None
    
    def describe(self) -> str:
        """Return a human-readable description of the generalization."""
        parts = []
        
        # Describe left (preceding) context
        if self.left_phoneme:
            if self.left_phoneme == '#':
                parts.append("word-initially")
            else:
                parts.append(f"after /{self.left_phoneme}/")
        elif self.left_features:
            feat_desc = self._describe_features(self.left_features)
            parts.append(f"after [{feat_desc}]")
        
        # Describe right (following) context
        if self.right_phoneme:
            if self.right_phoneme == '#':
                parts.append("word-finally")
            else:
                parts.append(f"before /{self.right_phoneme}/")
        elif self.right_features:
            feat_desc = self._describe_features(self.right_features)
            parts.append(f"before [{feat_desc}]")
        
        if not parts:
            return "no distinguishing context found"
        
        return " ".join(parts)
    
    def _describe_features(self, features: dict[str, int]) -> str:
        """Convert feature dict to readable string."""
        parts = []
        for feat, val in sorted(features.items()):
            sign = '+' if val == 1 else '-'
            parts.append(f"{sign}{feat}")
        return ', '.join(parts)


def get_protoform_segments(alignment: list[dict[str, str]], 
                           proto_lang: str) -> list[str]:
    """
    Extract the sequence of proto phonemes from an alignment, ignoring gaps.
    
    Args:
        alignment: List of alignment columns
        proto_lang: Name of the proto language
        
    Returns:
        List of proto phonemes (non-empty segments)
    """
    segments = []
    for column in alignment:
        phoneme = column.get(proto_lang, '')
        if phoneme:  # Skip gaps
            segments.append(phoneme)
    return segments


def extract_context_for_cognate(cognate_info: CognateSetInfo, 
                                 proto_lang: str) -> tuple[ContextElement, ContextElement]:
    """
    Extract the left and right context for a proto phoneme in a single cognate set.
    
    Args:
        cognate_info: Information about a cognate set
        proto_lang: Name of the proto language
        
    Returns:
        Tuple of (left_element, right_element) where each is HashableSegment or WordBoundary
    """
    alignment = cognate_info.alignment
    col_idx = cognate_info.column_index
    
    # Get all non-empty proto segments
    segments = get_protoform_segments(alignment, proto_lang)
    
    # Find position of our phoneme in the segment list
    # Count non-empty proto phonemes up to col_idx
    segment_pos = 0
    for i in range(col_idx):
        if alignment[i].get(proto_lang, ''):
            segment_pos += 1
    
    # Get left (preceding) context
    if segment_pos == 0:
        left = WORD_BOUNDARY
    else:
        left_phoneme = segments[segment_pos - 1]
        left = phoneme_to_segment(left_phoneme) or WORD_BOUNDARY
    
    # Get right (following) context
    if segment_pos >= len(segments) - 1:
        right = WORD_BOUNDARY
    else:
        right_phoneme = segments[segment_pos + 1]
        right = phoneme_to_segment(right_phoneme) or WORD_BOUNDARY
    
    return (left, right)


def build_context_for_correspondence_set(corr_set: CorrespondenceSet,
                                          proto_lang: str) -> Context:
    """
    Build a Context (with sets of segments) for a correspondence set.
    
    Aggregates all left and right contexts from all cognate sets in 
    the correspondence set into disjunctive sets.
    
    Args:
        corr_set: The correspondence set to analyze
        proto_lang: Name of the proto language
        
    Returns:
        Context with frozensets of left and right segments
    """
    left_set = set()
    right_set = set()
    
    for cognate_info in corr_set.cognate_sets:
        left, right = extract_context_for_cognate(cognate_info, proto_lang)
        left_set.add(left)
        right_set.add(right)
    
    return Context(left=frozenset(left_set), right=frozenset(right_set))


def find_distinguishing_features(positive_segs: FrozenSet[ContextElement],
                                  negative_segs: FrozenSet[ContextElement]) -> Optional[dict[str, int]]:
    """
    Find minimal feature set that matches all positive segments but no negative ones.
    
    Args:
        positive_segs: Segments that should match (from set we're characterizing)
        negative_segs: Segments that should NOT match (from other set)
        
    Returns:
        Dict of features, or None if no distinguishing features found
    """
    # Separate out word boundaries
    pos_segments = [s for s in positive_segs if isinstance(s, HashableSegment)]
    neg_segments = [s for s in negative_segs if isinstance(s, HashableSegment)]
    
    if not pos_segments:
        return None
    
    # Get features for all positive segments
    positive_features = [dict(s.segment.data) for s in pos_segments]
    
    if not positive_features:
        return None
    
    # Find features that are consistent across all positive segments
    consistent_features = {}
    all_feature_names = set()
    for fts in positive_features:
        all_feature_names.update(fts.keys())
    
    for feat in all_feature_names:
        values = [fts.get(feat, 0) for fts in positive_features]
        if len(set(values)) == 1 and values[0] != 0:
            consistent_features[feat] = values[0]
    
    if not consistent_features:
        return None
    
    # Get features for negative segments
    negative_features = [dict(s.segment.data) for s in neg_segments]
    
    # Find minimal subset that excludes all negative segments
    feature_names = list(consistent_features.keys())
    
    # Try single features first
    for feat in feature_names:
        constraint = {feat: consistent_features[feat]}
        excludes_all = True
        for neg_fts in negative_features:
            if neg_fts.get(feat, 0) == consistent_features[feat]:
                excludes_all = False
                break
        if excludes_all:
            return constraint
    
    # Try pairs of features
    for i, feat1 in enumerate(feature_names):
        for feat2 in feature_names[i+1:]:
            constraint = {
                feat1: consistent_features[feat1],
                feat2: consistent_features[feat2]
            }
            excludes_all = True
            for neg_fts in negative_features:
                matches = (neg_fts.get(feat1, 0) == consistent_features[feat1] and
                          neg_fts.get(feat2, 0) == consistent_features[feat2])
                if matches:
                    excludes_all = False
                    break
            if excludes_all:
                return constraint
    
    # Try all consistent features
    if negative_features:
        excludes_all = True
        for neg_fts in negative_features:
            matches_all = True
            for feat, val in consistent_features.items():
                if neg_fts.get(feat, 0) != val:
                    matches_all = False
                    break
            if matches_all:
                excludes_all = False
                break
        if excludes_all:
            return consistent_features
    
    return None


def find_probabilistic_features(positive_segs: FrozenSet[ContextElement], 
                                 negative_segs: FrozenSet[ContextElement],
                                 threshold: float = 0.7) -> Optional[dict[str, int]]:
    """
    Find features that characterize most (>threshold) of positive but few of negative.
    """
    pos_segments = [s for s in positive_segs if isinstance(s, HashableSegment)]
    neg_segments = [s for s in negative_segs if isinstance(s, HashableSegment)]
    
    if not pos_segments:
        return None
    
    pos_features = [dict(s.segment.data) for s in pos_segments]
    neg_features = [dict(s.segment.data) for s in neg_segments]
    
    if not pos_features:
        return None
    
    all_feature_names = set()
    for fts in pos_features:
        all_feature_names.update(fts.keys())
    
    best_feature = None
    best_score = 0
    
    for feat in all_feature_names:
        for target_val in [1, -1]:
            pos_count = sum(1 for fts in pos_features if fts.get(feat, 0) == target_val)
            pos_ratio = pos_count / len(pos_features)
            
            if neg_features:
                neg_count = sum(1 for fts in neg_features if fts.get(feat, 0) == target_val)
                neg_ratio = neg_count / len(neg_features)
            else:
                neg_ratio = 0
            
            if pos_ratio >= threshold and neg_ratio <= (1 - threshold):
                score = pos_ratio - neg_ratio
                if score > best_score:
                    best_score = score
                    best_feature = {feat: target_val}
    
    return best_feature


def find_minimal_generalization(ctx1: Context, ctx2: Context) -> Optional[Generalization]:
    """
    Find the minimal generalization that distinguishes context 1 from context 2.
    
    Args:
        ctx1: Context from correspondence set 1 (to characterize)
        ctx2: Context from correspondence set 2 (to exclude)
        
    Returns:
        Generalization that matches ctx1 but not ctx2, or None if not found
    """
    gen = Generalization()
    found_distinction = False
    
    # Strategy 1: Check if left contexts are disjoint
    if ctx1.left and not ctx1.left.intersection(ctx2.left):
        if len(ctx1.left) == 1:
            elem = next(iter(ctx1.left))
            gen.left_phoneme = elem.phoneme
            found_distinction = True
        else:
            feat = find_distinguishing_features(ctx1.left, ctx2.left)
            if feat:
                gen.left_features = feat
                found_distinction = True
    
    # Strategy 2: Check if right contexts are disjoint
    if not found_distinction and ctx1.right and not ctx1.right.intersection(ctx2.right):
        if len(ctx1.right) == 1:
            elem = next(iter(ctx1.right))
            gen.right_phoneme = elem.phoneme
            found_distinction = True
        else:
            feat = find_distinguishing_features(ctx1.right, ctx2.right)
            if feat:
                gen.right_features = feat
                found_distinction = True
    
    # Strategy 3: Find unique elements in ctx1's left
    if not found_distinction:
        unique_left = ctx1.left - ctx2.left
        if unique_left:
            if len(unique_left) == 1:
                elem = next(iter(unique_left))
                gen.left_phoneme = elem.phoneme
                found_distinction = True
            else:
                feat = find_distinguishing_features(unique_left, ctx2.left)
                if feat:
                    gen.left_features = feat
                    found_distinction = True
    
    # Strategy 4: Find unique elements in ctx1's right
    if not found_distinction:
        unique_right = ctx1.right - ctx2.right
        if unique_right:
            if len(unique_right) == 1:
                elem = next(iter(unique_right))
                gen.right_phoneme = elem.phoneme
                found_distinction = True
            else:
                feat = find_distinguishing_features(unique_right, ctx2.right)
                if feat:
                    gen.right_features = feat
                    found_distinction = True
    
    # Strategy 5: Probabilistic features for right context
    if not found_distinction:
        feat = find_probabilistic_features(ctx1.right, ctx2.right)
        if feat:
            gen.right_features = feat
            found_distinction = True
    
    # Strategy 6: Probabilistic features for left context
    if not found_distinction:
        feat = find_probabilistic_features(ctx1.left, ctx2.left)
        if feat:
            gen.left_features = feat
            found_distinction = True
    
    if found_distinction:
        return gen
    return None


def analyze_correspondence_sets(correspondence_sets: list[CorrespondenceSet],
                                 proto_lang: str,
                                 proto_phoneme: str) -> dict:
    """
    Analyze correspondence sets for a proto phoneme and find distinguishing contexts.
    
    Args:
        correspondence_sets: List of correspondence sets to analyze
        proto_lang: Name of the proto language
        proto_phoneme: The proto phoneme to analyze
        
    Returns:
        Dict with analysis results including pairwise generalizations
    """
    # Filter to sets with this proto phoneme
    relevant_sets = []
    for cs in correspondence_sets:
        pattern_phoneme = cs.pattern.phonemes.get(proto_lang, '')
        if pattern_phoneme == proto_phoneme:
            relevant_sets.append(cs)
    
    if len(relevant_sets) < 2:
        return {
            'proto_phoneme': proto_phoneme,
            'num_sets': len(relevant_sets),
            'message': 'Need at least 2 correspondence sets to find distinctions',
            'pairwise': []
        }
    
    # Build Context for each set
    set_contexts = []
    for cs in relevant_sets:
        ctx = build_context_for_correspondence_set(cs, proto_lang)
        set_contexts.append({
            'set': cs,
            'context': ctx,
            'pattern': {k: v for k, v in cs.pattern.phonemes.items() if v}
        })
    
    # Find pairwise generalizations
    pairwise_results = []
    for i in range(len(set_contexts)):
        for j in range(i + 1, len(set_contexts)):
            set1 = set_contexts[i]
            set2 = set_contexts[j]
            
            ctx1 = set1['context']
            ctx2 = set2['context']
            
            # Try to find generalization for set1 vs set2
            gen_1_vs_2 = find_minimal_generalization(ctx1, ctx2)
            # Also try the reverse
            gen_2_vs_1 = find_minimal_generalization(ctx2, ctx1)
            
            # Format contexts for output
            def format_context(ctx: Context) -> dict:
                return {
                    'left': [elem.phoneme for elem in ctx.left],
                    'right': [elem.phoneme for elem in ctx.right]
                }
            
            result = {
                'set1_index': i,
                'set2_index': j,
                'set1_pattern': set1['pattern'],
                'set2_pattern': set2['pattern'],
                'set1_count': set1['set'].count,
                'set2_count': set2['set'].count,
                'set1_context': format_context(ctx1),
                'set2_context': format_context(ctx2),
            }
            
            if gen_1_vs_2:
                result['generalization_1_vs_2'] = gen_1_vs_2.describe()
            else:
                result['generalization_1_vs_2'] = None
                
            if gen_2_vs_1:
                result['generalization_2_vs_1'] = gen_2_vs_1.describe()
            else:
                result['generalization_2_vs_1'] = None
            
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
    
    # Get correspondence sets for Proto-Tangkhulic
    result = extract_correspondence_sets_for_protolang(c, 17, 'Proto-Tangkhulic')
    correspondence_sets, languages = result
    
    # Analyze 'ʃ' correspondence sets (has 9 sets with clear distinctions)
    analysis = analyze_correspondence_sets(
        correspondence_sets, 'Proto-Tangkhulic', 'ʃ'
    )
    
    print(f"Analysis of Proto-Tangkhulic *ʃ")
    print(f"Number of correspondence sets: {analysis['num_sets']}")
    print()
    
    # Show pairs where distinctions were found
    found_distinctions = 0
    for pair in analysis['pairwise']:
        gen1 = pair['generalization_1_vs_2']
        gen2 = pair['generalization_2_vs_1']
        if gen1 or gen2:
            found_distinctions += 1
            print(f"Set {pair['set1_index']+1} (n={pair['set1_count']}) vs Set {pair['set2_index']+1} (n={pair['set2_count']})")
            print(f"  Set 1 pattern: {pair['set1_pattern']}")
            print(f"  Set 2 pattern: {pair['set2_pattern']}")
            print(f"  Set 1 context: left={pair['set1_context']['left']}, right={pair['set1_context']['right']}")
            print(f"  Set 2 context: left={pair['set2_context']['left']}, right={pair['set2_context']['right']}")
            if gen1:
                print(f"  Set 1 distinguished: {gen1}")
            if gen2:
                print(f"  Set 2 distinguished: {gen2}")
            print()
    
    print(f"Found distinctions for {found_distinctions} of {len(analysis['pairwise'])} pairs")
    
    conn.close()
