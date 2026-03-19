from tavily import TavilyClient
from typing import List, Dict, Any
from app.utils.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


def fetch_company_news(ticker: str, company_name: str) -> List[Dict[str, Any]]:
    try:
        client = TavilyClient(api_key=settings.TAVILY_API_KEY)

        query = f"{company_name} {ticker} stock news financial results 2025"

        response = client.search(
            query=query,
            search_depth="basic",
            max_results=5,
            include_answer=False,
        )

        articles = []
        for result in response.get("results", []):
            articles.append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "content": result.get("content", ""),
                "published_date": result.get("published_date", ""),
                "source": result.get("url", "").split("/")[2] if result.get("url") else "",
            })

        logger.info("news_fetched", ticker=ticker, article_count=len(articles))
        return articles

    except Exception as e:
        logger.error("tavily_fetch_failed", ticker=ticker, error=str(e))
        raise