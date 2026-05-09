import re

def mask_pii(text: str) -> str:
    """
    Mask sensitive financial and personal information for GDPR/privacy compliance.
    Masks:
    - Bank Account Numbers (IBAN-like)
    - Tax IDs
    - Credit Card Numbers
    """
    if not text:
        return ""
    
    # Mask IBAN/Bank accounts (simple pattern)
    # Matches strings like TR12 3456 7890 ... or simple numeric strings of 10+ digits
    text = re.sub(r'\b[A-Z]{2}\d{2}(?:\s?\d{4}){3,6}\b', lambda m: m.group(0)[:4] + '****' + m.group(0)[-4:], text)
    
    # Mask Credit Cards
    text = re.sub(r'\b(?:\d{4}[-\s]?){3}\d{4}\b', "****-****-****-****", text)
    
    # Mask Tax IDs / SSNs (9-11 digit numbers)
    text = re.sub(r'\b\d{9,11}\b', "**********", text)
    
    return text
