"""
Minimal Generalization Detector for correspondence sets.

For each correspondence set reflecting a single proto phoneme, finds the minimal
generalization that distinguishes that set from the others based on preceding
and following context in the protoform.
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

import panphon

from correspondence import CorrespondenceSet, CognateSetInfo


# Word boundary marker
WORD_BOUNDARY = '#'

# Initialize panphon feature table
_ft = panphon.FeatureTable()


@dataclass
class Context:
    """Context of a proto phoneme in a protoform."""
    preceding: str  # Preceding phoneme or '#' for word boundary
    following: str  # Following phoneme or '#' for word boundary
    
    def __hash__(self):
        return hash((self.preceding, self.following))
    
    def __eq__(self, other):
        if not isinstance(other, Context):
            return False
        return self.preceding == other.preceding and self.following == other.following


@dataclass 
class Generalization:
    """A generalization over contexts that distinguishes correspondence sets."""
    # Feature constraints on preceding context (None = any)
    preceding_features: Optional[dict[str, int]] = None
    # Feature constraints on following context (None = any)
    following_features: Optional[dict[str, int]] = None
    # Specific preceding phoneme (if more specific than features)
    preceding_phoneme: Optional[str] = None
    # Specific following phoneme (if more specific than features)
    following_phoneme: Optional[str] = None
    
    def describe(self) -> str:
        """Return a human-readable description of the generalization."""
        parts = []
        
        # Describe preceding context
        if self.preceding_phoneme:
            if self.preceding_phoneme == WORD_BOUNDARY:
                parts.append("word-initially")
            else:
                parts.append(f"after /{self.preceding_phoneme}/")
        elif self.preceding_features:
            feat_desc = self._describe_features(self.preceding_features)
            parts.append(f"after [{feat_desc}]")
        
        # Describe following context
        if self.following_phoneme:
            if self.following_phoneme == WORD_BOUNDARY:
                parts.append("word-finally")
            else:
                parts.append(f"before /{self.following_phoneme}/")
        elif self.following_features:
            feat_desc = self._describe_features(self.following_features)
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


def get_protoform_segments(protoform: str, alignment: list[dict[str, str]], 
                           proto_lang: str) -> list[str]:
    """
    Extract the sequence of proto phonemes from an alignment, ignoring gaps.
    
    Args:
        protoform: The protoform string (for reference)
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


def extract_context(cognate_info: CognateSetInfo, proto_lang: str) -> Context:
    """
    Extract the preceding and following context for a proto phoneme.
    
    Args:
        cognate_info: Information about a cognate set
        proto_lang: Name of the proto language
        
    Returns:
        Context with preceding and following phonemes
    """
    alignment = cognate_info.alignment
    col_idx = cognate_info.column_index
    
    # Get all non-empty proto segments
    segments = get_protoform_segments(
        cognate_info.proto_form, alignment, proto_lang
    )
    
    # Find position of our phoneme in the segment list
    # Count non-empty proto phonemes up to col_idx
    segment_pos = 0
    for i in range(col_idx):
        if alignment[i].get(proto_lang, ''):
            segment_pos += 1
    
    # Get preceding (or word boundary)
    if segment_pos == 0:
        preceding = WORD_BOUNDARY
    else:
        preceding = segments[segment_pos - 1]
    
    # Get following (or word boundary)
    if segment_pos >= len(segments) - 1:
        following = WORD_BOUNDARY
    else:
        following = segments[segment_pos + 1]
    
    return Context(preceding=preceding, following=following)


def get_phoneme_features(phoneme: str) -> Optional[dict[str, int]]:
    """
    Get panphon features for a phoneme.
    
    Args:
        phoneme: IPA phoneme
        
    Returns:
        Dict of feature name -> value (1/-1/0), or None if not found
    """
    if phoneme == WORD_BOUNDARY:
        return None
    
    fts = _ft.word_fts(phoneme)
    if not fts:
        return None
    
    # Return the features of the first segment
    return dict(fts[0])


