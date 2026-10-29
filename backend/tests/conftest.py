import os

os.environ.setdefault("DATABASE_PATH", ":memory:")

import pytest  # noqa: E402

from app.config import Settings  # noqa: E402
from app.crawler import CrawlConfig, Crawler  # noqa: E402
from app.fetcher import SafeFetcher  # noqa: E402
from tests.fixtures import site  # noqa: E402


@pytest.fixture
def settings() -> Settings:
    return Settings(database_path=":memory:", crawl_delay_s=0, request_timeout_s=2, llm_provider="none",
                    llm_api_key="", cors_origins="http://localhost:5173")


def make_fetcher(transport=None, **kw) -> SafeFetcher:
    return SafeFetcher(user_agent="test-bot", transport=transport or site.transport(),
                       resolver=kw.pop("resolver", site.public_resolver), **kw)


@pytest.fixture
async def crawl_fixture_site():
    async def _run(max_pages=50, max_depth=3, check_links=True, start=site.HOST + "/"):
        async with make_fetcher() as f:
            cfg = CrawlConfig(max_pages=max_pages, max_depth=max_depth, concurrency=4, delay_s=0,
                              max_duration_s=30, link_check_limit=50, check_uncrawled_links=check_links)
            return await Crawler(f, cfg).run(start)
    return _run
