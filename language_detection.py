from fnmatch import fnmatch
from tqdm import tqdm
import yaml
from gpt_client import get_gpt_client
from config import config  # це твій загальний конфіг
from pathlib import Path
from typing import List, Dict, Optional, Set
import re
from typing import List, Dict

def load_country_name_map(path: str) -> Dict[str, Set[str]]:
    """Load name-country map from YAML and convert to uppercase sets."""
    with open(path, 'r', encoding='utf-8') as file:
        raw = yaml.safe_load(file)
    return {
        country: set(name.upper() for name in names)
        for country, names in raw.items()
    }

UKRAINIAN_LETTERS = {'І', 'Ї', 'Є', 'Ґ'}
POLISH_LETTERS = {'Ą', 'Ć', 'Ę', 'Ł', 'Ń', 'Ó', 'Ś', 'Ź', 'Ż'}
NAMES_BY_COUNTRY = load_country_name_map("./config/names_by_country.yaml")
HEURISTIC_PATTERNS = {
    'BY pattern !!!': ['*ENKA', '*AU', '*YEU', '*OU', '*OUSK*', '*DZI*', 'TSI*', '*STS*'],
    'UA pattern !!!': ['*YSHYN', '*ENKO', '*SKYI', '*IV', '*CЬК*', '*ЗЬК*', '*ЦЬК*'],
}


def normalize_name(full_name: str) -> List[str]:
    """Return uppercased list of name parts."""
    return full_name.strip().upper().split()


def contains_special_letters(parts: List[str], alphabet: Set[str]) -> bool:
    """Check if any word contains characters from the given alphabet."""
    return any(char in alphabet for word in parts for char in word)

def match_heuristic_patterns(parts: list[str], patterns: dict[str, list[str]]) -> str | None:
    for country, pattern_list in patterns.items():
        for part in parts:
            if any(fnmatch(part, pat) for pat in pattern_list):
                return country
    return None

def match_known_names(parts: List[str], country_names: Dict[str, Set[str]]) -> str:
    """Match name parts against known name sets per country."""
    for word in parts:
        for country, names in country_names.items():
            if word in names:
                return country
    return None



def detect_country_from_name(full_name: str, name_map: Dict[str, Set[str]] = NAMES_BY_COUNTRY) -> str:
    parts = normalize_name(full_name)

    if contains_special_letters(parts, UKRAINIAN_LETTERS):
        return 'UA'
    
    if contains_special_letters(parts, POLISH_LETTERS):
        return 'PL'
    
    matched_by_pattern = match_heuristic_patterns(parts, HEURISTIC_PATTERNS)
    if matched_by_pattern:
        return matched_by_pattern

    matched_by_name = match_known_names(parts, name_map)
    if matched_by_name:
        return matched_by_name

    return 'EN'