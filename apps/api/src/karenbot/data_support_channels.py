"""Researched (UNVERIFIED) support channels for real companies.

Loaded by the dev seeder with verified=False — the policy engine cannot
send to any of these until a human verifies each row in the admin console
against its source URL. Sources: official pages and elliott.org company
contacts (accessed 2026-10-15; see docs/research/support-channels.md,
including the do-not-seed list and the AA executive-bounce warning).
"""

# company name -> list of (channel_type, address, purpose, is_escalation, source_url)
RESEARCH_CHANNELS: dict[str, list[tuple[str, str, str, bool, str]]] = {
    "American Airlines": [
        ("web_form", "https://www.aa.com/customerrelations", "customer relations complaints (ack 30d/resolve 60d)", False, "https://www.aa.com/customerrelations"),
        ("email", "kim.cisek@aa.com", "executive escalation — VP service recovery (bounce reports since 1/2026)", True, "https://elliott.org/company-contacts/american-airlines/"),
        ("email", "robert.isom@aa.com", "executive escalation — CEO (bounce reports)", True, "https://elliott.org/company-contacts/american-airlines/"),
    ],
    "Delta Air Lines": [
        ("web_form", "https://www.delta.com/us/en/need-help/overview?commentComplaintsForm", "comment & complaint form", False, "https://www.delta.com/us/en/need-help/overview"),
        ("email", "heidi.gould@delta.com", "executive escalation — Director of Customer Care", True, "https://elliott.org/company-contacts/delta-air-lines/"),
        ("email", "ed.bastian@delta.com", "executive escalation — CEO", True, "https://elliott.org/company-contacts/delta-air-lines/"),
    ],
    "Southwest Airlines": [
        ("web_form", "https://support.southwest.com/helpcenter/contact-us", "complaints incl. $75 delay-voucher requests", False, "https://support.southwest.com/helpcenter/s/"),
        ("email", "michelle.buckley@wnco.com", "executive escalation — Sr Dir Customer Relations", True, "https://www.elliott.org/company-contacts/southwest-airlines-co/"),
    ],
    "JetBlue": [
        ("web_form", "https://www.jetblue.com/contact-us", "complaints per Customer Service Plan", False, "https://www.jetblue.com/customer-assurance/customer-service-plan"),
        ("email", "steven.olson@jetblue.com", "executive escalation — SVP System Operations", True, "https://elliott.org/company-contacts/jetblue-airways/"),
    ],
    "Uber": [
        ("web_form", "https://help.uber.com", "in-app/help-center trip issue reports", False, "https://www.uber.com/us/en/contact/"),
        ("email", "dcx@uber.com", "executive escalation — Sr Dir Community Operations", True, "https://elliott.org/company-contacts/uber/"),
    ],
    "Amazon": [
        ("web_form", "https://www.amazon.com/gp/help/customer/display.html?nodeId=508510", "account help/contact flows", False, "https://www.amazon.com/gp/help/customer/display.html?nodeId=508510"),
        ("email", "cs-escalations@amazon.com", "escalated customer service (~24h responses)", True, "https://elliott.org/company-contacts/amazon/"),
    ],
    "American Express": [
        ("web_form", "https://www.americanexpress.com/en-us/support/contacts/", "secure message center (account-holder login required — assist mode)", False, "https://www.americanexpress.com/en-us/support/contacts/"),
        ("email", "mohammed.badi@aexp.com", "executive escalation — President Global Servicing", True, "https://elliott.org/company-contacts/american-express/"),
    ],
    "McDonald's": [
        ("web_form", "https://www.mcdonalds.com/us/en-us/feedback.html", "customer feedback form", False, "https://www.mcdonalds.com/us/en-us/feedback.html"),
        ("email", "viva.cohen@mcdonalds.com", "executive escalation — Mgr Global Customer Engagement", True, "https://elliott.org/company-contacts/mcdonalds/"),
    ],
    "Chipotle": [
        ("web_form", "https://www.chipotle.com/contact-us", "contact support + chat", False, "https://www.chipotle.com/contact-us"),
        ("email", "sboatwright@chipotle.com", "executive escalation — CEO", True, "https://elliott.org/company-contacts/chipotle/"),
    ],
}
