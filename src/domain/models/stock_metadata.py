from dataclasses import dataclass, field
from typing import Dict, List, Optional

@dataclass
class StockMetadata:
    ticker: str
    company_name: str
    country: str            # e.g., 'USA', 'China'
    exchange: str           # e.g., 'NYSE', 'NASDAQ', 'SSE', 'SZSE'
    sector: str             # e.g., 'Technology', 'Financials'
    pe_ratio: Optional[float] = None # Price-to-Earnings Ratio (None = missing/extreme)
    tags: List[str] = field(default_factory=list) # e.g. ['State-Owned', 'ESG', 'Tech']

# Pre-populated Metadata Registry for Project Ticker Universe
TICKER_METADATA_REGISTRY: Dict[str, StockMetadata] = {
    # US Stocks
    "AAPL": StockMetadata("AAPL", "Apple Inc.", "USA", "NASDAQ", "Technology", 32.4, ["Tech", "MegaCap"]),
    "MSFT": StockMetadata("MSFT", "Microsoft Corp.", "USA", "NASDAQ", "Technology", 35.1, ["Tech", "MegaCap", "Cloud"]),
    "AMZN": StockMetadata("AMZN", "Amazon.com Inc.", "USA", "NASDAQ", "Consumer Cyclical", 42.8, ["E-Commerce", "Cloud"]),
    "GOOGL": StockMetadata("GOOGL", "Alphabet Inc.", "USA", "NASDAQ", "Communication Services", 24.6, ["Tech", "Search"]),
    "NVDA": StockMetadata("NVDA", "NVIDIA Corp.", "USA", "NASDAQ", "Technology", 68.2, ["Tech", "Semiconductor", "AI"]),
    "TSLA": StockMetadata("TSLA", "Tesla Inc.", "USA", "NASDAQ", "Consumer Cyclical", 74.5, ["EV", "Automotive"]),
    "META": StockMetadata("META", "Meta Platforms Inc.", "USA", "NASDAQ", "Communication Services", 26.8, ["Social Media", "Tech"]),
    "JPM": StockMetadata("JPM", "JPMorgan Chase & Co.", "USA", "NYSE", "Financial Services", 12.1, ["Banking"]),
    "V": StockMetadata("V", "Visa Inc.", "USA", "NYSE", "Financial Services", 29.5, ["Payments"]),
    "JNJ": StockMetadata("JNJ", "Johnson & Johnson", "USA", "NYSE", "Healthcare", 18.2, ["Pharma"]),
    "PG": StockMetadata("PG", "Procter & Gamble", "USA", "NYSE", "Consumer Defensive", 25.4, ["Staples"]),
    "UNH": StockMetadata("UNH", "UnitedHealth Group", "USA", "NYSE", "Healthcare", 21.3, ["Insurance"]),
    "HD": StockMetadata("HD", "Home Depot Inc.", "USA", "NYSE", "Consumer Cyclical", 23.1, ["Retail"]),
    "BAC": StockMetadata("BAC", "Bank of America", "USA", "NYSE", "Financial Services", 13.4, ["Banking"]),
    "DIS": StockMetadata("DIS", "Walt Disney Co.", "USA", "NYSE", "Communication Services", None, ["Entertainment"]),

    # Chinese Stocks
    "600519.SS": StockMetadata("600519.SS", "Kweichow Moutai", "China", "SSE", "Consumer Defensive", 28.3, ["Liquor", "State-Owned"]),
    "000001.SZ": StockMetadata("000001.SZ", "Ping An Bank", "China", "SZSE", "Financial Services", 5.6, ["Banking"]),
    "600036.SS": StockMetadata("600036.SS", "China Merchants Bank", "China", "SSE", "Financial Services", 6.2, ["Banking"]),
    "000858.SZ": StockMetadata("000858.SZ", "Wuliangye Yibin", "China", "SZSE", "Consumer Defensive", 18.9, ["Liquor"]),
    "601318.SS": StockMetadata("601318.SS", "Ping An Insurance", "China", "SSE", "Financial Services", 9.1, ["Insurance"]),
    "600276.SS": StockMetadata("600276.SS", "Jiangsu Hengrui Pharma", "China", "SSE", "Healthcare", 48.5, ["Pharma"]),
    "600900.SS": StockMetadata("600900.SS", "China Yangtze Power", "China", "SSE", "Utilities", 20.4, ["State-Owned", "Clean Energy"]),
    "002594.SZ": StockMetadata("002594.SZ", "BYD Co. Ltd.", "China", "SZSE", "Consumer Cyclical", 22.8, ["EV", "Automotive"]),
    "601888.SS": StockMetadata("601888.SS", "China Tourism Group", "China", "SSE", "Consumer Cyclical", None, ["State-Owned", "Tourism"])
}

def get_metadata(ticker: str) -> StockMetadata:
    """Returns StockMetadata for ticker or a default fallback based on ticker suffix."""
    if ticker in TICKER_METADATA_REGISTRY:
        return TICKER_METADATA_REGISTRY[ticker]
    
    suffix_map = {
        ".SS": ("China", "Shanghai Stock Exchange"),
        ".SZ": ("China", "Shenzhen Stock Exchange"),
        ".T": ("Japan", "Tokyo Stock Exchange"),
        ".HK": ("Hong Kong", "Hong Kong Stock Exchange"),
        ".L": ("United Kingdom", "London Stock Exchange"),
        ".PA": ("France", "Euronext Paris"),
        ".DE": ("Germany", "Deutsche Börse (XETRA)"),
        ".SW": ("Switzerland", "SIX Swiss Exchange"),
        ".NS": ("India", "National Stock Exchange of India"),
        ".BO": ("India", "Bombay Stock Exchange"),
        ".TO": ("Canada", "Toronto Stock Exchange"),
        ".TW": ("Taiwan", "Taiwan Stock Exchange"),
        ".KS": ("South Korea", "Korea Exchange"),
        ".AX": ("Australia", "Australian Securities Exchange"),
        ".SA": ("Brazil", "B3"),
        ".SR": ("Saudi Arabia", "Saudi Exchange (Tadawul)"),
        ".ST": ("Sweden", "Nasdaq Stockholm"),
        ".CO": ("Denmark", "Nasdaq Copenhagen"),
        ".MC": ("Spain", "Bolsa de Madrid"),
        ".MI": ("Italy", "Borsa Italiana"),
        ".AS": ("Netherlands", "Euronext Amsterdam"),
        ".SI": ("Singapore", "Singapore Exchange"),
        ".MX": ("Mexico", "Mexican Stock Exchange"),
        ".OL": ("Norway", "Oslo Børs"),
        ".HE": ("Finland", "Nasdaq Helsinki"),
        ".TA": ("Israel", "Tel Aviv Stock Exchange"),
    }

    country = "USA"
    exchange = "US Exchange (NYSE/NASDAQ)"

    for suffix, (c, ex) in suffix_map.items():
        if ticker.endswith(suffix):
            country = c
            exchange = ex
            break

    return StockMetadata(
        ticker=ticker,
        company_name=ticker,
        country=country,
        exchange=exchange,
        sector="General Market",
        pe_ratio=None,
        tags=[]
    )
