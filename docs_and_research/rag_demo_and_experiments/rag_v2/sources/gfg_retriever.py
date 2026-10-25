"""
=============================================================================
                    GEEKSFORGEEKS (GFG) RETRIEVER
=============================================================================
Discovers and extracts technical interview articles and problem explanations
from GeeksforGeeks (GFG) for the given keyword/topic.
=============================================================================
"""

import re
import base64
import urllib.parse
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup


class GFGRetriever:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def search_gfg_articles(self, topic: str, max_results: int = 3) -> List[Dict[str, str]]:
        """
        Searches for relevant GeeksforGeeks articles using multi-engine discovery:
        1. DuckDuckGo Lite search
        2. Bing search
        """
        articles = []

        # 1. Try DuckDuckGo Lite
        try:
            ddg_resp = requests.post(
                "https://lite.duckduckgo.com/lite/",
                data={"q": f"site:geeksforgeeks.org {topic}"},
                headers=self.headers,
                timeout=8
            )
            if ddg_resp.status_code == 200:
                soup = BeautifulSoup(ddg_resp.text, "html.parser")
                for a in soup.select("a.result-link"):
                    href = a.get("href", "")
                    title = a.get_text(strip=True)
                    if "geeksforgeeks.org" in href and not href.endswith("/category/") and "#" not in href:
                        if not any(art["url"] == href for art in articles):
                            articles.append({
                                "title": title,
                                "url": href,
                                "snippet": f"GeeksforGeeks article for {topic}"
                            })
                            if len(articles) >= max_results:
                                return articles
        except Exception as e:
            pass

        # 2. Try Bing
        if not articles:
            try:
                b_url = f"https://www.bing.com/search?q={urllib.parse.quote(f'site:geeksforgeeks.org {topic}')}"
                resp = requests.get(b_url, headers=self.headers, timeout=8)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for li in soup.select("li.b_algo"):
                        a = li.select_one("h2 a") or li.select_one("a")
                        if not a:
                            continue

                        href = a.get("href", "")
                        title = a.get_text(strip=True)

                        target_url = href
                        if "u=a1" in href:
                            try:
                                b64 = href.split("u=a1")[1].split("&")[0]
                                b64 += "=" * (-len(b64) % 4)
                                decoded = base64.b64decode(b64).decode("utf-8", errors="ignore")
                                if "http" in decoded:
                                    target_url = decoded
                            except Exception:
                                pass

                        if "geeksforgeeks.org" in target_url and not target_url.endswith("/category/") and "#" not in target_url:
                            if not any(art["url"] == target_url for art in articles):
                                articles.append({
                                    "title": title,
                                    "url": target_url,
                                    "snippet": f"GeeksforGeeks article for {topic}"
                                })
                                if len(articles) >= max_results:
                                    break
            except Exception as e:
                pass

        # 3. Fallback to direct URL guess if search did not yield items
        if not articles:
            slug = topic.strip().lower().replace(" ", "-")
            candidate_urls = [
                f"https://www.geeksforgeeks.org/dsa/{slug}/",
                f"https://www.geeksforgeeks.org/{slug}/",
                f"https://www.geeksforgeeks.org/{slug}-interview-questions/",
            ]
            for u in candidate_urls:
                articles.append({
                    "title": f"{topic} on GeeksforGeeks",
                    "url": u,
                    "snippet": f"GeeksforGeeks technical article for {topic}"
                })

        return articles

    def fetch_and_extract_article(self, article: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """
        Fetches the GeeksforGeeks article web page, strips boilerplate,
        and extracts high-signal technical text, explanations, and complexity notes.
        """
        url = article["url"]
        try:
            resp = requests.get(url, headers=self.headers, timeout=12)
            if resp.status_code != 200 or len(resp.text) < 500:
                return None

            soup = BeautifulSoup(resp.text, "html.parser")

            # Remove navigation, ads, headers, footers, scripts, comments
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript", "svg"]):
                tag.decompose()

            # Locate article body in GFG DOM structure
            article_body = soup.find("article") or soup.find("div", class_="article-content") or soup.find("div", class_="text") or soup.find("div", id="content") or soup.body

            if not article_body:
                return None

            # Extract headings, paragraphs, code notes, and list items
            elements = article_body.find_all(["h1", "h2", "h3", "h4", "p", "li", "pre", "table"])
            lines = []
            for elem in elements:
                text = elem.get_text(separator=" ", strip=True)
                if len(text) > 25:
                    lines.append(text)

            content = "\n\n".join(lines)
            if len(content) < 150:
                return None

            # Clean extra whitespaces
            content = re.sub(r"\n{3,}", "\n\n", content)

            return {
                "title": article["title"],
                "url": url,
                "content": content[:20000],  # cap at 20k chars per article
            }
        except Exception as e:
            print(f"  [WARN] Error fetching GFG article ({url}): {e}")
            return None

    def retrieve_and_chunk_gfg(self, topic: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[Dict[str, Any]]:
        """
        Searches GFG, fetches top article content, and returns structured text chunks.
        """
        articles = self.search_gfg_articles(topic, max_results=2)
        all_chunks = []

        for art in articles:
            print(f"  [INSPECT] GeeksforGeeks source: {art['url'][:70]}...")
            extracted = self.fetch_and_extract_article(art)
            if not extracted:
                continue

            text = extracted["content"]
            title = extracted["title"]
            url = extracted["url"]

            start = 0
            while start < len(text):
                end = min(start + chunk_size, len(text))
                chunk_text = text[start:end].strip()

                if len(chunk_text) >= 60:
                    all_chunks.append({
                        "source": f"GeeksforGeeks: {title} ({url})",
                        "source_type": "gfg",
                        "article_title": title,
                        "article_url": url,
                        "text": chunk_text,
                    })

                if end >= len(text):
                    break
                start += chunk_size - chunk_overlap

            if all_chunks:
                print(f"  [OK] Extracted {len(all_chunks)} chunks from GeeksforGeeks.")
                break  # Top high-quality article retrieved

        return all_chunks
