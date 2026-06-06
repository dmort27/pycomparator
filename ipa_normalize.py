"""IPA normalization utilities for converting non-standard transcriptions to IPA."""

import re
import unicodedata

import panphon

# Initialize panphon feature table for vowel/consonant classification
_ft = panphon.FeatureTable()

# Cache for vowel/consonant lookups
_syl_cache: dict[str, int | None] = {}


def _get_syl_feature(char: str) -> int | None:
    """Get the syllabic feature for a character using panphon.
    
    Returns:
        1 if vowel (syllabic), -1 if consonant, None if unknown
    """
    if char in _syl_cache:
        return _syl_cache[char]
    
    fts = _ft.word_fts(char)
    if fts:
        syl = fts[0].get('syl', None)
        _syl_cache[char] = syl
        return syl
    _syl_cache[char] = None
    return None


def is_vowel(char: str) -> bool:
    """Check if a character is a vowel based on panphon syllabic feature."""
    return _get_syl_feature(char) == 1


# Ligature tie character
TIE = '\u0361'  # ͡

# Tone diacritics (combining characters)
TONE_MARKS = [
    '\u0300',  # ̀ grave (low tone)
    '\u0301',  # ́ acute (high tone)
    '\u0302',  # ̂ circumflex (falling tone)
    '\u030C',  # ̌ caron/háček (rising tone)
    '\u0304',  # ̄ macron (mid tone)
    '\u030B',  # ̋ double acute (extra high)
    '\u030F',  # ̏ double grave (extra low)
    '\u1DC4',  # ᷄ mid-high
    '\u1DC5',  # ᷅ low-mid
    '\u1DC8',  # ᷈ rising-falling
]

# Affricates to add ties to (without tie → with tie)
AFFRICATES = [
    ('ts', 't' + TIE + 's'),
    ('dz', 'd' + TIE + 'z'),
    ('tʃ', 't' + TIE + 'ʃ'),
    ('dʒ', 'd' + TIE + 'ʒ'),
    ('tɕ', 't' + TIE + 'ɕ'),
    ('dʑ', 'd' + TIE + 'ʑ'),
    ('tθ', 't' + TIE + 'θ'),
    ('dð', 'd' + TIE + 'ð'),
    ('pf', 'p' + TIE + 'f'),
    ('bv', 'b' + TIE + 'v'),
    ('kx', 'k' + TIE + 'x'),
    ('ɡɣ', 'ɡ' + TIE + 'ɣ'),
    ('tɬ', 't' + TIE + 'ɬ'),
    ('dɮ', 'd' + TIE + 'ɮ'),
]

# Digraph mappings (applied before affricate ties)
# Order matters: longer sequences first
DIGRAPHS = [
    ('ng', 'ŋ'),
    ('ny', 'ɲ'),
]

# Single character mappings
CHAR_MAPPINGS = [
    ('ñ', 'ɲ'),   # Precomposed ñ (U+00F1)
    ('ñ', 'ɲ'),   # n + combining tilde (U+006E U+0303)
]

# Long vowel marker
LONG = 'ː'


def remove_tone_marks(text: str) -> str:
    """Remove tone diacritics from text while preserving other characters."""
    # First decompose to NFD so precomposed characters are split
    text = unicodedata.normalize('NFD', text)
    result = []
    for char in text:
        if char not in TONE_MARKS:
            result.append(char)
    # Recompose (NFC) to get clean output
    return unicodedata.normalize('NFC', ''.join(result))


def apply_char_mappings(text: str) -> str:
    """Apply single character mappings (e.g., ñ → ɲ)."""
    for source, target in CHAR_MAPPINGS:
        text = text.replace(source, target)
    return text


def convert_digraphs(text: str) -> str:
    """Convert common digraphs to IPA (e.g., ng → ŋ, ny → ɲ)."""
    for digraph, ipa in DIGRAPHS:
        text = text.replace(digraph, ipa)
    return text


