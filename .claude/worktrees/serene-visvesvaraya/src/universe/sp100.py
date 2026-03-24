# S&P 100 (OEX) constituent tickers.
# Last verified: 2025-03-23
# Note: Refresh this list periodically as the index rebalances.
# Source: S&P Dow Jones Indices — 101 securities (Alphabet has two share classes).


def get_sp100_universe() -> list[str]:
    """Return the full S&P 100 constituent ticker list (alphabetically sorted)."""
    return [
        "AAPL",   # Apple
        "ABBV",   # AbbVie
        "ABT",    # Abbott Laboratories
        "ACN",    # Accenture
        "ADBE",   # Adobe
        "AIG",    # American International Group
        "AMGN",   # Amgen
        "AMT",    # American Tower
        "AMZN",   # Amazon
        "AVGO",   # Broadcom
        "AXP",    # American Express
        "BA",     # Boeing
        "BAC",    # Bank of America
        "BK",     # Bank of New York Mellon
        "BKNG",   # Booking Holdings
        "BLK",    # BlackRock
        "BMY",    # Bristol-Myers Squibb
        "BRK.B",  # Berkshire Hathaway (Class B)
        "C",      # Citigroup
        "CAT",    # Caterpillar
        "CHTR",   # Charter Communications
        "CL",     # Colgate-Palmolive
        "CMCSA",  # Comcast
        "COF",    # Capital One
        "COP",    # ConocoPhillips
        "COST",   # Costco
        "CRM",    # Salesforce
        "CSCO",   # Cisco Systems
        "CVS",    # CVS Health
        "CVX",    # Chevron
        "DE",     # Deere & Company
        "DHR",    # Danaher
        "DIS",    # Walt Disney
        "DOW",    # Dow Inc.
        "DUK",    # Duke Energy
        "EMR",    # Emerson Electric
        "EXC",    # Exelon
        "F",      # Ford Motor
        "FDX",    # FedEx
        "GD",     # General Dynamics
        "GE",     # GE Aerospace
        "GILD",   # Gilead Sciences
        "GM",     # General Motors
        "GOOG",   # Alphabet (Class C)
        "GOOGL",  # Alphabet (Class A)
        "GS",     # Goldman Sachs
        "HD",     # Home Depot
        "HON",    # Honeywell
        "IBM",    # IBM
        "INTC",   # Intel
        "INTU",   # Intuit
        "JNJ",    # Johnson & Johnson
        "JPM",    # JPMorgan Chase
        "KHC",    # Kraft Heinz
        "KO",     # Coca-Cola
        "LIN",    # Linde
        "LLY",    # Eli Lilly
        "LMT",    # Lockheed Martin
        "LOW",    # Lowe's
        "MA",     # Mastercard
        "MCD",    # McDonald's
        "MDLZ",   # Mondelez International
        "MDT",    # Medtronic
        "MET",    # MetLife
        "META",   # Meta Platforms
        "MMM",    # 3M
        "MO",     # Altria
        "MRK",    # Merck
        "MS",     # Morgan Stanley
        "MSFT",   # Microsoft
        "NEE",    # NextEra Energy
        "NFLX",   # Netflix
        "NKE",    # Nike
        "NOW",    # ServiceNow
        "NVDA",   # NVIDIA
        "ORCL",   # Oracle
        "PEP",    # PepsiCo
        "PFE",    # Pfizer
        "PG",     # Procter & Gamble
        "PM",     # Philip Morris International
        "PYPL",   # PayPal
        "QCOM",   # Qualcomm
        "RTX",    # RTX Corporation
        "SBUX",   # Starbucks
        "SCHW",   # Charles Schwab
        "SO",     # Southern Company
        "SPG",    # Simon Property Group
        "T",      # AT&T
        "TGT",    # Target
        "TMO",    # Thermo Fisher Scientific
        "TMUS",   # T-Mobile US
        "TXN",    # Texas Instruments
        "UNH",    # UnitedHealth Group
        "UNP",    # Union Pacific
        "UPS",    # United Parcel Service
        "USB",    # U.S. Bancorp
        "V",      # Visa
        "VZ",     # Verizon
        "WFC",    # Wells Fargo
        "WMT",    # Walmart
        "XOM",    # Exxon Mobil
    ]
