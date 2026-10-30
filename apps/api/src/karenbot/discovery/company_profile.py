"""Map inbox sender addresses to companies the user does business with.

Conservative on purpose: a sender only becomes a profile entry when its
domain label maps to a company we know (explicit label map or a match
against the companies table). Random newsletters never become "companies
you use". The scan is user-initiated and the resulting list is shown to
the user to edit — never a silent dossier.
"""

# Sender-domain labels that don't literally match the company's name.
KNOWN_SENDER_LABELS: dict[str, str] = {
    "att": "AT&T",
    "aa": "American Airlines",
    "americanairlines": "American Airlines",
    "aexp": "American Express",
    "americanexpress": "American Express",
    "amex": "American Express",
    "xfinity": "Comcast / Xfinity",
    "comcast": "Comcast / Xfinity",
    "mcdonalds": "McDonald's",
    "mcd": "McDonald's",
    "deltaair": "Delta Air Lines",
    "ubereats": "Uber",
    "awscloud": "Amazon Web Services",
    "aws": "Amazon Web Services",
    # Demo company used by the mock inbox.
    "acmeair": "Acme Air",
}


def sender_label(address: str) -> str | None:
    """Registered-domain label: 'promo@e.delta.com' -> 'delta'."""
    if "@" not in address:
        return None
    domain = address.rsplit("@", 1)[1].lower().strip()
    parts = [p for p in domain.split(".") if p]
    if len(parts) < 2:
        return None
    return parts[-2]


def companies_from_senders(
    addresses: list[str], known_company_names: list[str]
) -> set[str]:
    """Company names used by this inbox, from sender domains."""
    # First word of each known company name, lowercased: "delta" -> "Delta
    # Air Lines". Single tokens only; too-short tokens are skipped (noise).
    by_token: dict[str, str] = {}
    for name in known_company_names:
        token = name.split()[0].lower().strip(".,'&")
        if len(token) >= 3:
            by_token.setdefault(token, name)

    found: set[str] = set()
    for address in addresses:
        label = sender_label(address)
        if label is None:
            continue
        if label in KNOWN_SENDER_LABELS:
            found.add(KNOWN_SENDER_LABELS[label])
        elif label in by_token:
            found.add(by_token[label])
    return found
