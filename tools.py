import os
import time
import random
import re
from typing import List, Dict, Optional, Tuple
from urllib.parse import quote_plus, urlparse
import requests
from bs4 import BeautifulSoup, FeatureNotFound
import pandas as pd
import base64

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
REQUEST_TIMEOUT = 10
MAX_RETRIES = 2

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


def _extract_linkedin_from_text(text: str) -> Optional[str]:
    """
    Extract LinkedIn profile URLs from text (bio, description, etc.)
    Returns the first valid LinkedIn URL found
    """
    if not text:
        return None
    
    patterns = [
        r'(https?://(?:www\.)?linkedin\.com/in/[\w\-]+)/?',
        r'(https?://(?:www\.)?linkedin\.com/company/[\w\-]+)/?',
        r'linkedin\.com/in/([\w\-]+)',
        r'www\.linkedin\.com/in/([\w\-]+)',
        r'linkedin\.com/in/([\w\-]+)/?',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                match = match[0]
            
            if match.startswith('http'):
                
                clean_url = match.split('?')[0].split('#')[0]
                return clean_url.rstrip('/')
            else:
                
                return f"https://www.linkedin.com/in/{match}"
    
    return None

def _extract_email_from_text(text: str) -> Optional[str]:
    """
    Extract email addresses from text using comprehensive patterns
    """
    if not text:
        return None
    
    email_patterns = [
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        r'email\s*[:\-]?\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})',
        r'contact\s*[:\-]?\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})',
        r'mail\s*[:\-]?\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})',
    ]
    
    for pattern in email_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                match = match[0]
            if '@' in match and '.' in match and len(match) > 5:
                return match.lower()
    
    return None


def _fetch_github_readme_content(username: str, headers: Dict) -> str:
    """
    Fetch README content from GitHub profile and repositories
    """
    all_content = ""
    readme_urls = [
        f"https://api.github.com/repos/{username}/{username}/readme",
        f"https://api.github.com/repos/{username}/README/readme",
        f"https://api.github.com/repos/{username}/.github/readme",
    ]
    
    for readme_url in readme_urls:
        try:
            r = _safe_get(readme_url, headers=headers)
            if r and r.status_code == 200:
                readme_data = r.json()
                content = readme_data.get("content", "")
                if content:
                    decoded_content = base64.b64decode(content).decode('utf-8')
                    all_content += f" {decoded_content}"
                    print(f"Found README content from {readme_url}")
        except Exception as e:
            print(f"Error: {e}")
            continue
    
    return all_content


def _fetch_github_repo_descriptions(username: str, headers: Dict, max_repos: int = 10) -> str:
    """
    Fetch descriptions from user's repositories
    """
    all_descriptions = ""
    
    repos_url = f"https://api.github.com/users/{username}/repos?per_page={max_repos}&sort=updated"
    try:
        r = _safe_get(repos_url, headers=headers)
        if r and r.status_code == 200:
            repos = r.json()
            for repo in repos:
                desc = repo.get("description", "")
                if desc:
                    all_descriptions += f" {desc}"
 
                repo_name = repo.get("name", "")
                if "linkedin" in repo_name.lower() or "portfolio" in repo_name.lower():
                    all_descriptions += f" {repo_name}"
    except Exception as e:
        print(f"Error fetching repo descriptions: {e}")
    
    return all_descriptions


def _scrape_github_profile_page(username: str) -> str:
    """
    Scrape the actual GitHub profile page for additional info not in API
    """
    profile_url = f"https://github.com/{username}"
    try:
        r = _safe_get(profile_url)
        if r and r.status_code == 200:
            soup = _soup_from_html(r.text)

            profile_content = ""

            bio_div = soup.find("div", {"class": "p-note"})
            if bio_div:
                profile_content += f" {bio_div.get_text(strip=True)}"
   
            status_div = soup.find("div", {"class": "user-status-message-wrapper"})
            if status_div:
                profile_content += f" {status_div.get_text(strip=True)}"
            
            website_link = soup.find("a", {"class": "Link--primary", "rel": "nofollow me"})
            if website_link and website_link.get("href"):
                profile_content += f" {website_link.get('href')}"
            
            return profile_content
    except Exception as e:
        print(f"Error scraping GitHub profile page: {e}")
    
    return ""

def fetch_github_profile(username_or_url: str, max_repos: int = 5) -> Dict:
    """
    Retrieve basic GitHub user info + enhanced LinkedIn/email detection.
    Now checks multiple sources aggressively.
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

    print(f"Enhanced GitHub scan for: {username}")
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
        "linkedin_from_github": None,
        "email_from_github": None,
    }
    all_text_sources = []
    
    basic_fields = [
        profile.get("bio", ""),
        profile.get("blog", ""),
        profile.get("company", ""),
        profile.get("location", ""),
        profile.get("name", ""),
    ]
    all_text_sources.extend(basic_fields)

    readme_content = _fetch_github_readme_content(username, headers)
    if readme_content:
        all_text_sources.append(readme_content)
        print(f"Scanned README files")
    
    repo_descriptions = _fetch_github_repo_descriptions(username, headers, max_repos=10)
    if repo_descriptions:
        all_text_sources.append(repo_descriptions)
        print(f"Scanned {max_repos} repo descriptions")
    
    profile_page_content = _scrape_github_profile_page(username)
    if profile_page_content:
        all_text_sources.append(profile_page_content)
        print(f"Scanned profile page")
   
    combined_text = " ".join([str(text) for text in all_text_sources if text])
   
    linkedin_url = None
    email_address = None
    
    if combined_text:
        print(f"Analyzing {len(combined_text)} characters of text...")

        linkedin_url = _extract_linkedin_from_text(combined_text)
        if linkedin_url:
            print(f"LinkedIn found: {linkedin_url}")
        else:
            print(f"No LinkedIn detected in GitHub data")

        email_address = _extract_email_from_text(combined_text)
        if email_address:
            print(f"Email found: {email_address}")
        else:
            print(f"No email detected in GitHub data")
    else:
        print(f"No text content found for analysis")

    info["linkedin_from_github"] = linkedin_url
    info["email_from_github"] = email_address

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

    findings = []
    if linkedin_url:
        findings.append("LinkedIn")
    if email_address:
        findings.append("Email")
    
    if findings:
        print(f"SUCCESS: Found {', '.join(findings)} in GitHub data")
    else:
        print(f"ℹ️ No contact info found in GitHub data for {username}")

    print(f"Found GitHub user: {info['name'] or username} with {len(info['top_repos'])} repos")
    return info

def build_professional_snapshot(name: str,
                                use_search: bool = True,
                                max_search_results: int = 3,
                                github_hint: Optional[str] = None,
                                offline_htmls: Optional[List[str]] = None) -> Tuple[Dict, pd.DataFrame]:
    """Enhanced OSINT snapshot builder with LinkedIn validation from GitHub."""
    print(f"\n=== Building professional snapshot for: {name} ===")
    results, linkedin_urls = [], []

    if use_search:
        linkedin_urls = search_linkedin_footprints(name, max_results=max_search_results)
        if not linkedin_urls:
            alt_links = fallback_people_search(name)
            results.append({"profile_url": alt_links, "error": "linkedin_not_found", "source": "people_search"})

    for url in linkedin_urls:
        try:
            res = scrape_linkedin_public(url)
            results.append(res)
            time.sleep(random.uniform(1.0, 2.0))
        except Exception as e:
            print(f"Error scraping {url}: {e}")

    github_profile = None
    gh_candidate = github_hint or find_github_by_name(name)
    if gh_candidate:
        gh_info = fetch_github_profile(gh_candidate)
        if gh_info and not gh_info.get("error"):
            github_profile = gh_info
        else:
            print(f"GitHub lookup failed: {gh_info.get('error')}")
    
    validated_linkedin_urls = linkedin_urls.copy()
    validated_results = results.copy()
    
    if github_profile and github_profile.get("linkedin_from_github"):
        github_linkedin = github_profile["linkedin_from_github"]
        print(f"Validating LinkedIn from GitHub: {github_linkedin}")
        
        if github_linkedin not in validated_linkedin_urls:
            print(f"GitHub LinkedIn is different from search results")
            print(f"Search found: {validated_linkedin_urls}")
            print(f"GitHub has: {github_linkedin}")
            
            print(f"   Testing GitHub LinkedIn URL...")
            test_result = scrape_linkedin_public(github_linkedin)
            
            if test_result and not test_result.get("error") and test_result.get("full_name"):
                validated_linkedin_urls = [github_linkedin]
                validated_results = [test_result]
                print(f"SUCCESS: Using GitHub-validated LinkedIn: {github_linkedin}")
                print(f"Profile name: {test_result.get('full_name')}")
            else:
                print(f"GitHub LinkedIn failed validation, keeping original results")
                if test_result and test_result.get("error"):
                    print(f"   Error: {test_result.get('error')}")
        else:
            print(f"GitHub LinkedIn matches our search results")

    snapshot = {
        "query_name": name,
        "linkedin_profiles_found": validated_linkedin_urls,
        "linkedin_raw": validated_results,
        "github": github_profile,
        "linkedin_validated": github_profile.get("linkedin_from_github") if github_profile else None,
        "email_from_github": github_profile.get("email_from_github") if github_profile else None,
        "validation_status": "github_validated" if (github_profile and github_profile.get("linkedin_from_github") and github_profile["linkedin_from_github"] in validated_linkedin_urls) else "search_based"
    }

    portfolio = find_portfolio_link([github_profile] + validated_results if github_profile else validated_results)
    snapshot["portfolio"] = portfolio

    df_rows = []
    for r in validated_results:
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
            "linkedin_from_github": github_profile.get("linkedin_from_github"),
            "email_from_github": github_profile.get("email_from_github"),
        })

    df = pd.DataFrame(df_rows or [], columns=["source", "profile_url", "full_name", "title", "job_title", "talks_about", "error", "linkedin_from_github", "email_from_github"])
    print(f"\n=== Snapshot complete: {len(df)} records ===\n")

    if github_profile and github_profile.get("linkedin_from_github"):
        if github_profile["linkedin_from_github"] in validated_linkedin_urls:
            print(f"SUCCESS: LinkedIn validated via GitHub - using authoritative source")
        else:
            print(f"WARNING: LinkedIn from GitHub couldn't be validated")
    
    return snapshot, df

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
    """Scrape a *public* LinkedIn profile for basic information."""
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

    exp_section = soup.find("section", {"id": "experience-section"}) or soup.find("section", string=lambda t: t and "Experience" in t)
    if exp_section:
        job_tag = exp_section.find("h3") or exp_section.find("span", {"class": "visually-hidden"})
        if job_tag:
            result["job_title"] = job_tag.get_text(strip=True)

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

    if not result["full_name"] and not result["title"]:
        result["error"] = "login_required_or_profile_not_found"

    print(f"Scraped profile: {result['full_name'] or 'Unknown'} - {result['title'] or 'No title'}")
    return result


def find_portfolio_link(sources: List[Dict]) -> Optional[str]:
    """
    Enhanced portfolio finder that also considers LinkedIn URLs from GitHub.
    """
    for s in sources:
        if isinstance(s, dict) and s.get("linkedin_from_github"):
            linkedin_url = s["linkedin_from_github"]
            print(f"Found LinkedIn from GitHub: {linkedin_url}")
    
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
                    if "linkedin.com" not in url: 
                        print(f"Found portfolio link: {url}")
                        return url

    print("No portfolio link found")
    return None


tools = [
    {"name": "search_linkedin_footprints", "description": "Searches public LinkedIn profiles by name using search engine footprints.", "func": search_linkedin_footprints},
    {"name": "scrape_linkedin_public", "description": "Extracts visible public data (name, title, job title, about) from a LinkedIn profile URL.", "func": scrape_linkedin_public},
    {"name": "fetch_github_profile", "description": "Fetches GitHub profile data and top repos using the public API, including LinkedIn detection from bio.", "func": fetch_github_profile},
    {"name": "find_portfolio_link", "description": "Analyzes LinkedIn + GitHub data and returns a personal website or portfolio link.", "func": find_portfolio_link},
    {"name": "find_github_by_name", "description": "Searches GitHub users by name via the public API.", "func": find_github_by_name},
    {"name": "fallback_people_search", "description": "Searches for other public profiles or resumes when LinkedIn fails.", "func": fallback_people_search},
    {"name": "build_professional_snapshot", "description": "Aggregates LinkedIn + GitHub + other public sources into a unified OSINT snapshot with LinkedIn validation.", "func": build_professional_snapshot},
]