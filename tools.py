import os
import time
import random
import re
from typing import List, Dict, Optional, Tuple
from urllib.parse import quote_plus, urlparse
import requests
from bs4 import BeautifulSoup, FeatureNotFound
import pandas as pd

# ================================================================
# CONFIGURATION
# ================================================================

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
REQUEST_TIMEOUT = 10
MAX_RETRIES = 2

# ================================================================
# INTERNAL UTILITIES
# ================================================================

def _safe_get(url: str, params=None, headers=None, timeout=REQUEST_TIMEOUT) -> Optional[requests.Response]:
    """Simple GET with retries and polite jitter."""
    headers = headers or DEFAULT_HEADERS
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=timeout)
            return r
        except requests.RequestException as e:
            print(f"Request attempt {attempt} failed: {e}")
            if attempt == MAX_RETRIES:
                return None
            time.sleep(0.5 * attempt + random.random())
    return None


def _soup_from_html(html: str) -> BeautifulSoup:
    try:
        return BeautifulSoup(html, "lxml")
    except FeatureNotFound:
        return BeautifulSoup(html, "html.parser")


def _is_captcha_page_text(text: str) -> bool:
    text_l = text.lower()
    triggers = ["captcha", "are you human", "unusual traffic", "bot detection", "verify you are"]
    return any(t in text_l for t in triggers)


# ================================================================
# SEARCH FUNCTIONS
# ================================================================

def search_linkedin_footprints(name: str, max_results: int = 3) -> List[str]:
    """Return a list of public LinkedIn profile URLs for a given name."""
    print(f"Searching LinkedIn profiles for: {name}")
    name_slug = name.lower().replace(" ", "-").replace(".", "")
    possible_urls = [
        f"https://www.linkedin.com/in/{name_slug}/",
        f"https://www.linkedin.com/in/{name.lower().replace(' ', '')}/",
    ]

    query = quote_plus(f'site:linkedin.com/in "{name}"')
    ddg_url = f"https://html.duckduckgo.com/html/?q={query}"

    r = _safe_get(ddg_url)
    if not r:
        print("DuckDuckGo search failed, trying Bing...")
        return _bing_search_for_linkedin(name, max_results) or possible_urls[:1]

    if _is_captcha_page_text(r.text):
        print("CAPTCHA detected on DuckDuckGo, using direct URL fallback.")
        return possible_urls[:1]

    soup = _soup_from_html(r.text)
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "linkedin.com/in/" in href:
            clean = href.split("?")[0].split("#")[0]
            if clean not in links and clean.startswith("http"):
                links.append(clean)
        if len(links) >= max_results:
            break

    if links:
        print(f"Found {len(links)} LinkedIn profiles via DuckDuckGo")
        return links

    print("No results from DuckDuckGo, trying Bing...")
    bing_results = _bing_search_for_linkedin(name, max_results)
    if not bing_results:
        print(f"No results from search engines, trying direct URL: {possible_urls[0]}")
        return possible_urls[:1]
    return bing_results


def _bing_search_for_linkedin(name: str, max_results: int = 3) -> List[str]:
    query = quote_plus(f'site:linkedin.com/in "{name}"')
    url = f"https://www.bing.com/search?q={query}"
    r = _safe_get(url)
    if not r or _is_captcha_page_text(r.text):
        print("Bing blocked or CAPTCHA encountered.")
        return []

    soup = _soup_from_html(r.text)
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "linkedin.com/in/" in href:
            clean = href.split("?")[0].split("#")[0]
            if clean not in links and clean.startswith("http"):
                links.append(clean)
        if len(links) >= max_results:
            break

    print(f"Found {len(links)} LinkedIn profiles via Bing")
    return links


