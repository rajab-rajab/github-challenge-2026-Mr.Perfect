from tool_registry import tool_registry

import html
import re
import urllib.request
import webbrowser
from urllib.parse import quote, unquote, urlparse


class WebToolsMixin:
    def _clean_text(self, value):
        if value is None:
            return ""
        text = str(value)
        text = text.replace("&lt;", "<").replace("&gt;", ">")
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
        text = re.sub(r"```[a-zA-Z0-9_+-]*\n?", "", text)
        text = text.replace("```", "")
        return text.strip()

    def _open_top_results(self, urls):
        opened = 0
        for url in urls[:2]:
            if url:
                try:
                    webbrowser.open(url)
                    opened += 1
                except Exception:
                    pass
        return opened

    @tool_registry.register(
        name="web_search",
        description="Search the web for up-to-date information.",
        args_description="query",
    )
    def web_search(self, query: str) -> str:
        search_query = self._clean_text(query)
        if not search_query:
            return "Error: Empty search query."

        if hasattr(self, "tavily") and self.tavily:
            try:
                results = self.tavily.search(query=search_query, search_depth="advanced", max_results=4)
                if isinstance(results, dict) and "results" in results:
                    formatted = [f"Search Results for: {search_query}", "=" * 50]
                    urls = []
                    for i, item in enumerate(results["results"], 1):
                        title = self._clean_text(item.get("title", "No title"))
                        url = self._clean_text(item.get("url", ""))
                        content = self._clean_text(item.get("content", ""))[:180]
                        urls.append(url)
                        formatted.append(f"[{i}] {title}")
                        formatted.append(f"   URL: {url}")
                        formatted.append(f"   Summary: {content}...\n")
                    opened = self._open_top_results(urls)
                    if opened:
                        formatted.append(f"Opened the top {opened} result(s) in your browser.")
                    return "\n".join(formatted)
            except Exception:
                pass

        try:
            url = f"https://html.duckduckgo.com/html/?q={quote(search_query)}"
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=10) as response:
                page = response.read().decode("utf-8", errors="ignore")

            result_pattern = re.compile(
                r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                re.IGNORECASE | re.DOTALL,
            )
            snippet_pattern = re.compile(
                r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>|<div[^>]*class="result__snippet"[^>]*>(.*?)</div>',
                re.IGNORECASE | re.DOTALL,
            )

            results = result_pattern.findall(page)
            snippets = snippet_pattern.findall(page)
            output = [f"Search (Fallback): {search_query}", "=" * 50]
            urls = []

            for i, (link, title_html) in enumerate(results[:3], 1):
                link = html.unescape(link)
                if "/l/?kh=" in link and "uddg=" in link:
                    link = unquote(link.split("uddg=")[-1].split("&")[0])
                title = re.sub(r"<.*?>", "", html.unescape(title_html)).strip()
                snippet_html = snippets[i - 1][0] or snippets[i - 1][1] if i - 1 < len(snippets) else ""
                snippet = re.sub(r"<.*?>", "", html.unescape(snippet_html)).strip() or "No description available."
                urls.append(link)
                output.append(f"[{i}] {title}")
                output.append(f"   URL: {link}")
                output.append(f"   Summary: {snippet[:150]}...\n")

            opened = self._open_top_results(urls)
            if opened:
                output.append(f"Opened the top {opened} result(s) in your browser.")
            return "\n".join(output)
        except Exception as exc:
            return f"Error: All search providers failed. {exc}"

    @tool_registry.register(
        name="open_web",
        description="Open a specific URL in the browser.",
        args_description="url",
    )
    def open_web(self, url: str) -> str:
        try:
            target = self._clean_text(url).strip("'\"")
            if not target.startswith(("http://", "https://")):
                target = f"https://{target}" if "." in target else ""
            if not target:
                return "Error: Invalid URL."
            webbrowser.open(target, new=2)
            return f"Successfully opened: {target}"
        except Exception as exc:
            return f"Error opening URL: {exc}"

    @tool_registry.register(
        name="browser_browse",
        description="Navigate and read website content via Playwright.",
        args_description="url_or_query",
    )
    def browser_browse(self, url_or_query: str) -> str:
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            return f"Browser Error: Playwright is not available: {exc}"

        target = self._clean_text(url_or_query).strip("'\"")
        if not (target.startswith("http://") or target.startswith("https://")):
            if "." in target and " " not in target:
                target = "https://" + target
            else:
                target = f"https://www.google.com/search?q={quote(target)}"

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(user_agent="Mozilla/5.0")
                page = context.new_page()
                page.goto(target, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)
                title = page.title()
                page.evaluate(
                    'document.querySelectorAll("script, style, nav, footer, header").forEach(el => el.remove());'
                )
                text = re.sub(r"\n+", "\n", page.inner_text("body")).strip()
                browser.close()
                return f"Title: {title}\nURL: {target}\n\nContent:\n{text[:2500]}..."
        except Exception as exc:
            return f"Browser Error: {exc}"

    @tool_registry.register(
        name="get_weather",
        description="Get weather for a location.",
        args_description="location",
    )
    def get_weather(self, location: str) -> str:
        place = self._clean_text(location)
        if not place:
            return "Error: No location provided."

        if hasattr(self, "tavily") and self.tavily:
            try:
                results = self.tavily.search(
                    query=f"current weather in {place}",
                    search_depth="advanced",
                    max_results=1,
                )
                if results.get("results"):
                    item = results["results"][0]
                    return f"Weather for: {place}\n{self._clean_text(item.get('content', 'No data found.'))}"
            except Exception:
                pass

        try:
            request = urllib.request.Request(
                f"https://wttr.in/{quote(place)}?format=3",
                headers={"User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.read().decode("utf-8", errors="ignore").strip()
        except Exception as exc:
            return f"Weather Error: {exc}"

    @tool_registry.register(
        name="search_program",
        description="Search for official program download links.",
        args_description="program_name",
    )
    def search_program(self, program_name: str) -> str:
        name = self._clean_text(program_name)
        if not name:
            return "Error: No program name provided."

        try:
            if hasattr(self, "tavily") and self.tavily:
                results = self.tavily.search(query=f"{name} official download site", max_results=3)
                if results.get("results"):
                    formatted = [f"Search Results for: {name}", "=" * 30]
                    for item in results["results"]:
                        title = self._clean_text(item.get("title", "No title"))
                        url = self._clean_text(item.get("url", ""))
                        parsed = urlparse(url)
                        badge = "OFFICIAL" if "official" in title.lower() else "VERIFY"
                        formatted.append(f"{badge}: {title}")
                        formatted.append(f"URL: {parsed.geturl() or url}\n")
                    return "\n".join(formatted)
            return self.web_search(f"{name} official download")
        except Exception as exc:
            return f"Search Error: {exc}"
