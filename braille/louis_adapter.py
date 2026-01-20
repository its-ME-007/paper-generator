"""
Liblouis adapter with intelligent fallback.
Single source of truth for Braille conversion.
"""

from braille.fallback_map import BRAILLE_MAP, CAPITAL_INDICATOR, NUMBER_INDICATOR, UNKNOWN_CHAR
from braille.math_handler import should_use_math_table

# Try to import liblouis
try:
    import louis  # type: ignore
    LIBLOUIS_AVAILABLE = True
except ImportError:
    LIBLOUIS_AVAILABLE = False

# UEB table selection
UEB_GRADE2_TABLE = ["en-ueb-g2.ctb"]
UEB_MATH_TABLE = ["en-ueb-math.ctb"]
UEB_GRADE1_TABLE = ["en-ueb-g1.ctb"]

def is_available():
    """Check if Liblouis is available."""
    return LIBLOUIS_AVAILABLE

def translate_with_liblouis(text, use_math=False):
    """
    Translate text to Braille using Liblouis.
    
    Args:
        text: Text to translate
        use_math: Use math table if True
        
    Returns:
        str: Braille text
        
    Raises:
        RuntimeError: If Liblouis not available
    """
    if not LIBLOUIS_AVAILABLE:
        raise RuntimeError("Liblouis not available")
    
    if not text:
        return ''
    
    # Select table
    table = UEB_MATH_TABLE if use_math else UEB_GRADE2_TABLE
    
    try:
        return louis.translateString(table, str(text))
    except Exception as e:
        # If translation fails, fall back to Grade 1
        try:
            return louis.translateString(UEB_GRADE1_TABLE, str(text))
        except:
            raise RuntimeError(f"Liblouis translation failed: {e}")

def translate_with_fallback(text):
    """
    Emergency fallback: character-by-character mapping.
    Used only when Liblouis unavailable.
    
    Args:
        text: Text to convert
        
    Returns:
        str: Braille text (basic mapping)
    """
    if not text:
        return ''
    
    result = []
    text = str(text)
    in_number_mode = False
    
    for char in text:
        # Handle numbers - need number indicator before first digit
        if char.isdigit():
            if not in_number_mode:
                result.append(NUMBER_INDICATOR)
                in_number_mode = True
            result.append(BRAILLE_MAP.get(char, UNKNOWN_CHAR))
        # Handle uppercase letters
        elif char.isupper():
            in_number_mode = False
            result.append(CAPITAL_INDICATOR)
            result.append(BRAILLE_MAP.get(char.lower(), UNKNOWN_CHAR))
        # Handle mapped characters
        elif char in BRAILLE_MAP:
            in_number_mode = False
            result.append(BRAILLE_MAP[char])
        # Unknown character
        else:
            in_number_mode = False
            result.append(UNKNOWN_CHAR)
    
    return ''.join(result)

def translate(text, force_fallback=False):
    """
    Main translation function - single source of truth.
    
    Strategy:
    1. If Liblouis available: use it (detect math automatically)
    2. If Liblouis unavailable: use fallback map
    3. Never mix both in same text segment
    
    Args:
        text: Text to convert to Braille
        force_fallback: Force use of fallback map (testing only)
        
    Returns:
        str: Braille text
    """
    if not text:
        return ''
    
    # Force fallback if requested (testing)
    if force_fallback:
        return translate_with_fallback(text)
    
    # Use Liblouis if available
    if LIBLOUIS_AVAILABLE:
        use_math = should_use_math_table(text)
        try:
            return translate_with_liblouis(text, use_math=use_math)
        except RuntimeError:
            # Liblouis failed, use fallback
            return translate_with_fallback(text)
    else:
        # No Liblouis, use fallback
        return translate_with_fallback(text)

def get_status():
    """
    Get current Braille system status.
    
    Returns:
        dict: Status information
    """
    return {
        'liblouis_available': LIBLOUIS_AVAILABLE,
        'default_table': 'UEB Grade 2' if LIBLOUIS_AVAILABLE else 'Fallback Map',
        'math_support': LIBLOUIS_AVAILABLE,
        'quality': 'Professional' if LIBLOUIS_AVAILABLE else 'Basic'
    }