def fallback_people_search(name: str) -> List[str]:
    """Generic fallback search for public profiles, resumes, or portfolios."""
    print(f"No LinkedIn found — running fallback people search for: {name}")
    query = quote_plus(f'"{name}" (portfolio OR resume OR CV OR developer OR engineer OR designer)')
    url = f"https://html.duckduckgo.com/html/?q={query}"
    r = _safe_get(url)
    if not r or _is_captcha_page_text(r.text):
        print("Fallback search blocked or CAPTCHA triggered.")
        return []
    soup = _soup_from_html(r.text)
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("http") and "duckduckgo.com" not in href:
            links.append(href)
        if len(links) >= 5:
            break
    print(f"Found {len(links)} alternate public links.")
    return links


# ================================================================
# GITHUB INTELLIGENCE
# ================================================================

def find_github_by_name(name: str) -> Optional[str]:
    """Search GitHub for a user by name (first match)."""
    print(f"Searching GitHub users by name: {name}")
    token = os.getenv("GITHUB_TOKEN")
    headers = DEFAULT_HEADERS.copy()
    if token:
        headers["Authorization"] = f"token {token}"
    url = f"https://api.github.com/search/users?q={quote_plus(name)}"
    r = _safe_get(url, headers=headers)
    if not r or r.status_code != 200:
        print(f"GitHub search failed with status {r.status_code if r else 'no_response'}")
        return None
    data = r.json().get("items", [])
    if not data:
        print("No GitHub users found by name.")
        return None
    username = data[0]["login"]
    print(f"Found GitHub username candidate: {username}")
    return username

def scrape_linkedin_public(profile_url: str, html_override: Optional[str] = None) -> Dict:
    """
    Scrape a *public* LinkedIn profile for the fields:
    - full_name
    - title (headline)
    - job_title (first listed experience if visible)
    - talks_about (About summary; often hidden when logged out)
    Behavior:
      - If html_override is provided, parse that string instead of fetching the URL (offline demo).
      - If CAPTCHA is detected, returns {"error":"captcha"} so caller can handle fallback.
    """
    result = {
        "profile_url": profile_url,
        "full_name": None,
        "title": None,
        "job_title": None,
        "talks_about": None,
        "error": None,
    }

    if html_override:
        print(f"Using HTML override for {profile_url}")
        html = html_override
    else:
        print(f"Scraping LinkedIn profile: {profile_url}")
        try:
            r = _safe_get(profile_url)
            if not r:
                result["error"] = "request_failed"
                return result
        except Exception as e:
            result["error"] = f"request_failed: {e}"
            return result

        if _is_captcha_page_text(r.text):
            result["error"] = "captcha"
            print("CAPTCHA detected on LinkedIn profile")
            return result
        html = r.text

    soup = _soup_from_html(html)

    # Try multiple selectors for name
    name_selectors = [
        ("div", {"class": "pv-text-details__left-panel"}),
        ("div", {"class": "top-card-layout__entity-info"}),
        ("div", {"class": "pv-top-card"}),
        ("section", {"class": "top-card-layout"}),
    ]
    
    for tag, attrs in name_selectors:
        name_div = soup.find(tag, attrs)
        if name_div:
            h1 = name_div.find("h1")
            if h1:
                result["full_name"] = h1.get_text(strip=True)
                break

    # Try multiple selectors for title/headline
    if not result["title"]:
        title_selectors = [
            ("div", {"class": "text-body-medium"}),
            ("div", {"class": "pv-top-card--list-bullet"}),
            ("h2", {}),
        ]
        for tag, attrs in title_selectors:
            title_tag = soup.find(tag, attrs)
            if title_tag and title_tag.get_text(strip=True):
                result["title"] = title_tag.get_text(strip=True)
                break

    # Try to extract from meta tags (more reliable for public profiles)
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        content = og_title.get("content")
        if not result["full_name"] and " - " in content:
            result["full_name"] = content.split(" - ")[0].strip()
        if not result["title"] and " - " in content:
            parts = content.split(" - ")
            if len(parts) > 1:
                result["title"] = parts[1].strip()

    og_description = soup.find("meta", property="og:description")
    if og_description and og_description.get("content"):
        result["talks_about"] = og_description.get("content").strip()

    # Experience section
    exp_section = soup.find("section", {"id": "experience-section"}) or soup.find("section", string=lambda t: t and "Experience" in t)
    if exp_section:
        job_tag = exp_section.find("h3") or exp_section.find("span", {"class": "visually-hidden"})
        if job_tag:
            result["job_title"] = job_tag.get_text(strip=True)

    # Final fallback: extract from title tag
    if not result["full_name"]:
        t = soup.find("title")
        if t:
            text = t.get_text(strip=True)
            if " - " in text:
                result["full_name"] = text.split(" - ")[0].strip()
            elif "|" in text:
                result["full_name"] = text.split("|")[0].strip()
            else:
                result["full_name"] = text.strip()

    # Mark as login required if we got nothing useful
    if not result["full_name"] and not result["title"]:
        result["error"] = "login_required_or_profile_not_found"

    print(f"Scraped profile: {result['full_name'] or 'Unknown'} - {result['title'] or 'No title'}")
    return result


