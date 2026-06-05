"""IPA normalization utilities for converting non-standard transcriptions to IPA."""

import re
import unicodedata

# Ligature tie character
TIE = '\u0361'  # ͡

# Vowels for detecting consonant context
VOWELS = set('aeiouɐɑɒæɔəɛɜɤɪɨʉɯʊʌœøɵɶʏ')

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

# Long vowel marker
LONG = 'ː'

# Double vowels to convert to long vowels
DOUBLE_VOWELS = [(v + v, v + LONG) for v in VOWELS]


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


def add_affricate_ties(text: str) -> str:
    """Add ligature ties to affricates (e.g., ts → t͡s)."""
    # Skip if already has tie
    if TIE in text:
        return text
    for affricate, tied in AFFRICATES:
        text = text.replace(affricate, tied)
    return text


def convert_double_vowels(text: str) -> str:
    """Convert double vowels to vowels with length marks (e.g., aa → aː)."""
    for double, long in DOUBLE_VOWELS:
        text = text.replace(double, long)
    return text


def is_consonant(char: str) -> bool:
    """Check if a character is a consonant (not a vowel, space, or punctuation)."""
    if not char or char in VOWELS:
        return False
    # Check if it's a letter-like character
    if unicodedata.category(char).startswith('L'):
        return True
    # IPA modifiers and diacritics
    if unicodedata.category(char).startswith('M'):
        return False
    return False


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
    2. Add ligature ties to affricates
    3. Convert double vowels to long vowels
    4. Convert y to j when appropriate
    """
    if not form:
        return form
    
    # Apply transformations in order
    result = remove_tone_marks(form)
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
    ]
    
    print("IPA Normalization Tests:")
    print("-" * 60)
    for form in test_forms:
        normalized = normalize_to_ipa(form)
        print(f"{form:30} → {normalized}")
