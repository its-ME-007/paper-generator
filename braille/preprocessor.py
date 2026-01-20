"""
Layer 1 mechanism for Braille pipeline.
Scans text for Braille characters and converts them to natural language.
"""

from braille.fallback_map import BRAILLE_MAP

# Create reverse mapping: Braille Pattern -> ASCII Character
REVERSE_BRAILLE_MAP = {v: k for k, v in BRAILLE_MAP.items()}

def is_braille_char(char):
    """Check if character is a Unicode Braille Pattern."""
    return 0x2800 <= ord(char) <= 0x28FF

def scan_and_convert_braille_to_text(text):
    """
    Layer 1: Scans the input text.
    If a character is a Braille pattern (supported in our map), convert it to its natural language (ASCII) equivalent.
    """
    if not text:
        return ""

    result = []
    for char in text:
        if is_braille_char(char):
            # It's a Braille character
            if char in REVERSE_BRAILLE_MAP:
                # Supported -> Convert to natural language
                result.append(REVERSE_BRAILLE_MAP[char])
            else:
                # Braille character but not in our simple map
                # Keep it as is (or could handle otherwise)
                result.append(char)
        else:
            # Already natural language (or other symbol)
            result.append(char)
            
    return "".join(result)
