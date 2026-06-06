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

# Superscript tone numbers
SUPERSCRIPT_NUMBERS = [
    '\u2070',  # ⁰
    '\u00B9',  # ¹
    '\u00B2',  # ²
    '\u00B3',  # ³
    '\u2074',  # ⁴
    '\u2075',  # ⁵
    '\u2076',  # ⁶
    '\u2077',  # ⁷
    '\u2078',  # ⁸
    '\u2079',  # ⁹
]

# Plosives and affricates that can take aspiration
# Note: These are base forms before affricate ties are added
PLOSIVES = {'p', 'b', 't', 'd', 'k', 'g', 'ɡ', 'c', 'ɟ', 'q', 'ɢ', 'ʔ'}
AFFRICATE_ENDINGS = {'s', 'z', 'ʃ', 'ʒ', 'ɕ', 'ʑ', 'θ', 'ð', 'f', 'v', 'x', 'ɣ', 'ɬ', 'ɮ'}

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

# Retroflex mappings: consonant + underdot → retroflex
# The underdot can be combining dot below (U+0323) or combining diaeresis below (U+0324)
UNDERDOT = '\u0323'           # ̣ COMBINING DOT BELOW
UNDERDIAERESIS = '\u0324'     # ̤ COMBINING DIAERESIS BELOW
RETROFLEX_MARKERS = {UNDERDOT, UNDERDIAERESIS}
RETROFLEX_MAPPINGS = {
    't': 'ʈ',
    'd': 'ɖ',
    's': 'ʂ',
    'z': 'ʐ',
    'n': 'ɳ',
    'l': 'ɭ',
}

# Long vowel marker
LONG = 'ː'

# Aspiration marker
ASPIRATION = 'ʰ'


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


def remove_superscript_numbers(text: str) -> str:
    """Remove superscript tone numbers from text."""
    for num in SUPERSCRIPT_NUMBERS:
        text = text.replace(num, '')
    return text


def convert_retroflex(text: str) -> str:
    """Convert consonants with underdot/underdiaeresis to retroflex equivalents.
    
    E.g., ṭ → ʈ, ḍ → ɖ, ṣ → ʂ, etc.
    Handles both combining dot below (U+0323) and combining diaeresis below (U+0324).
    """
    # Decompose to NFD to separate base character from combining marks
    text = unicodedata.normalize('NFD', text)
    result = []
    i = 0
    while i < len(text):
        char = text[i]
        # Check if next character is a retroflex marker and current char has a retroflex mapping
        if (i + 1 < len(text) and 
            text[i + 1] in RETROFLEX_MARKERS and 
            char in RETROFLEX_MAPPINGS):
            result.append(RETROFLEX_MAPPINGS[char])
            i += 2  # Skip both the consonant and the marker
        else:
            result.append(char)
            i += 1
    # Recompose
    return unicodedata.normalize('NFC', ''.join(result))


def convert_aspiration(text: str) -> str:
    """Convert 'h' following plosives/affricates to aspiration marker ʰ.
    
    Handles both simple plosives (ph → pʰ) and affricates (tsh → t͡sʰ).
    Must be called AFTER affricate ties are added.
    """
    result = []
    i = 0
    chars = list(text)
    
    while i < len(chars):
        char = chars[i]
        
        if char == 'h' and i > 0:
            # Look back to find what precedes this 'h'
            prev_idx = i - 1
            prev_char = chars[prev_idx]
            
            # Check if preceded by a plosive
            if prev_char in PLOSIVES:
                result.append(ASPIRATION)
                i += 1
                continue
            
            # Check if preceded by an affricate (ending in fricative after tie)
            if prev_char in AFFRICATE_ENDINGS:
                # Check if there's a tie before the fricative
                if prev_idx >= 2 and chars[prev_idx - 1] == TIE:
                    result.append(ASPIRATION)
                    i += 1
                    continue
            
            # Check if preceded by a retroflex that can take aspiration
            if prev_char in {'ʈ', 'ɖ'}:
                result.append(ASPIRATION)
                i += 1
                continue
        
        result.append(char)
        i += 1
    
    return ''.join(result)


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
    
    Applies the following transformations in order:
    1. Convert retroflex consonants (t̤ → ʈ, etc.) - before tone removal
    2. Remove tone diacritics
    3. Remove superscript tone numbers
    4. Convert double vowels to long vowels (after tone removal)
    5. Apply character mappings (e.g., ñ → ɲ)
    6. Convert digraphs (e.g., ng → ŋ, ny → ɲ)
    7. Add ligature ties to affricates
    8. Convert h after plosives/affricates to aspiration (ʰ)
    9. Convert y to j when appropriate
    """
    if not form:
        return form
    
    # Apply transformations in order
    result = convert_retroflex(form)         # 1. Retroflex before tone removal
    result = remove_tone_marks(result)       # 2. Remove tone diacritics
    result = remove_superscript_numbers(result)  # 3. Remove superscript numbers
    result = convert_double_vowels(result)   # 4. Double vowels → long (after tone removal)
    result = apply_char_mappings(result)     # 5. Character mappings
    result = convert_digraphs(result)        # 6. Digraphs
    result = add_affricate_ties(result)      # 7. Affricate ties
    result = convert_aspiration(result)      # 8. h → ʰ after plosives/affricates
    result = convert_y_to_j(result)          # 9. y → j
    
    return result


if __name__ == '__main__':
    # Test cases
    test_forms = [
        # Basic tests
        'si-ðu-hu',
        'ʔa-ŋə-tsɐ',
        'si-kwee',           # Double vowel
        'ʔa-rɐ-huu',         # Double vowel
        'sə́-lỳ',             # Tone marks
        'mí-tʰŷn',
        'báŋ-gôɹ',
        'tʃa-ka',
        'dʒu-mi',
        'y-ʔi-ʃî',
        'si-ŋi-tsy',
        # Digraph tests
        'bang',              # ng → ŋ
        'singing',           # Multiple ng → ŋ
        'finger',            # ng in middle
        'anya',              # ny → ɲ
        'kenyan',            # ny → ɲ
        'ñoño',              # ñ → ɲ (precomposed)
        'cañon',             # ñ → ɲ
        # Aspiration tests
        'pha',               # ph → pʰ
        'thi',               # th → tʰ
        'kha',               # kh → kʰ
        'cha',               # ch → cʰ
        'tsha',              # tsh → t͡sʰ
        'tʃha',              # tʃh → t͡ʃʰ (already has ʃ)
        # Retroflex tests (using combining dot below U+0323)
        't\u0323a',          # ṭa: t + underdot → ʈa
        'd\u0323i',          # ḍi: d + underdot → ɖi
        's\u0323u',          # ṣu: s + underdot → ʂu
        'n\u0323a',          # ṇa: n + underdot → ɳa
        'l\u0323i',          # ḷi: l + underdot → ɭi
        # Retroflex tests (using combining diaeresis below U+0324)
        't\u0324a',          # t̤a: t + diaeresis below → ʈa
        'd\u0324i',          # d̤i: d + diaeresis below → ɖi
        # Superscript number tests
        'ma¹',               # Superscript 1
        'pa²³',              # Superscript 2, 3
        'ka⁵⁵',              # Superscript 5, 5
        # Combined tests
        'áá',                # Tone + double vowel → aː
        't\u0323ha',         # Retroflex + aspiration → ʈʰa
        'tsha⁵⁵',            # Affricate + aspiration + tone numbers
    ]
    
    print("IPA Normalization Tests:")
    print("-" * 60)
    for form in test_forms:
        normalized = normalize_to_ipa(form)
        print(f"{form:30} → {normalized}")