def features_match(phoneme: str, feature_constraints: dict[str, int]) -> bool:
    """
    Check if a phoneme matches the given feature constraints.
    
    Args:
        phoneme: IPA phoneme
        feature_constraints: Dict of feature name -> required value
        
    Returns:
        True if phoneme has all the specified feature values
    """
    if phoneme == WORD_BOUNDARY:
        return False
    
    fts = get_phoneme_features(phoneme)
    if fts is None:
        return False
    
    for feat, val in feature_constraints.items():
        if fts.get(feat, 0) != val:
            return False
    return True


def find_distinguishing_features(positive_phonemes: set[str], 
                                  negative_phonemes: set[str]) -> Optional[dict[str, int]]:
    """
    Find minimal feature set that matches all positive phonemes but no negative ones.
    
    Args:
        positive_phonemes: Phonemes that should match
        negative_phonemes: Phonemes that should not match
        
    Returns:
        Dict of features, or None if no distinguishing features found
    """
    if not positive_phonemes:
        return None
    
    # Handle word boundary specially
    if positive_phonemes == {WORD_BOUNDARY}:
        if WORD_BOUNDARY not in negative_phonemes:
            return None  # Will use phoneme-level distinction
        return None
    
    # Remove word boundary from consideration for features
    positive_phonemes = positive_phonemes - {WORD_BOUNDARY}
    negative_phonemes = negative_phonemes - {WORD_BOUNDARY}
    
    if not positive_phonemes:
        return None
    
    # Get features for all positive phonemes
    positive_features = []
    for p in positive_phonemes:
        fts = get_phoneme_features(p)
        if fts:
            positive_features.append(fts)
    
    if not positive_features:
        return None
    
    # Find features that are consistent across all positive phonemes
    # (same value for all)
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
    
    # Get features for negative phonemes
    negative_features = []
    for p in negative_phonemes:
        fts = get_phoneme_features(p)
        if fts:
            negative_features.append(fts)
    
    # Find minimal subset that excludes all negative phonemes
    # Start with single features, then pairs, etc.
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


def find_minimal_generalization(set1_contexts: list[Context],
                                 set2_contexts: list[Context]) -> Optional[Generalization]:
    """
    Find the minimal generalization that distinguishes two sets of contexts.
    
    Args:
        set1_contexts: Contexts from correspondence set 1
        set2_contexts: Contexts from correspondence set 2
        
    Returns:
        Generalization that matches set1 but not set2, or None if not found
    """
    # Collect all preceding and following phonemes for each set
    set1_preceding = {c.preceding for c in set1_contexts}
    set1_following = {c.following for c in set1_contexts}
    set2_preceding = {c.preceding for c in set2_contexts}
    set2_following = {c.following for c in set2_contexts}
    
    gen = Generalization()
    found_distinction = False
    
    # Strategy 1: Try to distinguish by preceding context (no overlap)
    if set1_preceding and not set1_preceding.intersection(set2_preceding):
        if len(set1_preceding) == 1:
            gen.preceding_phoneme = list(set1_preceding)[0]
            found_distinction = True
        else:
            feat = find_distinguishing_features(set1_preceding, set2_preceding)
            if feat:
                gen.preceding_features = feat
                found_distinction = True
    
    # Strategy 2: Try to distinguish by following context (no overlap)
    if not found_distinction and set1_following and not set1_following.intersection(set2_following):
        if len(set1_following) == 1:
            gen.following_phoneme = list(set1_following)[0]
            found_distinction = True
        else:
            feat = find_distinguishing_features(set1_following, set2_following)
            if feat:
                gen.following_features = feat
                found_distinction = True
    
    # Strategy 3: Try features that distinguish the TYPICAL case even with overlap
    # Find phonemes that appear only in set1 and not in set2
    if not found_distinction:
        unique_preceding = set1_preceding - set2_preceding
        if unique_preceding:
            if len(unique_preceding) == 1:
                gen.preceding_phoneme = list(unique_preceding)[0]
                found_distinction = True
            else:
                feat = find_distinguishing_features(unique_preceding, set2_preceding)
                if feat:
                    gen.preceding_features = feat
                    found_distinction = True
    
    if not found_distinction:
        unique_following = set1_following - set2_following
        if unique_following:
            if len(unique_following) == 1:
                gen.following_phoneme = list(unique_following)[0]
                found_distinction = True
            else:
                feat = find_distinguishing_features(unique_following, set2_following)
                if feat:
                    gen.following_features = feat
                    found_distinction = True
    
    # Strategy 4: Try to find features that characterize most of set1 vs set2
    # even if there's overlap in specific phonemes
    if not found_distinction:
        # Try to find a feature that is TRUE for most of set1_following 
        # but FALSE for most of set2_following
        feat = find_probabilistic_features(set1_following, set2_following)
        if feat:
            gen.following_features = feat
            found_distinction = True
    
    if not found_distinction:
        feat = find_probabilistic_features(set1_preceding, set2_preceding)
        if feat:
            gen.preceding_features = feat
            found_distinction = True
    
    if found_distinction:
        return gen
    return None