def fetch_github_profile(username_or_url: str, max_repos: int = 5) -> Dict:
    """
    Retrieve basic GitHub user info + top public repos.
    username_or_url can be a username or full URL like 'https://github.com/octocat'.
    Uses GitHub API (free, rate-limited). If GITHUB_TOKEN env var present, will use it.
    """
    token = os.getenv("GITHUB_TOKEN")
    headers = DEFAULT_HEADERS.copy()
    if token:
        headers["Authorization"] = f"token {token}"

    if "github.com/" in username_or_url:
        parts = urlparse(username_or_url).path.strip("/").split("/")
        username = parts[0] if parts else username_or_url
    else:
        username = username_or_url

    print(f"Fetching GitHub profile for: {username}")
    base = "https://api.github.com"
    user_url = f"{base}/users/{username}"
    
    try:
        r = _safe_get(user_url, headers=headers)
        if not r or r.status_code != 200:
            print(f"GitHub user not found: {username}")
            return {"error": f"github_status_{r.status_code if r else 'no_response'}"}
    except Exception as e:
        return {"error": f"github_request_failed: {e}"}

    try:
        profile = r.json()
    except Exception as e:
        return {"error": f"github_json_parse_error: {e}"}

    info = {
        "github_username": username,
        "name": profile.get("name"),
        "bio": profile.get("bio"),
        "blog": profile.get("blog"),
        "company": profile.get("company"),
        "location": profile.get("location"),
        "public_repos": profile.get("public_repos"),
        "followers": profile.get("followers"),
        "following": profile.get("following"),
        "profile_url": profile.get("html_url"),
    }

    repos_url = f"{base}/users/{username}/repos?per_page=100&type=owner&sort=updated"
    try:
        r2 = _safe_get(repos_url, headers=headers)
        repos = r2.json() if r2 and r2.status_code == 200 else []
    except Exception as e:
        print(f"Failed to fetch repos: {e}")
        repos = []

    repos_sorted = sorted(repos, key=lambda x: x.get("stargazers_count", 0), reverse=True) if isinstance(repos, list) else []
    info["top_repos"] = [
        {"name": r.get("name"), "html_url": r.get("html_url"), "description": r.get("description"),
         "language": r.get("language"), "stars": r.get("stargazers_count")}
        for r in repos_sorted[:min(max_repos, len(repos_sorted))]
    ]

    print(f"Found GitHub user: {info['name'] or username} with {len(info['top_repos'])} repos")
    return info


def find_portfolio_link(sources: List[Dict]) -> Optional[str]:
    """
    Given a list of dicts (e.g., LinkedIn scrape results and GitHub profile dict),
    return the best candidate for portfolio/personal site.
    Looks at GitHub 'blog' field, LinkedIn 'talks_about' and 'title' fields for URLs.
    """
    for s in sources:
        if isinstance(s, dict) and s.get("blog"):
            blog = s["blog"].strip()
            if blog and blog != "null" and blog.startswith("http"):
                print(f"Found portfolio link: {blog}")
                return blog

    url_re = re.compile(r"https?://[^\s]+")
    for s in sources:
        if not isinstance(s, dict):
            continue
        for k in ("talks_about", "title", "bio", "full_name"):
            v = s.get(k)
            if v:
                m = url_re.search(str(v))
                if m:
                    url = m.group(0).rstrip(".,;")
                    print(f"Found portfolio link: {url}")
                    return url

    print("No portfolio link found")
    return None

