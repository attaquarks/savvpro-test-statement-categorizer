"""Curated labeled examples for the local text classifier.

Every pair below is a hand-written label contract, authored alongside the
merchant keyword tables in rules.py: "a bank description that reads like
this belongs to this category." They are the same hand-authored knowledge
as the rules, expressed with realistic statement noise (reference numbers,
extra words, abbreviations, casing) so the classifier can learn wording
that exact keyword matching misses.

These are NOT outputs of the rule engine and NOT labels read from any
downloaded statement file. The payment-platform CSVs in the reviewer's
Downloads folder are unlabeled and are never used as ground truth.
"""

from .. import categories as cat

CURATED_LABELED_EXAMPLES: list[tuple[str, str]] = [
    # Software & Subscriptions
    ("adobe systems inc recurring pmt 5591234", cat.SOFTWARE),
    ("adobe creative cloud renewal", cat.SOFTWARE),
    ("figma inc monthly plan pmts 8834129", cat.SOFTWARE),
    ("github com 4154486673 wa subscription", cat.SOFTWARE),
    ("microsoft corporation renewal 5591234", cat.SOFTWARE),
    ("dropbox business subscription", cat.SOFTWARE),
    ("zoom us video communications", cat.SOFTWARE),
    ("amazon web services cloud bill", cat.SOFTWARE),

    # Travel
    ("uber technologies inc help uber com 8812441", cat.TRAVEL),
    ("lyft ride 559123", cat.TRAVEL),
    ("delta air lines tkt 0067441", cat.TRAVEL),
    ("united airlines ticket 016441", cat.TRAVEL),
    ("hilton garden inn stay 881244", cat.TRAVEL),
    ("shell oil 5599123 fuel", cat.TRAVEL),
    ("chevron station 90210", cat.TRAVEL),
    ("amtrak rail ticket 881", cat.TRAVEL),

    # Meals & Entertainment
    ("starbucks coffee store 90210", cat.MEALS),
    ("chipotle mexican grill 8812", cat.MEALS),
    ("panera bread 44172 cafe", cat.MEALS),
    ("dominos pizza order 8812", cat.MEALS),
    ("doordash order 5591234", cat.MEALS),
    ("blue bottle coffee co", cat.MEALS),
    ("grubhub food delivery 5591", cat.MEALS),

    # Office Supplies
    ("staples credit center 5591234", cat.OFFICE_SUPPLIES),
    ("staples advantage purchase", cat.OFFICE_SUPPLIES),
    ("office depot store 8812", cat.OFFICE_SUPPLIES),
    ("uline shipping supplies 559123", cat.OFFICE_SUPPLIES),
    ("office depot inc 90210", cat.OFFICE_SUPPLIES),

    # Hardware & Equipment
    ("best buy electronics 8812441", cat.HARDWARE),
    ("apple store r044 8812", cat.HARDWARE),
    ("newegg com order 5591234", cat.HARDWARE),
    ("b h photo video 8812441", cat.HARDWARE),

    # Advertising & Marketing
    ("google ads ppc spend 5591234", cat.ADVERTISING),
    ("facebook ads campaign 8812", cat.ADVERTISING),
    ("meta platforms ads pmt", cat.ADVERTISING),
    ("godaddy com domain renewal 8812", cat.ADVERTISING),
    ("mailchimp monthly campaign", cat.ADVERTISING),
    ("squarespace website renewal", cat.ADVERTISING),

    # Professional Services
    ("upwork escrow payment 5591234", cat.PROFESSIONAL_SERVICES),
    ("upwork inc freelancer fee", cat.PROFESSIONAL_SERVICES),
    ("intuit quickbooks subscription", cat.PROFESSIONAL_SERVICES),
    ("legalzoom com order 881244", cat.PROFESSIONAL_SERVICES),

    # Education & Training
    ("udemy online course 5591234", cat.EDUCATION),
    ("coursera org monthly subscription", cat.EDUCATION),
    ("skillshare monthly membership", cat.EDUCATION),
    ("domestika course payment 8812", cat.EDUCATION),
]
