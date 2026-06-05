"""
Correspondence set extraction and management.

Extracts correspondence patterns from aligned cognate sets and groups them
into hierarchical correspondence sets. A partial correspondence (with gaps)
is considered an instance of any total correspondence it doesn't contradict.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from alignment import CognateAligner, align_cognate_set


@dataclass
class CorrespondencePattern:
    """A single correspondence pattern (one column from an alignment)."""
    # Maps language name -> phoneme ('' for gaps)
    phonemes: dict[str, str]
    
    def to_tuple(self, languages: list[str]) -> tuple:
        """Convert to ordered tuple for hashing/comparison."""
        return tuple(self.phonemes.get(lang, '') for lang in languages)
    
    def is_instance_of(self, other: 'CorrespondencePattern', languages: list[str]) -> bool:
        """
        Check if this pattern is an instance of another pattern.
        
        A is an instance of B if:
        1. There are no conflicting (lang, phoneme) pairs between A and B
        2. There are at least 2 matching non-empty positions
        """
        matching_positions = 0
        
        for lang in languages:
            my_phoneme = self.phonemes.get(lang, '')
            other_phoneme = other.phonemes.get(lang, '')
            
            # Skip if either has a gap (empty)
            if my_phoneme == '' or other_phoneme == '':
                continue
            
            # Check for conflict
            if my_phoneme != other_phoneme:
                return False
            
            # Count matching positions
            matching_positions += 1
        
        # Require at least 2 matching positions
        return matching_positions >= 2


@dataclass
class ReflexInfo:
    """Information about a reflex in a cognate set."""
    refid: int
    lang_name: str
    form: str
    ipaform: str
    gloss: str
    
    def to_dict(self) -> dict:
        return {
            'refid': self.refid,
            'lang_name': self.lang_name,
            'form': self.form,
            'ipaform': self.ipaform,
            'gloss': self.gloss
        }


@dataclass
class CognateSetInfo:
    """Information about a cognate set for display."""
    prefid: int
    proto_form: str
    proto_gloss: str
    alignment: list[dict[str, str]]
    languages: list[str]
    column_index: int  # Which alignment column contains this correspondence
    reflexes: list[ReflexInfo] = None  # List of reflexes in this cognate set
    
    def to_dict(self) -> dict:
        result = {
            'prefid': self.prefid,
            'proto_form': self.proto_form,
            'proto_gloss': self.proto_gloss,
            'alignment': self.alignment,
            'languages': self.languages,
            'column_index': self.column_index
        }
        if self.reflexes:
            result['reflexes'] = [r.to_dict() for r in self.reflexes]
        return result


@dataclass
class CorrespondenceSet:
    """
    A correspondence set: a canonical pattern with associated cognate sets.
    """
    # The canonical (total) pattern for this set
    pattern: CorrespondencePattern
    # Cognate sets that exhibit this correspondence
    cognate_sets: list[CognateSetInfo] = field(default_factory=list)
    # Number of cognate sets (for sorting)
    count: int = 0
    
    def pattern_tuple(self, languages: list[str]) -> tuple:
        """Get pattern as ordered tuple."""
        return self.pattern.to_tuple(languages)
    
    def pattern_display(self, languages: list[str]) -> dict[str, str]:
        """Get pattern as dict for display."""
        return {lang: self.pattern.phonemes.get(lang, '-') for lang in languages}
    
    def to_dict(self, languages: list[str]) -> dict:
        return {
            'pattern': self.pattern_display(languages),
            'count': self.count,
            'cognate_sets': [cs.to_dict() for cs in self.cognate_sets]
        }


class CorrespondenceExtractor:
    """
    Extracts and manages correspondence sets from cognate data.
    """
    
    def __init__(self, aligner: Optional[CognateAligner] = None):
        self.aligner = aligner or CognateAligner()
        
    def extract_from_cognate_set(
        self,
        prefid: int,
        proto_form: str,
        proto_gloss: str,
        proto_lang: str,
        daughter_forms: list[tuple[str, str, int]],
        languages: list[str],
        reflexes: list[ReflexInfo] = None
    ) -> list[tuple[CorrespondencePattern, CognateSetInfo]]:
        """
        Extract correspondence patterns from a single cognate set.
        
        Args:
            prefid: Protoform ID
            proto_form: Reconstructed form
            proto_gloss: Gloss/meaning
            proto_lang: Proto-language name
            daughter_forms: List of (language_name, form, morph_index) tuples
            languages: Ordered list of all languages to consider
            reflexes: Optional list of ReflexInfo for the daughter forms
            
        Returns:
            List of (pattern, cognate_info) tuples, one per alignment column
        """
        # Compute alignment
        protoform_tuple = (proto_lang, proto_form)
        alignment = align_cognate_set(daughter_forms, protoform_tuple)
        
        if not alignment:
            return []
        
        # Build language list for this cognate set
        cognate_languages = [proto_lang] + [lang for lang, _, _ in daughter_forms]
        
        results = []
        for col_idx, column in enumerate(alignment):
            # Build pattern
            pattern_phonemes = {}
            for lang in cognate_languages:
                phoneme = column.get(lang, '')
                pattern_phonemes[lang] = phoneme
            
            pattern = CorrespondencePattern(phonemes=pattern_phonemes)
            cognate_info = CognateSetInfo(
                prefid=prefid,
                proto_form=proto_form,
                proto_gloss=proto_gloss,
                alignment=alignment,
                languages=cognate_languages,
                column_index=col_idx,
                reflexes=reflexes
            )
            results.append((pattern, cognate_info))
        
        return results
    
    def build_correspondence_sets(
        self,
        patterns_with_cognates: list[tuple[CorrespondencePattern, CognateSetInfo]],
        languages: list[str]
    ) -> list[CorrespondenceSet]:
        """
        Group patterns into correspondence sets.
        
        Partial patterns (with gaps) are matched to all compatible total patterns.
        Total patterns become canonical correspondence sets.
        
        Args:
            patterns_with_cognates: List of (pattern, cognate_info) tuples
            languages: Ordered list of languages for consistent ordering
            
        Returns:
            List of CorrespondenceSet objects, sorted by count (descending)
        """
        # Separate total patterns (no gaps) from partial patterns
        total_patterns: dict[tuple, list[tuple[CorrespondencePattern, CognateSetInfo]]] = defaultdict(list)
        partial_patterns: list[tuple[CorrespondencePattern, CognateSetInfo]] = []
        
        for pattern, cognate_info in patterns_with_cognates:
            pattern_tuple = pattern.to_tuple(languages)
            has_gap = '' in pattern_tuple
            
            if has_gap:
                partial_patterns.append((pattern, cognate_info))
            else:
                total_patterns[pattern_tuple].append((pattern, cognate_info))
        
        # Build correspondence sets from total patterns
        correspondence_sets: dict[tuple, CorrespondenceSet] = {}
        for pattern_tuple, items in total_patterns.items():
            # Use first pattern as canonical
            canonical_pattern = items[0][0]
            corr_set = CorrespondenceSet(pattern=canonical_pattern)
            
            # Add all cognate sets
            for _, cognate_info in items:
                corr_set.cognate_sets.append(cognate_info)
            
            corr_set.count = len(corr_set.cognate_sets)
            correspondence_sets[pattern_tuple] = corr_set
        
        # Match partial patterns to compatible total patterns
        for pattern, cognate_info in partial_patterns:
            matched = False
            for pattern_tuple, corr_set in correspondence_sets.items():
                if pattern.is_instance_of(corr_set.pattern, languages):
                    corr_set.cognate_sets.append(cognate_info)
                    corr_set.count = len(corr_set.cognate_sets)
                    matched = True
                    # Note: a partial can match multiple total patterns
            
            # If no match, create a new set from this partial pattern
            if not matched:
                pattern_tuple = pattern.to_tuple(languages)
                if pattern_tuple not in correspondence_sets:
                    corr_set = CorrespondenceSet(pattern=pattern)
                    corr_set.cognate_sets.append(cognate_info)
                    corr_set.count = 1
                    correspondence_sets[pattern_tuple] = corr_set
                else:
                    correspondence_sets[pattern_tuple].cognate_sets.append(cognate_info)
                    correspondence_sets[pattern_tuple].count += 1
        
        # Sort cognate sets within each correspondence set by gloss
        for corr_set in correspondence_sets.values():
            corr_set.cognate_sets.sort(key=lambda cs: cs.proto_gloss.lower())
        
        # Filter out sets with fewer than 2 non-empty positions
        def count_non_empty(corr_set: CorrespondenceSet) -> int:
            return sum(1 for lang in languages 
                      if corr_set.pattern.phonemes.get(lang, '') not in ('', '-'))
        
        filtered_sets = [cs for cs in correspondence_sets.values() if count_non_empty(cs) >= 2]
        
        # Sort correspondence sets by count (descending), then by pattern
        result = sorted(
            filtered_sets,
            key=lambda cs: (-cs.count, cs.pattern_tuple(languages))
        )
        
        return result


def extract_correspondence_sets_for_protolang(
    db_cursor,
    plangid: int,
    proto_lang_name: str
) -> tuple[list[CorrespondenceSet], list[str]]:
    """
    Extract all correspondence sets for a given proto-language.
    
    Args:
        db_cursor: Database cursor
        plangid: Proto-language ID
        proto_lang_name: Proto-language name
        
    Returns:
        Tuple of (list of CorrespondenceSet, ordered list of languages)
    """
    extractor = CorrespondenceExtractor()
    
    # Get all protoforms for this proto-language
    db_cursor.execute(
        """SELECT reflexes.refid, reflexes.ipaform, reflexes.gloss
           FROM reflexes
           WHERE reflexes.langid = ?""",
        (plangid,)
    )
    protoforms = db_cursor.fetchall()
    
    # Get all daughter languages for this proto-language
    db_cursor.execute(
        """SELECT DISTINCT langnames.name
           FROM descendant_of
           JOIN langnames ON langnames.langid = descendant_of.langid
           WHERE descendant_of.plangid = ?
           ORDER BY langnames.name""",
        (plangid,)
    )
    daughter_languages = [row[0] for row in db_cursor.fetchall()]
    
    # Full language list: proto-language first, then daughters
    languages = [proto_lang_name] + daughter_languages
    
    # Collect all patterns
    all_patterns: list[tuple[CorrespondencePattern, CognateSetInfo]] = []
    
    for prefid, proto_form, proto_gloss in protoforms:
        # Get daughter forms for this cognate set (with refid for removal)
        # Use ipaform for alignment, form for display
        db_cursor.execute(
            """SELECT reflexes.refid, langnames.name, reflexes.form, reflexes.ipaform, reflexes.gloss, reflex_of.morph_index
               FROM reflex_of
               JOIN reflexes ON reflexes.refid = reflex_of.refid
               JOIN langnames ON langnames.langid = reflexes.langid
               WHERE reflex_of.prefid = ?
               ORDER BY langnames.name""",
            (prefid,)
        )
        rows = db_cursor.fetchall()
        # Use ipaform (row[3]) for alignment, form (row[2]) for display
        daughter_forms = [(row[1], row[3] or row[2], row[5]) for row in rows]  # Use ipaform, fallback to form
        reflexes = [ReflexInfo(refid=row[0], lang_name=row[1], form=row[2], ipaform=row[3] or row[2], gloss=row[4]) for row in rows]
        
        if not daughter_forms:
            continue
        
        # Extract patterns from this cognate set
        patterns = extractor.extract_from_cognate_set(
            prefid=prefid,
            proto_form=proto_form,
            proto_gloss=proto_gloss,
            proto_lang=proto_lang_name,
            daughter_forms=daughter_forms,
            languages=languages,
            reflexes=reflexes
        )
        all_patterns.extend(patterns)
    
    # Build correspondence sets
    correspondence_sets = extractor.build_correspondence_sets(all_patterns, languages)
    
    return correspondence_sets, languages