def build_professional_snapshot(name: str,
                                use_search: bool = True,
                                max_search_results: int = 3,
                                github_hint: Optional[str] = None,
                                offline_htmls: Optional[List[str]] = None) -> Tuple[Dict, pd.DataFrame]:
    """Enhanced OSINT snapshot builder with fallbacks."""
    print(f"\n=== Building professional snapshot for: {name} ===")
    results, linkedin_urls = [], []

    if use_search:
        linkedin_urls = search_linkedin_footprints(name, max_results=max_search_results)
        if not linkedin_urls:
            # fallback to people search
            alt_links = fallback_people_search(name)
            results.append({"profile_url": alt_links, "error": "linkedin_not_found", "source": "people_search"})

    # scrape linkedin
    for url in linkedin_urls:
        try:
            res = scrape_linkedin_public(url)
            results.append(res)
            time.sleep(random.uniform(1.0, 2.0))
        except Exception as e:
            print(f"Error scraping {url}: {e}")

    # GitHub lookup
    github_profile = None
    gh_candidate = github_hint or find_github_by_name(name)
    if gh_candidate:
        gh_info = fetch_github_profile(gh_candidate)
        if gh_info and not gh_info.get("error"):
            github_profile = gh_info
        else:
            print(f"GitHub lookup failed: {gh_info.get('error')}")

    snapshot = {
        "query_name": name,
        "linkedin_profiles_found": [r.get("profile_url") for r in results if isinstance(r, dict)],
        "linkedin_raw": results,
        "github": github_profile,
    }

    portfolio = find_portfolio_link([github_profile] + results if github_profile else results)
    snapshot["portfolio"] = portfolio

    df_rows = []
    for r in results:
        if not isinstance(r, dict):
            continue
        df_rows.append({
            "source": r.get("source", "linkedin_public"),
            "profile_url": r.get("profile_url"),
            "full_name": r.get("full_name"),
            "title": r.get("title"),
            "job_title": r.get("job_title"),
            "talks_about": r.get("talks_about"),
            "error": r.get("error"),
        })

    if github_profile:
        df_rows.append({
            "source": "github",
            "profile_url": github_profile.get("profile_url"),
            "full_name": github_profile.get("name"),
            "title": None,
            "job_title": None,
            "talks_about": github_profile.get("bio"),
            "error": github_profile.get("error"),
        })

    df = pd.DataFrame(df_rows or [], columns=["source", "profile_url", "full_name", "title", "job_title", "talks_about", "error"])
    print(f"\n=== Snapshot complete: {len(df)} records ===\n")
    return snapshot, df


tools = [
    {"name": "search_linkedin_footprints", "description": "Searches public LinkedIn profiles by name using search engine footprints.", "func": search_linkedin_footprints},
    {"name": "scrape_linkedin_public", "description": "Extracts visible public data (name, title, job title, about) from a LinkedIn profile URL.", "func": scrape_linkedin_public},
    {"name": "fetch_github_profile", "description": "Fetches GitHub profile data and top repos using the public API.", "func": fetch_github_profile},
    {"name": "find_portfolio_link", "description": "Analyzes LinkedIn + GitHub data and returns a personal website or portfolio link.", "func": find_portfolio_link},
    {"name": "find_github_by_name", "description": "Searches GitHub users by name via the public API.", "func": find_github_by_name},
    {"name": "fallback_people_search", "description": "Searches for other public profiles or resumes when LinkedIn fails.", "func": fallback_people_search},
    {"name": "build_professional_snapshot", "description": "Aggregates LinkedIn + GitHub + other public sources into a unified OSINT snapshot.", "func": build_professional_snapshot},
]
