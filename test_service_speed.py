
import time
from flask_app.services.stock_service import StockService


def test_stock_service():
    service = StockService()
    ticker = "NVDA"

    print(f"Testing data fetch for {ticker}...")
    start = time.time()
    data = service.get_complete_data(ticker)
    duration = time.time() - start

    print(f"Total time: {duration:.2f}s")

    print("\nNews items:")
    for news in data.get('news', [])[:5]:
        print(f"- [{news.get('published')}] {news.get('headline')}")


if __name__ == "__main__":
    test_stock_service()
