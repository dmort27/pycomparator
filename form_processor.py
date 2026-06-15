"""Process forms for data intake: IPA normalization and syllabification."""

from syllabiphon.syllabify import Syllabify
from ipa_normalize import normalize_to_ipa

# Initialize syllabifier once
_syllabifier = Syllabify()


def syllabify_form(ipa_form: str) -> str:
    """
    Syllabify an IPA form and join syllables with hyphens.
    
    Handles space-separated words by syllabifying each word separately.
    
    Args:
        ipa_form: IPA transcription (hyphens should already be removed)
        
    Returns:
        Syllabified form with hyphens at syllable boundaries
    """
    if not ipa_form:
        return ipa_form
    
    # Split on spaces to handle multi-word forms
    words = ipa_form.split(' ')
    syllabified_words = []
    
    for word in words:
        if not word:
            continue
        try:
            syls = _syllabifier._syl_seg(word)
            # Join phonemes within each syllable, then join syllables with hyphens
            syllabified = '-'.join([''.join([seg.ph for seg in syl]) for syl in syls])
            syllabified_words.append(syllabified)
        except Exception:
            # If syllabification fails, use the original word
            syllabified_words.append(word)
    
    return ' '.join(syllabified_words)


def process_form(form: str) -> tuple[str, str]:
    """
    Process a form for database insertion.
    
    Processing steps:
    1. Normalize to IPA (removes tones, adds affricate ties, etc.)
    2. Preserve spaces
    3. Remove existing hyphens
    4. Re-syllabify and add hyphens at syllable boundaries
    
    Args:
        form: Raw input form
        
    Returns:
        Tuple of (processed_ipaform, original_form)
        - processed_ipaform: Normalized and syllabified IPA form
        - original_form: The original input for reference
    """
    if not form:
        return '', form
    
    original = form.strip()
    
    # Step 1: Normalize to IPA
    normalized = normalize_to_ipa(original)
    if normalized is None:
        normalized = original
    
    # Step 2: Remove existing hyphens (spaces are preserved)
    no_hyphens = normalized.replace('-', '')
    
    # Step 3: Syllabify
    syllabified = syllabify_form(no_hyphens)
    
    return syllabified, original


def detect_delimiter(content: str) -> str:
    """
    Auto-detect the delimiter of a CSV/TSV file.
    
    Args:
        content: File content as string
        
    Returns:
        Detected delimiter (',' or '\\t')
    """
    first_lines = content.split('\n')[:5]
    
    tab_count = sum(line.count('\t') for line in first_lines)
    comma_count = sum(line.count(',') for line in first_lines)
    
    return '\t' if tab_count >= comma_count else ','


def parse_lexicon_file(content: str, delimiter: str | None = None) -> list[tuple[str, str]]:
    """
    Parse a lexicon file (CSV/TSV) with gloss in first column and form in second.
    
    Args:
        content: File content as string
        delimiter: Column delimiter. If None, auto-detect.
        
    Returns:
        List of (gloss, form) tuples
    """
    if delimiter is None:
        delimiter = detect_delimiter(content)
    
    entries = []
    for line in content.strip().split('\n'):
        if not line.strip():
            continue
        
        parts = line.split(delimiter)
        if len(parts) >= 2:
            gloss = parts[0].strip()
            form = parts[1].strip()
            if gloss and form:
                entries.append((gloss, form))
    
    return entries


if __name__ == '__main__':
    # Test processing
    test_forms = [
        'siðuhu',
        'ʔafak',
        'tekku',
        'si kwi',  # Multi-word with space
        'praŋka',
        'si-ðu-hu',  # With existing hyphens
    ]
    
    print('Form Processing Tests:')
    print('-' * 60)
    for form in test_forms:
        processed, original = process_form(form)
        print(f'{original:20} -> {processed}')
