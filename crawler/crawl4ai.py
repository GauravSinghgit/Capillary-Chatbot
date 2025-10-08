import os
import re
import json
from urllib.parse import urljoin, urlparse
from pathlib import Path
from typing import List, Dict, Any, Set

import asyncio
import httpx
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

DOCS_DOMAIN = os.getenv("DOCS_DOMAIN", "https://docs.capillarytech.com/")
CRAWL_MAX_PAGES = int(os.getenv("CRAWL_MAX_PAGES", "500"))
CONCURRENCY = int(os.getenv("CRAWL_CONCURRENCY", "5"))

OUTPUT_DIR = Path("data/raw")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def same_domain(url: str, root: str) -> bool:
    try:
        u = urlparse(url)
        r = urlparse(root)
        return (u.netloc or "") == (r.netloc or "")
    except Exception:
        return False


async def fetch_sitemap_urls(seed: str, limit: int) -> List[str]:
    urls: List[str] = []
    candidates = [urljoin(seed, "/sitemap.xml"), urljoin(seed, "/sitemap_index.xml"), seed]
    async with httpx.AsyncClient(timeout=30) as client:
        for sm in candidates[:2]:
            try:
                resp = await client.get(sm)
                if resp.status_code == 200 and ("<urlset" in resp.text or "<sitemapindex" in resp.text):
                    urls = re.findall(r"<loc>\s*([^<]+)\s*</loc>", resp.text)
                    urls = [u.strip() for u in urls if u.strip()]
                    urls = [u for u in urls if same_domain(u, seed)]
                    break
            except Exception:
                pass
        if not urls:
            urls = [seed]

    # de-dup and clamp
    seen: Set[str] = set()
    uniq: List[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
        if len(uniq) >= limit:
            break
    return uniq


async def render_page(page, url: str) -> Dict[str, Any]:
    try:
        await page.goto(url, wait_until="networkidle", timeout=60000)
        title = await page.title() or ""

        # Extract main content using Readability
        await page.add_script_tag(
            url="https://cdnjs.cloudflare.com/ajax/libs/readability/0.4.4/Readability.min.js"
        )
        content = await page.evaluate("""
            () => {
                try {
                    const docClone = document.cloneNode(true);
                    const article = new Readability(docClone).parse();
                    return article ? article.content : document.body.innerText;
                } catch { return document.body.innerText; }
            }
        """)

        md = f"# {title}\n\n{content}"
        return {"url": url, "title": title, "markdown": md}
    except Exception:
        return {"url": url, "title": "", "markdown": ""}
    

async def render_and_extract(urls: List[str]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []

    semaphore = asyncio.Semaphore(CONCURRENCY)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        async def worker(url):
            async with semaphore:
                page = await context.new_page()
                try:
                    result = await render_page(page, url)
                    results.append(result)
                finally:
                    await page.close()

        await asyncio.gather(*(worker(url) for url in urls))

        await context.close()
        await browser.close()

    return results


def persist_pages(pages: List[Dict[str, Any]]):
    for page in pages:
        url: str = page.get("url") or ""
        md: str = (page.get("markdown") or "").strip()
        title: str = page.get("title") or ""
        if not url:
            continue
        slug = url.replace("https://", "").replace("http://", "").replace("/", "_")
        out_path = OUTPUT_DIR / f"{slug}.md"
        meta = {"url": url, "title": title}
        with out_path.open("w", encoding="utf-8") as f:
            f.write(f"---\n{json.dumps(meta)}\n---\n\n")
            f.write(md or "<!-- No content scraped -->")


async def main():
    seed = DOCS_DOMAIN
    urls = await fetch_sitemap_urls(seed, CRAWL_MAX_PAGES)
    print(f"Discovered {len(urls)} urls to fetch (limit={CRAWL_MAX_PAGES}).")

    pages = await render_and_extract(urls)
    print(f"Fetched pages: {len(pages)}")

    persist_pages(pages)
    print("Saved pages to data/raw.")


if __name__ == "__main__":
    asyncio.run(main())
