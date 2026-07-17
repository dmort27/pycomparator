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
    """
    A single correspondence pattern (one column from an alignment).
    
    Key distinction:
    - Language NOT in phonemes dict → "no data" (language has no reflex in cognate set)
    - Language IN phonemes dict with value '' → "blank/∅" (gap in alignment)
    """
    # Maps language name -> phoneme ('' for gaps, absence means no data)
    phonemes: dict[str, str]
    
    # Sentinel for "no data" - used in comparisons
    _NO_DATA = object()
    
    # Sentinel string for "no data" - sorts after all real phonemes
    _NO_DATA_STR = '\uffff'  # Last valid Unicode character
    
    def to_tuple(self, languages: list[str]) -> tuple:
        """
        Convert to ordered tuple for hashing/comparison.
        
        Uses a special sentinel string to represent "no data" to distinguish 
        from '' (blank/∅) while remaining sortable.
        """
        return tuple(
            self.phonemes.get(lang, CorrespondencePattern._NO_DATA_STR) 
            for lang in languages
        )
    
    def is_instance_of(self, other: 'CorrespondencePattern', languages: list[str]) -> bool:
        """
        Check if this pattern is an instance of another pattern.
        
        A is an instance of B if:
        1. There are no conflicting (lang, phoneme) pairs between A and B
        2. There are at least 2 matching non-empty positions
        
        Rules:
        - "No data" (not in dict) can unify with anything
        - "Blank/∅" (in dict with '') only unifies with blank/∅
        """
        matching_positions = 0
        
        for lang in languages:
            # Check if language has data in each pattern
            my_has_data = lang in self.phonemes
            other_has_data = lang in other.phonemes
            
            # If either has no data, skip (no conflict possible)
            if not my_has_data or not other_has_data:
                continue
            
            my_phoneme = self.phonemes[lang]
            other_phoneme = other.phonemes[lang]
            
            # Check for conflict (including blank vs non-blank)
            if my_phoneme != other_phoneme:
                return False
            
            # Count matching positions (only non-blank)
            if my_phoneme != '':
                matching_positions += 1
        
        # Require at least 2 matching non-blank positions
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
    # Languages that have at least one reflex in this correspondence set
    languages_with_data: set[str] = field(default_factory=set)
    
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
            'cognate_sets': [cs.to_dict() for cs in self.cognate_sets],
            'languages_with_data': list(self.languages_with_data)
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
        Group patterns into correspondence sets using frequency-based agglomeration.
        
        Algorithm:
        1. First group identical patterns together
        2. Precompute compatibility between all pairs (O(n²) once)
        3. Use Union-Find to efficiently track merges
        4. Process merge candidates in priority order (least complete first)
        
        Args:
            patterns_with_cognates: List of (pattern, cognate_info) tuples
            languages: Ordered list of languages for consistent ordering
            
        Returns:
            List of CorrespondenceSet objects, sorted by count (descending)
        """
        import heapq
        
        def count_non_empty(pattern: CorrespondencePattern) -> int:
            """Count non-empty positions in a pattern."""
            return sum(1 for lang in languages 
                      if pattern.phonemes.get(lang, '') != '')
        
        # Sentinel value to distinguish "no data" from "blank/∅"
        NO_DATA = object()
        
        def patterns_compatible(p1: CorrespondencePattern, p2: CorrespondencePattern) -> bool:
            """
            Check if two patterns are compatible (no contradictory phonemes).
            
            Rules:
            - "No data" (language not in pattern) can unify with anything
            - "Blank/∅" (language in pattern with value '') only unifies with blank/∅
            - Different phonemes are incompatible
            """
            for lang in languages:
                # Use sentinel to distinguish "not present" from "present with ''"
                ph1 = p1.phonemes.get(lang, NO_DATA)
                ph2 = p2.phonemes.get(lang, NO_DATA)
                
                # If either has no data, they're compatible for this language
                if ph1 is NO_DATA or ph2 is NO_DATA:
                    continue
                
                # Both have data - they must match (including both being '')
                if ph1 != ph2:
                    return False
            
            return True
        
        def merge_patterns(p1: CorrespondencePattern, p2: CorrespondencePattern) -> CorrespondencePattern:
            """
            Merge two compatible patterns.
            
            Rules:
            - If one has data and other has no data, use the one with data
            - If both have data, they must be equal (including both being ''), use either
            """
            merged_phonemes = {}
            for lang in languages:
                ph1 = p1.phonemes.get(lang, NO_DATA)
                ph2 = p2.phonemes.get(lang, NO_DATA)
                
                if ph1 is NO_DATA and ph2 is NO_DATA:
                    # Neither has data - don't include in merged pattern
                    continue
                elif ph1 is NO_DATA:
                    # Only p2 has data
                    merged_phonemes[lang] = ph2
                elif ph2 is NO_DATA:
                    # Only p1 has data
                    merged_phonemes[lang] = ph1
                else:
                    # Both have data - use p2 (target) value (they should be equal)
                    merged_phonemes[lang] = ph2
            
            return CorrespondencePattern(phonemes=merged_phonemes)
        
        # Step 1: Group by exact pattern tuple first (agglomerate identical correspondences)
        exact_groups: dict[tuple, list[tuple[CorrespondencePattern, CognateSetInfo]]] = defaultdict(list)
        
        for pattern, cognate_info in patterns_with_cognates:
            pattern_tuple = pattern.to_tuple(languages)
            exact_groups[pattern_tuple].append((pattern, cognate_info))
        
        # Build initial correspondence sets from exact groups
        correspondence_sets: list[CorrespondenceSet] = []
        
        for pattern_tuple, items in exact_groups.items():
            canonical_pattern = items[0][0]
            corr_set = CorrespondenceSet(pattern=canonical_pattern)
            for _, cognate_info in items:
                corr_set.cognate_sets.append(cognate_info)
            corr_set.count = len(corr_set.cognate_sets)
            correspondence_sets.append(corr_set)
        
        n = len(correspondence_sets)
        if n <= 1:
            return correspondence_sets
        
        # Step 2: Precompute blanks count and non-empty count for each set
        blanks = [len(languages) - count_non_empty(cs.pattern) for cs in correspondence_sets]
        
        # Union-Find data structure for tracking merges
        parent = list(range(n))
        rank = [0] * n
        
        def find(x: int) -> int:
            if parent[x] != x:
                parent[x] = find(parent[x])  # Path compression
            return parent[x]
        
        def union(x: int, y: int) -> int:
            """Union x into y, return the new root (always y's root)."""
            rx, ry = find(x), find(y)
            if rx == ry:
                return rx
            # Always merge into ry (the target)
            parent[rx] = ry
            if rank[rx] == rank[ry]:
                rank[ry] += 1
            return ry
        
        # Step 3: Build priority queue of merge candidates
        # Priority: (source_blanks, -target_non_empty, -target_count, source_idx, target_idx)
        # This prioritizes: most blanks in source, most complete target, most frequent target
        heap = []
        
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                if patterns_compatible(correspondence_sets[i].pattern, correspondence_sets[j].pattern):
                    # i is potential source, j is potential target
                    # Only add if j is "better" than i (fewer blanks or same blanks but more frequent)
                    if blanks[j] < blanks[i] or (blanks[j] == blanks[i] and correspondence_sets[j].count > correspondence_sets[i].count):
                        # Priority: process sources with most blanks first, prefer targets with fewer blanks and higher count
                        priority = (-blanks[i], blanks[j], -correspondence_sets[j].count, i, j)
                        heapq.heappush(heap, priority)
        
        # Step 4: Process merges using the priority queue
        while heap:
            neg_src_blanks, tgt_blanks, neg_tgt_count, src_idx, tgt_idx = heapq.heappop(heap)
            
            # Check if both sets are still roots (not already merged)
            src_root = find(src_idx)
            tgt_root = find(tgt_idx)
            
            if src_root == tgt_root:
                # Already in the same set
                continue
            
            # Check if this merge is still valid (patterns might have changed due to prior merges)
            src_set = correspondence_sets[src_root]
            tgt_set = correspondence_sets[tgt_root]
            
            if not patterns_compatible(src_set.pattern, tgt_set.pattern):
                continue
            
            # Recompute blanks for current roots
            current_src_blanks = len(languages) - count_non_empty(src_set.pattern)
            current_tgt_blanks = len(languages) - count_non_empty(tgt_set.pattern)
            
            # Only merge if target is still "better"
            if not (current_tgt_blanks < current_src_blanks or 
                    (current_tgt_blanks == current_src_blanks and tgt_set.count > src_set.count)):
                continue
            
            # Perform the merge: src_root into tgt_root
            tgt_set.cognate_sets.extend(src_set.cognate_sets)
            tgt_set.count = len(tgt_set.cognate_sets)
            tgt_set.pattern = merge_patterns(src_set.pattern, tgt_set.pattern)
            
            # Update union-find
            union(src_root, tgt_root)
        
        # Step 5: Collect final sets (only roots)
        final_sets = []
        seen_roots = set()
        for i in range(n):
            root = find(i)
            if root not in seen_roots:
                seen_roots.add(root)
                final_sets.append(correspondence_sets[root])
        
        # Step 6: Finalize - sort cognate sets and compute metadata
        for corr_set in final_sets:
            corr_set.cognate_sets.sort(key=lambda cs: cs.proto_gloss.lower())
            # Compute languages_with_data from all cognate sets in this correspondence set
            langs_with_data = set()
            for cog_set in corr_set.cognate_sets:
                # The proto-language always has data (it's the source of the cognate set)
                if cog_set.languages:
                    langs_with_data.add(cog_set.languages[0])  # proto-language
                # Add daughter languages that have reflexes
                if cog_set.reflexes:
                    for reflex in cog_set.reflexes:
                        langs_with_data.add(reflex.lang_name)
            corr_set.languages_with_data = langs_with_data
        
        # Filter out sets with fewer than 2 non-empty positions
        filtered_sets = [cs for cs in final_sets 
                        if count_non_empty(cs.pattern) >= 2]
        
        # Sort correspondence sets by count (descending), then by pattern
        result = sorted(
            filtered_sets,
            key=lambda cs: (-cs.count, cs.pattern_tuple(languages))
        )
        
        return result


def extract_correspondence_sets_for_protolang(
    db_cursor,
    plangid: int,
    proto_lang_name: str,
    selected_languages: list[str] | None = None
) -> tuple[list[CorrespondenceSet], list[str]]:
    """
    Extract all correspondence sets for a given proto-language.
    
    Args:
        db_cursor: Database cursor
        plangid: Proto-language ID
        proto_lang_name: Proto-language name
        selected_languages: Optional list of language names to include. If None, all languages are included.
        
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
    all_daughter_languages = [row[0] for row in db_cursor.fetchall()]
    
    # Full language list: proto-language first, then daughters
    all_languages = [proto_lang_name] + all_daughter_languages
    
    # Filter to selected languages if specified
    if selected_languages is not None:
        selected_set = set(selected_languages)
        # Always include proto-language, then filter daughters
        languages = [proto_lang_name] + [lang for lang in all_daughter_languages if lang in selected_set]
    else:
        languages = all_languages
    
    # Create set of selected languages for filtering daughter forms
    languages_set = set(languages)
    
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
        
        # Filter to only include selected languages
        filtered_rows = [row for row in rows if row[1] in languages_set]
        
        # Use ipaform (row[3]) for alignment, form (row[2]) for display
        daughter_forms = [(row[1], row[3] or row[2], row[5]) for row in filtered_rows]
        reflexes = [ReflexInfo(refid=row[0], lang_name=row[1], form=row[2], ipaform=row[3] or row[2], gloss=row[4]) for row in filtered_rows]
        
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
