import urllib.parse
import logging
from playwright.async_api import async_playwright, Page

logger = logging.getLogger("vaib")

class BrowserManager:
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(BrowserManager, cls).__new__(cls, *args, **kwargs)
            cls._instance.playwright = None
            cls._instance.browser = None
            cls._instance.context = None
            cls._instance.page = None
        return cls._instance

    async def get_page(self) -> Page:
        """Lazily initialize Playwright and return the current page."""
        if self.page and not self.page.is_closed():
            return self.page
            
        try:
            if not self.playwright:
                self.playwright = await async_playwright().start()
            if not self.browser:
                # Launch Chromium headlessly
                self.browser = await self.playwright.chromium.launch(headless=True)
            if not self.context:
                self.context = await self.browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            self.page = await self.context.new_page()
            self.page.set_default_timeout(15000)
            return self.page
        except Exception as e:
            logger.error(f"Failed to initialize Playwright browser: {e}")
            raise e

    async def close(self):
        """Close browser resources."""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.error(f"Error closing browser: {e}")
        finally:
            self.page = None
            self.context = None
            self.browser = None
            self.playwright = None

# Global manager instance
browser_manager = BrowserManager()

async def browser_search(query: str) -> str:
    """
    Search the web for information using a search engine query and return top results.
    Use this tool whenever the user asks to search, lookup, or query the internet.
    
    Args:
        query: The search query or terms to look up.
    """
    try:
        page = await browser_manager.get_page()
        escaped_query = urllib.parse.quote(query)
        url = f"https://html.duckduckgo.com/html/?q={escaped_query}"
        logger.info(f"Searching DuckDuckGo for: '{query}'")
        await page.goto(url, wait_until="domcontentloaded")
        
        # Parse results using Playwright locators
        results = []
        result_elements = await page.locator(".result").all()
        
        for i, el in enumerate(result_elements[:5]):
            try:
                title_el = el.locator(".result__a")
                snippet_el = el.locator(".result__snippet")
                
                title = await title_el.inner_text()
                link = await title_el.get_attribute("href")
                
                # Clean up redirections
                if link and "uddg=" in link:
                    parsed = urllib.parse.urlparse(link)
                    q_params = urllib.parse.parse_qs(parsed.query)
                    if "uddg" in q_params:
                        link = q_params["uddg"][0]
                        
                snippet = await snippet_el.inner_text()
                results.append(f"{i+1}. {title}\n   Link: {link}\n   Snippet: {snippet}")
            except Exception as inner_err:
                logger.warning(f"Error parsing single search result item: {inner_err}")
                
        if not results:
            body_text = await page.locator("body").inner_text()
            return f"DuckDuckGo search page loaded, but no results found. Content: {body_text[:1500]}"
            
        return "\n\n".join(results)
    except Exception as e:
        logger.error(f"Failed to run browser search: {e}")
        return f"Failed to perform search: {str(e)}"

async def browser_navigate(url: str) -> str:
    """
    Open or navigate to a website URL or domain (e.g., github.com, youtube.com, google.com).
    Use this tool whenever the user wants to access a website or web page.
    
    Args:
        url: The web address, URL, or domain to navigate to.
    """
    try:
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
            
        page = await browser_manager.get_page()
        logger.info(f"Navigating browser to: {url}")
        await page.goto(url, wait_until="domcontentloaded")
        
        title = await page.title()
        content = await page.locator("body").inner_text()
        return f"URL: {url}\nTitle: {title}\n\nContent:\n{content[:2500]}"
    except Exception as e:
        logger.error(f"Failed to navigate browser to {url}: {e}")
        return f"Failed to navigate to {url}: {str(e)}"

async def browser_click(selector: str) -> str:
    """
    Click a DOM element identified by CSS selector on the active browser page.
    """
    try:
        page = await browser_manager.get_page()
        logger.info(f"Clicking selector: {selector}")
        await page.click(selector)
        title = await page.title()
        return f"Clicked '{selector}' successfully. Current page title: '{title}'"
    except Exception as e:
        logger.error(f"Failed to click selector {selector}: {e}")
        return f"Failed to click '{selector}': {str(e)}"

async def browser_input(selector: str, text: str) -> str:
    """
    Type text into an input field CSS selector on the active browser page.
    """
    try:
        page = await browser_manager.get_page()
        logger.info(f"Typing into selector {selector}")
        await page.fill(selector, text)
        return f"Successfully typed text into '{selector}'."
    except Exception as e:
        logger.error(f"Failed to type into selector {selector}: {e}")
        return f"Failed to type into '{selector}': {str(e)}"