def add_affricate_ties(text: str) -> str:
    """Add ligature ties to affricates (e.g., ts → t͡s)."""
    # Skip if already has tie
    if TIE in text:
        return text
    for affricate, tied in AFFRICATES:
        text = text.replace(affricate, tied)
    return text


def convert_double_vowels(text: str) -> str:
    """Convert double vowels to vowels with length marks (e.g., aa → aː).
    
    Uses panphon to identify vowels based on the syllabic feature.
    """
    result = []
    i = 0
    chars = list(text)
    while i < len(chars):
        char = chars[i]
        # Check if current and next char are identical vowels
        if i + 1 < len(chars) and char == chars[i + 1] and is_vowel(char):
            result.append(char)
            result.append(LONG)
            i += 2  # Skip both vowels
        else:
            result.append(char)
            i += 1
    return ''.join(result)


def is_consonant(char: str) -> bool:
    """Check if a character is a consonant based on panphon syllabic feature.
    
    A consonant is a letter-like character that is not a vowel (syl != 1).
    """
    if not char:
        return False
    # Check if it's a letter-like character
    if not unicodedata.category(char).startswith('L'):
        return False
    # Use panphon: consonants have syl=-1, vowels have syl=1
    syl = _get_syl_feature(char)
    # If panphon knows it, use that; vowels have syl=1
    if syl is not None:
        return syl != 1
    # Unknown to panphon but is a letter - assume consonant
    return True


def convert_y_to_j(text: str) -> str:
    """Convert /y/ to /j/ when not between consonants."""
    result = []
    chars = list(text)
    
    for i, char in enumerate(chars):
        if char == 'y':
            # Get previous and next characters (skipping combining marks)
            prev_char = None
            next_char = None
            
            # Look backward for a base character
            j = i - 1
            while j >= 0:
                if not unicodedata.category(chars[j]).startswith('M'):
                    prev_char = chars[j]
                    break
                j -= 1
            
            # Look forward for a base character
            j = i + 1
            while j < len(chars):
                if not unicodedata.category(chars[j]).startswith('M'):
                    next_char = chars[j]
                    break
                j += 1
            
            # Convert y to j if NOT surrounded by consonants on both sides
            prev_is_consonant = prev_char is not None and is_consonant(prev_char)
            next_is_consonant = next_char is not None and is_consonant(next_char)
            
            if not (prev_is_consonant and next_is_consonant):
                result.append('j')
            else:
                result.append('y')
        else:
            result.append(char)
    
    return ''.join(result)


def normalize_to_ipa(form: str) -> str:
    """
    Normalize a transcription to IPA.
    
    Applies the following transformations:
    1. Remove tone marks
    2. Apply character mappings (e.g., ñ → ɲ)
    3. Convert digraphs (e.g., ng → ŋ, ny → ɲ)
    4. Add ligature ties to affricates
    5. Convert double vowels to long vowels
    6. Convert y to j when appropriate
    """
    if not form:
        return form
    
    # Apply transformations in order
    result = remove_tone_marks(form)
    result = apply_char_mappings(result)
    result = convert_digraphs(result)
    result = add_affricate_ties(result)
    result = convert_double_vowels(result)
    result = convert_y_to_j(result)
    
    return result


if __name__ == '__main__':
    # Test cases
    test_forms = [
        'si-ðu-hu',
        'ʔa-ŋə-tsɐ',
        'si-kwee',
        'ʔa-rɐ-huu',
        'sə́-lỳ',
        'mí-tʰŷn',
        'báŋ-gôɹ',
        'tʃa-ka',
        'dʒu-mi',
        'y-ʔi-ʃî',
        'si-ŋi-tsy',
        'bang',       # Test ng → ŋ
        'singing',    # Test multiple ng → ŋ
        'finger',     # Test ng in middle
        'anya',       # Test ny → ɲ
        'kenyan',     # Test ny → ɲ
        'ñoño',       # Test ñ → ɲ (precomposed)
        'cañon',      # Test ñ → ɲ
    ]
    
    print("IPA Normalization Tests:")
    print("-" * 60)
    for form in test_forms:
        normalized = normalize_to_ipa(form)
        print(f"{form:30} → {normalized}")
