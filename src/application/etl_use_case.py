from datetime import datetime, timedelta
import time
from typing import List

from src.domain.models.stock_price import DelistedTicker
from src.ports.repositories import StockPriceRepository, DelistedTickerRepository, MarketDataProvider

class MarketDataSyncUseCase:
    def __init__(
        self,
        stock_repo: StockPriceRepository,
        delisted_repo: DelistedTickerRepository,
        market_data: MarketDataProvider,
        sleep_between_requests: int = 60
    ):
        self.stock_repo = stock_repo
        self.delisted_repo = delisted_repo
        self.market_data = market_data
        self.sleep_between_requests = sleep_between_requests

    def is_already_up_to_date(self, latest_date) -> bool:
        if not latest_date:
            return False
        now = datetime.now()
        today = now.date()
        if latest_date >= today:
            return True
        weekday = now.weekday()
        if weekday == 5 and latest_date >= (today - timedelta(days=1)):
            return True
        if weekday == 6 and latest_date >= (today - timedelta(days=2)):
            return True
        if weekday == 0 and now.hour < 16 and latest_date >= (today - timedelta(days=3)):
            return True
        if now.hour < 7 and latest_date >= (today - timedelta(days=1)):
            return True
        return False

    def execute(self, tickers: List[str], purge_invalid: List[str] = None):
        if purge_invalid:
            print(f"Purging invalid tickers: {purge_invalid}")
            self.stock_repo.purge_tickers(purge_invalid)

        blacklist = set(self.delisted_repo.get_all())
        if blacklist:
            print(f"Blacklisted (delisted) tickers: {len(blacklist)}")

        failed_stocks = []
        end_date = datetime.now().strftime('%Y-%m-%d')

        for i, ticker in enumerate(tickers, 1):
            if ticker in blacklist:
                continue

            latest_date = self.stock_repo.get_latest_date(ticker)
            if self.is_already_up_to_date(latest_date):
                print(f"[{i}/{len(tickers)}] {ticker} is already up to date ({latest_date}).")
                continue

            fetch_start = (latest_date + timedelta(days=1)).strftime('%Y-%m-%d') if latest_date else "2015-01-01"
            print(f"[{i}/{len(tickers)}] Downloading {ticker} from {fetch_start} to {end_date}...")

            prices = self.market_data.fetch_historical_prices(ticker, fetch_start, end_date)

            if not prices:
                if self.market_data.check_delisted(ticker):
                    print(f"[DELISTED] Blacklisting {ticker}")
                    self.delisted_repo.add(DelistedTicker(ticker=ticker, reason="Delisted", date_added=datetime.now().date()))
                    blacklist.add(ticker)
                continue

            saved_count = self.stock_repo.save_stock_prices(prices)
            print(f"[OK] Saved {saved_count} records for {ticker}")

            if i < len(tickers):
                time.sleep(self.sleep_between_requests)

        return failed_stocks