def find_probabilistic_features(positive_phonemes: set[str], 
                                 negative_phonemes: set[str],
                                 threshold: float = 0.7) -> Optional[dict[str, int]]:
    """
    Find features that characterize most (>threshold) of positive but few of negative.
    
    This is useful when there's overlap between the sets.
    """
    # Remove word boundaries
    pos_phones = positive_phonemes - {WORD_BOUNDARY}
    neg_phones = negative_phonemes - {WORD_BOUNDARY}
    
    if not pos_phones:
        return None
    
    # Get features for all phonemes
    pos_features = []
    for p in pos_phones:
        fts = get_phoneme_features(p)
        if fts:
            pos_features.append(fts)
    
    neg_features = []
    for p in neg_phones:
        fts = get_phoneme_features(p)
        if fts:
            neg_features.append(fts)
    
    if not pos_features:
        return None
    
    # Find features where value is consistent in positive set
    all_feature_names = set()
    for fts in pos_features:
        all_feature_names.update(fts.keys())
    
    best_feature = None
    best_score = 0
    
    for feat in all_feature_names:
        for target_val in [1, -1]:
            # Count how many positive phonemes have this value
            pos_count = sum(1 for fts in pos_features if fts.get(feat, 0) == target_val)
            pos_ratio = pos_count / len(pos_features)
            
            # Count how many negative phonemes have this value
            if neg_features:
                neg_count = sum(1 for fts in neg_features if fts.get(feat, 0) == target_val)
                neg_ratio = neg_count / len(neg_features)
            else:
                neg_ratio = 0
            
            # Score: high positive ratio, low negative ratio
            if pos_ratio >= threshold and neg_ratio <= (1 - threshold):
                score = pos_ratio - neg_ratio
                if score > best_score:
                    best_score = score
                    best_feature = {feat: target_val}
    
    return best_feature


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
    
    # Extract contexts for each set
    set_contexts = []
    for cs in relevant_sets:
        contexts = []
        for cog in cs.cognate_sets:
            ctx = extract_context(cog, proto_lang)
            contexts.append(ctx)
        set_contexts.append({
            'set': cs,
            'contexts': contexts,
            'pattern': {k: v for k, v in cs.pattern.phonemes.items() if v}
        })
    
    # Find pairwise generalizations
    pairwise_results = []
    for i in range(len(set_contexts)):
        for j in range(i + 1, len(set_contexts)):
            set1 = set_contexts[i]
            set2 = set_contexts[j]
            
            # Try to find generalization for set1 vs set2
            gen_1_vs_2 = find_minimal_generalization(
                set1['contexts'], set2['contexts']
            )
            # Also try the reverse
            gen_2_vs_1 = find_minimal_generalization(
                set2['contexts'], set1['contexts']
            )
            
            result = {
                'set1_index': i,
                'set2_index': j,
                'set1_pattern': set1['pattern'],
                'set2_pattern': set2['pattern'],
                'set1_count': set1['set'].count,
                'set2_count': set2['set'].count,
                'set1_contexts': [(c.preceding, c.following) for c in set1['contexts']],
                'set2_contexts': [(c.preceding, c.following) for c in set2['contexts']],
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
            if gen1:
                print(f"  Set 1 distinguished: {gen1}")
            if gen2:
                print(f"  Set 2 distinguished: {gen2}")
            print()
    
    print(f"Found distinctions for {found_distinctions} of {len(analysis['pairwise'])} pairs")
    
    conn.close()
