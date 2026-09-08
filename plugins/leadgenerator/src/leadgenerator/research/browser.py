"""Small Playwright collector used by both fast and visible research modes."""

from __future__ import annotations

import asyncio
from urllib.parse import urljoin

import html2text
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from undetected_playwright import Malenia

VISIBLE_PREVIEW_MS = 5_000


async def _collect_html(
    url: str,
    *,
    timeout: int,
    headless: bool,
) -> str:
    """Render one page and return its DOM after JavaScript execution."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless)
        try:
            context = await browser.new_context(ignore_https_errors=True)
            await Malenia.apply_stealth(context)
            page = await context.new_page()
            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=timeout * 1_000,
            )
            if response and response.status >= 400:
                raise RuntimeError(
                    f"La page a répondu avec le statut HTTP {response.status}."
                )
            html = await page.content()
            if not headless:
                await page.wait_for_timeout(VISIBLE_PREVIEW_MS)
            return html
        finally:
            await browser.close()


def collect_html(url: str, *, timeout: int = 60, headless: bool = True) -> str:
    """Synchronously collect a rendered page for the MCP tool."""
    return asyncio.run(_collect_html(url, timeout=timeout, headless=headless))


def html_to_markdown(html: str, base_url: str) -> str:
    """Remove non-evidence markup and convert the rendered page to Markdown."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    for tag in soup(["script", "style", "noscript", "template", "svg"]):
        tag.decompose()
    for link in soup.find_all("a", href=True):
        link["href"] = urljoin(base_url, link["href"])
    body = soup.body or soup

    converter = html2text.HTML2Text()
    converter.baseurl = base_url
    converter.body_width = 0
    converter.ignore_links = False
    converter.ignore_images = True
    title_markup = f"<h1>{title}</h1>" if title else ""
    return converter.handle(title_markup + str(body)).strip()
