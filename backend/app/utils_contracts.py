import re

def is_valid_contract_number(c: str) -> bool:
    if not c:
        return False
    c = str(c).strip()
    if len(c) < 3 or len(c) > 30:
        return False
        
    if c.upper() == "AZURE_DOCINTEL_REF":
        return False
        
    lower_c = c.lower()
    invalid_words = {
        "output", "carrier", "freight", "rate", "rates", "summary", "standard", 
        "number", "notes", "schedules", "details", "charge", "ofr", "harge", 
        "sheet1", "sheet2", "sheet3", "to_usa ports", "to_usa", "ports", "contract",
        "agreement", "service", "validity", "reference", "quote", "quotation"
    }
    if lower_c in invalid_words:
        return False

    if c.count(" ") > 1:
        return False

    has_digit = any(char.isdigit() for char in c)
    if not has_digit:
        if " " in c:
            return False
            
    return True
