import os
import time
import random
import re
from typing import List, Dict, Optional, Tuple
from urllib.parse import quote_plus, urlparse
import requests
from bs4 import BeautifulSoup, FeatureNotFound
import pandas as pd

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


def multi_source_linkedin_search(name: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Multi-source search for LinkedIn profiles using various OSINT techniques.
    """
    print(f"Starting multi-source LinkedIn search for: {name}")
    results = []
    seen_urls = set()
    
    search_engines = [
        ("DuckDuckGo", f"https://html.duckduckgo.com/html/?q={quote_plus(f'site:linkedin.com/in {name}')}"),
        ("Bing", f"https://www.bing.com/search?q={quote_plus(f'site:linkedin.com/in {name}')}"),
        ("Google", f"https://www.google.com/search?q={quote_plus(f'site:linkedin.com/in {name}')}"),
    ]
    
    for engine_name, url in search_engines:
        print(f"Trying {engine_name}")
        r = _safe_get(url)
        if not r or _is_captcha_page_text(r.text):
            print(f"{engine_name} blocked or CAPTCHA")
            continue
        
        soup = _soup_from_html(r.text)
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "linkedin.com/in/" in href:
                clean_url = href.split("?")[0].split("#")[0]
                if clean_url.startswith("http") and clean_url not in seen_urls:
                    seen_urls.add(clean_url)
                    results.append({
                        "url": clean_url,
                        "source": engine_name,
                        "title": a.get_text(strip=True)[:100]
                    })
                    print(f"Found: {clean_url}")
            
            if len(results) >= max_results:
                break
        
        if len(results) >= max_results:
            break
        
        time.sleep(random.uniform(0.5, 1.5))
    
    if not results:
        name_slug = name.lower().replace(" ", "-").replace(".", "")
        direct_urls = [
            f"https://www.linkedin.com/in/{name_slug}/",
            f"https://www.linkedin.com/in/{name.lower().replace(' ', '')}/",
        ]
        print(f"No results found, trying direct URLs")
        for url in direct_urls:
            results.append({"url": url, "source": "Direct", "title": "Direct URL attempt"})
    
    print(f"Total LinkedIn profiles found: {len(results)}")
    return results


def multi_source_github_search(name: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Multi-source search for GitHub profiles using various OSINT techniques.
    """
    print(f"Starting multi-source GitHub search for: {name}")
    results = []
    seen_urls = set()
    
    search_engines = [
        ("DuckDuckGo", f"https://html.duckduckgo.com/html/?q={quote_plus(f'site:github.com {name}')}"),
        ("Bing", f"https://www.bing.com/search?q={quote_plus(f'site:github.com {name}')}"),
        ("Google", f"https://www.google.com/search?q={quote_plus(f'site:github.com {name}')}"),
    ]
    
    for engine_name, url in search_engines:
        print(f"Trying {engine_name}")
        r = _safe_get(url)
        if not r or _is_captcha_page_text(r.text):
            print(f"{engine_name} blocked or CAPTCHA")
            continue
        
        soup = _soup_from_html(r.text)
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "github.com/" in href and "github.com/search" not in href:
                clean_url = href.split("?")[0].split("#")[0]
                if clean_url.startswith("http") and clean_url not in seen_urls:
                    parts = urlparse(clean_url).path.strip("/").split("/")
                    if len(parts) >= 1 and parts[0] and not parts[0].startswith("topics"):
                        seen_urls.add(clean_url)
                        results.append({
                            "url": clean_url,
                            "username": parts[0],
                            "source": engine_name,
                            "title": a.get_text(strip=True)[:100]
                        })
                        print(f"Found: {clean_url}")
            
            if len(results) >= max_results:
                break
        
        if len(results) >= max_results:
            break
        
        time.sleep(random.uniform(0.5, 1.5))
    
    print(f"Total GitHub profiles found: {len(results)}")
    return results


def github_api_search(name: str) -> Optional[str]:
    """
    Search GitHub using official API with token support.
    """
    print(f"Searching GitHub API for: {name}")
    token = os.getenv("GITHUB_TOKEN")
    headers = DEFAULT_HEADERS.copy()
    if token:
        headers["Authorization"] = f"token {token}"
        print("Using GitHub token for authentication")
    
    url = f"https://api.github.com/search/users?q={quote_plus(name)}"
    r = _safe_get(url, headers=headers)
    if not r or r.status_code != 200:
        print(f"GitHub API search failed: {r.status_code if r else 'no_response'}")
        return None
    
    data = r.json().get("items", [])
    if data:
        username = data[0]["login"]
        print(f"GitHub API found: {username}")
        return username
    return None


def scrape_linkedin_public(profile_url: str) -> Dict:
    """
    Scrape public LinkedIn profile data.
    """
    result = {
        "profile_url": profile_url,
        "full_name": None,
        "title": None,
        "job_title": None,
        "talks_about": None,
        "error": None,
    }

    print(f"Scraping LinkedIn profile: {profile_url}")
    r = _safe_get(profile_url)
    if not r:
        result["error"] = "request_failed"
        return result

    if _is_captcha_page_text(r.text):
        result["error"] = "captcha"
        print("CAPTCHA detected on LinkedIn profile")
        return result

    soup = _soup_from_html(r.text)

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


def extract_linkedin_from_github(github_data: Dict) -> Optional[str]:
    """
    Extract LinkedIn URL from GitHub profile bio or blog field.
    """
    if not github_data or github_data.get("error"):
        return None
    
    linkedin_pattern = re.compile(r'https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+/?', re.IGNORECASE)
    
    fields_to_check = [
        github_data.get("bio", ""),
        github_data.get("blog", ""),
        github_data.get("company", ""),
    ]
    
    for field in fields_to_check:
        if field:
            match = linkedin_pattern.search(str(field))
            if match:
                linkedin_url = match.group(0).rstrip("/") + "/"
                print(f"Found LinkedIn URL in GitHub profile: {linkedin_url}")
                return linkedin_url
    
    return None


def fetch_github_profile(username_or_url: str, max_repos: int = 5) -> Dict:
    """
    Fetch GitHub profile using official API with token support.
    """
    token = os.getenv("GITHUB_TOKEN")
    headers = DEFAULT_HEADERS.copy()
    if token:
        headers["Authorization"] = f"token {token}"
        print("Using GitHub token for authentication")

    if "github.com/" in username_or_url:
        parts = urlparse(username_or_url).path.strip("/").split("/")
        username = parts[0] if parts else username_or_url
    else:
        username = username_or_url

    print(f"Fetching GitHub profile for: {username}")
    base = "https://api.github.com"
    user_url = f"{base}/users/{username}"
    
    r = _safe_get(user_url, headers=headers)
    if not r or r.status_code != 200:
        print(f"GitHub user not found: {username}")
        return {"error": f"github_status_{r.status_code if r else 'no_response'}"}

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
    r2 = _safe_get(repos_url, headers=headers)
    repos = r2.json() if r2 and r2.status_code == 200 else []

    repos_sorted = sorted(repos, key=lambda x: x.get("stargazers_count", 0), reverse=True) if isinstance(repos, list) else []
    info["top_repos"] = [
        {"name": r.get("name"), "html_url": r.get("html_url"), "description": r.get("description"),
         "language": r.get("language"), "stars": r.get("stargazers_count")}
        for r in repos_sorted[:min(max_repos, len(repos_sorted))]
    ]

    linkedin_url = extract_linkedin_from_github(info)
    if linkedin_url:
        info["linkedin_from_github"] = linkedin_url

    print(f"Found GitHub user: {info['name'] or username} with {len(info['top_repos'])} repos")
    return info


def find_portfolio_link(sources: List[Dict]) -> Optional[str]:
    """
    Extract portfolio/website from LinkedIn and GitHub data.
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


def generate_report(snapshot: Dict, output_file: str = None) -> str:
    """
    Generate comprehensive text report from OSINT data.
    """
    if not output_file:
        target_name = snapshot.get('query_name', 'unknown').replace(" ", "_").lower()
        output_file = f"report/{target_name}_report.txt"
    
    os.makedirs("report", exist_ok=True)
    
    print(f"Generating report: {output_file}")
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("HARVEY OSINT PROFESSIONAL SNAPSHOT REPORT\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"Target: {snapshot.get('query_name', 'Unknown')}\n")
        f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        github = snapshot.get("github")
        if github and not github.get("error") and github.get("linkedin_from_github"):
            f.write("-" * 80 + "\n")
            f.write("LINKEDIN FROM GITHUB BIO\n")
            f.write("-" * 80 + "\n")
            f.write(f"LinkedIn URL found in GitHub profile: {github.get('linkedin_from_github')}\n")
            f.write("This profile has been automatically scraped and included below.\n\n")
        
        f.write("-" * 80 + "\n")
        f.write("LINKEDIN PROFILES\n")
        f.write("-" * 80 + "\n")
        linkedin_searches = snapshot.get("linkedin_searches", [])
        if linkedin_searches:
            for i, result in enumerate(linkedin_searches, 1):
                f.write(f"{i}. {result.get('url', 'N/A')}\n")
                f.write(f"   Source: {result.get('source', 'N/A')}\n\n")
        else:
            f.write("No LinkedIn profiles found via search\n")
        f.write("\n")
        
        linkedin_raw = snapshot.get("linkedin_raw", [])
        if linkedin_raw:
            f.write("-" * 80 + "\n")
            f.write("LINKEDIN DATA\n")
            f.write("-" * 80 + "\n")
            for profile in linkedin_raw:
                if isinstance(profile, dict):
                    source_note = " (from GitHub bio)" if profile.get("source") == "github_bio" else ""
                    f.write(f"Profile URL: {profile.get('profile_url', 'N/A')}{source_note}\n")
                    f.write(f"Name: {profile.get('full_name', 'N/A')}\n")
                    f.write(f"Title: {profile.get('title', 'N/A')}\n")
                    f.write(f"Job Title: {profile.get('job_title', 'N/A')}\n")
                    f.write(f"About: {profile.get('talks_about', 'N/A')}\n")
                    if profile.get('error'):
                        f.write(f"Error: {profile['error']}\n")
                    f.write("\n")
        
        github_searches = snapshot.get("github_searches", [])
        if github_searches:
            f.write("-" * 80 + "\n")
            f.write("GITHUB PROFILES FOUND\n")
            f.write("-" * 80 + "\n")
            for i, result in enumerate(github_searches, 1):
                f.write(f"{i}. {result.get('url', 'N/A')}\n")
                f.write(f"   Username: {result.get('username', 'N/A')}\n")
                f.write(f"   Source: {result.get('source', 'N/A')}\n\n")
        
        if github and not github.get("error"):
            f.write("-" * 80 + "\n")
            f.write("GITHUB PROFILE DATA\n")
            f.write("-" * 80 + "\n")
            f.write(f"Username: {github.get('github_username', 'N/A')}\n")
            f.write(f"Name: {github.get('name', 'N/A')}\n")
            f.write(f"Bio: {github.get('bio', 'N/A')}\n")
            f.write(f"Company: {github.get('company', 'N/A')}\n")
            f.write(f"Location: {github.get('location', 'N/A')}\n")
            f.write(f"Profile URL: {github.get('profile_url', 'N/A')}\n")
            f.write(f"Public Repos: {github.get('public_repos', 0)}\n")
            f.write(f"Followers: {github.get('followers', 0)}\n")
            f.write(f"Following: {github.get('following', 0)}\n")
            if github.get('linkedin_from_github'):
                f.write(f"LinkedIn in bio: {github.get('linkedin_from_github')}\n")
            f.write("\n")
            
            top_repos = github.get("top_repos", [])
            if top_repos:
                f.write("Top Repositories:\n")
                for i, repo in enumerate(top_repos, 1):
                    f.write(f"  {i}. {repo.get('name', 'N/A')}\n")
                    f.write(f"     URL: {repo.get('html_url', 'N/A')}\n")
                    f.write(f"     Description: {repo.get('description', 'N/A')}\n")
                    f.write(f"     Language: {repo.get('language', 'N/A')}\n")
                    f.write(f"     Stars: {repo.get('stars', 0)}\n\n")
        else:
            f.write("-" * 80 + "\n")
            f.write("GITHUB PROFILE DATA\n")
            f.write("-" * 80 + "\n")
            f.write("No GitHub profile found or error occurred\n\n")
        
        portfolio = snapshot.get("portfolio")
        f.write("-" * 80 + "\n")
        f.write("PORTFOLIO/WEBSITE\n")
        f.write("-" * 80 + "\n")
        if portfolio:
            f.write(f"{portfolio}\n")
        else:
            f.write("No portfolio or personal website found\n")
        f.write("\n")
        
        f.write("=" * 80 + "\n")
        f.write("END OF REPORT\n")
        f.write("=" * 80 + "\n")
    
    print(f"Report saved to {output_file}")
    return output_file


def compare_profiles(name1: str, name2: str) -> Dict:
    """
    Compare two professional profiles and provide strength/weakness analysis.
    """
    print(f"\n=== Comparing profiles: {name1} vs {name2} ===\n")
    
    print(f"Building snapshot for {name1}")
    snapshot1, _ = build_professional_snapshot(name1)
    
    print(f"Building snapshot for {name2}")
    snapshot2, _ = build_professional_snapshot(name2)
    
    comparison = {
        "person1": name1,
        "person2": name2,
        "snapshot1": snapshot1,
        "snapshot2": snapshot2,
        "analysis": {}
    }
    
    def get_profile_metrics(snapshot):
        github = snapshot.get("github", {})
        linkedin_raw = snapshot.get("linkedin_raw", [])
        
        linkedin_present = len(linkedin_raw) > 0 and any(
            not d.get("error") for d in linkedin_raw if isinstance(d, dict)
        )
        
        return {
            "github_present": github and not github.get("error"),
            "github_repos": github.get("public_repos", 0) if github else 0,
            "github_followers": github.get("followers", 0) if github else 0,
            "github_stars": sum(r.get("stars", 0) for r in github.get("top_repos", [])) if github else 0,
            "linkedin_present": linkedin_present,
            "has_portfolio": bool(snapshot.get("portfolio")),
        }
    
    metrics1 = get_profile_metrics(snapshot1)
    metrics2 = get_profile_metrics(snapshot2)
    
    analysis = {
        "github_comparison": {
            "winner": None,
            "details": ""
        },
        "linkedin_comparison": {
            "winner": None,
            "details": ""
        },
        "overall_strengths": {
            name1: [],
            name2: []
        },
        "overall_weaknesses": {
            name1: [],
            name2: []
        }
    }
    
    if metrics1["github_present"] and metrics2["github_present"]:
        if metrics1["github_repos"] > metrics2["github_repos"]:
            analysis["github_comparison"]["winner"] = name1
            analysis["github_comparison"]["details"] = f"{name1} has more repositories ({metrics1['github_repos']} vs {metrics2['github_repos']})"
        elif metrics2["github_repos"] > metrics1["github_repos"]:
            analysis["github_comparison"]["winner"] = name2
            analysis["github_comparison"]["details"] = f"{name2} has more repositories ({metrics2['github_repos']} vs {metrics1['github_repos']})"
        else:
            analysis["github_comparison"]["details"] = "Both have similar number of repositories"
        
        if metrics1["github_stars"] > metrics2["github_stars"]:
            analysis["overall_strengths"][name1].append(f"Higher GitHub impact ({metrics1['github_stars']} stars vs {metrics2['github_stars']})")
        elif metrics2["github_stars"] > metrics1["github_stars"]:
            analysis["overall_strengths"][name2].append(f"Higher GitHub impact ({metrics2['github_stars']} stars vs {metrics1['github_stars']})")
    elif metrics1["github_present"]:
        analysis["github_comparison"]["winner"] = name1
        analysis["github_comparison"]["details"] = f"{name1} has GitHub presence, {name2} does not"
        analysis["overall_weaknesses"][name2].append("No GitHub profile found")
    elif metrics2["github_present"]:
        analysis["github_comparison"]["winner"] = name2
        analysis["github_comparison"]["details"] = f"{name2} has GitHub presence, {name1} does not"
        analysis["overall_weaknesses"][name1].append("No GitHub profile found")
    else:
        analysis["github_comparison"]["details"] = "Neither has a GitHub profile"
    
    if metrics1["linkedin_present"] and not metrics2["linkedin_present"]:
        analysis["linkedin_comparison"]["winner"] = name1
        analysis["linkedin_comparison"]["details"] = f"{name1} has LinkedIn presence, {name2} does not"
        analysis["overall_weaknesses"][name2].append("No LinkedIn profile found")
    elif metrics2["linkedin_present"] and not metrics1["linkedin_present"]:
        analysis["linkedin_comparison"]["winner"] = name2
        analysis["linkedin_comparison"]["details"] = f"{name2} has LinkedIn presence, {name1} does not"
        analysis["overall_weaknesses"][name1].append("No LinkedIn profile found")
    elif metrics1["linkedin_present"] and metrics2["linkedin_present"]:
        analysis["linkedin_comparison"]["details"] = "Both have LinkedIn presence"
    else:
        analysis["linkedin_comparison"]["details"] = "Neither has accessible LinkedIn profile"
    
    if metrics1["has_portfolio"]:
        analysis["overall_strengths"][name1].append("Has portfolio/personal website")
    else:
        analysis["overall_weaknesses"][name1].append("No portfolio/personal website found")
    
    if metrics2["has_portfolio"]:
        analysis["overall_strengths"][name2].append("Has portfolio/personal website")
    else:
        analysis["overall_weaknesses"][name2].append("No portfolio/personal website found")
    
    comparison["analysis"] = analysis
    
    report_file = generate_comparison_report(comparison)
    comparison["report_file"] = report_file
    
    print(f"\n=== Comparison complete ===\n")
    return comparison


def generate_comparison_report(comparison: Dict, output_file: str = None) -> str:
    """
    Generate comparison report between two profiles.
    """
    if not output_file:
        name1 = comparison.get('person1', 'person1').replace(" ", "_").lower()
        name2 = comparison.get('person2', 'person2').replace(" ", "_").lower()
        output_file = f"report/{name1}_vs_{name2}_comparison.txt"
    
    os.makedirs("report", exist_ok=True)
    
    print(f"Generating comparison report: {output_file}")
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("HARVEY PROFILE COMPARISON REPORT\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"Person 1: {comparison['person1']}\n")
        f.write(f"Person 2: {comparison['person2']}\n")
        f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        analysis = comparison.get("analysis", {})
        
        f.write("-" * 80 + "\n")
        f.write("GITHUB COMPARISON\n")
        f.write("-" * 80 + "\n")
        github_comp = analysis.get("github_comparison", {})
        if github_comp.get("winner"):
            f.write(f"Winner: {github_comp['winner']}\n")
        f.write(f"{github_comp.get('details', 'No data')}\n\n")
        
        f.write("-" * 80 + "\n")
        f.write("LINKEDIN COMPARISON\n")
        f.write("-" * 80 + "\n")
        linkedin_comp = analysis.get("linkedin_comparison", {})
        if linkedin_comp.get("winner"):
            f.write(f"Winner: {linkedin_comp['winner']}\n")
        f.write(f"{linkedin_comp.get('details', 'No data')}\n\n")
        
        f.write("-" * 80 + "\n")
        f.write("STRENGTHS & WEAKNESSES\n")
        f.write("-" * 80 + "\n")
        
        strengths = analysis.get("overall_strengths", {})
        weaknesses = analysis.get("overall_weaknesses", {})
        
        f.write(f"\n{comparison['person1']}:\n")
        f.write("  Strengths:\n")
        for s in strengths.get(comparison['person1'], []):
            f.write(f"    - {s}\n")
        if not strengths.get(comparison['person1']):
            f.write("    - None identified\n")
        
        f.write("  Weaknesses:\n")
        for w in weaknesses.get(comparison['person1'], []):
            f.write(f"    - {w}\n")
        if not weaknesses.get(comparison['person1']):
            f.write("    - None identified\n")
        
        f.write(f"\n{comparison['person2']}:\n")
        f.write("  Strengths:\n")
        for s in strengths.get(comparison['person2'], []):
            f.write(f"    - {s}\n")
        if not strengths.get(comparison['person2']):
            f.write("    - None identified\n")
        
        f.write("  Weaknesses:\n")
        for w in weaknesses.get(comparison['person2'], []):
            f.write(f"    - {w}\n")
        if not weaknesses.get(comparison['person2']):
            f.write("    - None identified\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("DETAILED SNAPSHOTS\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"See individual reports for detailed data:\n")
        f.write(f"- {comparison['snapshot1'].get('report_file', 'N/A')}\n")
        f.write(f"- {comparison['snapshot2'].get('report_file', 'N/A')}\n\n")
        
        f.write("=" * 80 + "\n")
        f.write("END OF COMPARISON REPORT\n")
        f.write("=" * 80 + "\n")
    
    print(f"Comparison report saved to {output_file}")
    return output_file

def build_professional_snapshot(name: str) -> Tuple[Dict, pd.DataFrame]:
    """
    Build comprehensive OSINT snapshot using multi-source search approach.
    """
    print(f"\n=== Building professional snapshot for: {name} ===\n")
    
    linkedin_searches = multi_source_linkedin_search(name, max_results=5)
    
    linkedin_data = []
    for result in linkedin_searches[:3]:
        try:
            scraped = scrape_linkedin_public(result["url"])
            linkedin_data.append(scraped)
            time.sleep(random.uniform(1.0, 2.0))
        except Exception as e:
            print(f"Error scraping {result['url']}: {e}")
    
    github_searches = multi_source_github_search(name, max_results=5)
    
    github_profile = None
    if github_searches:
        username = github_searches[0].get("username")
        if username:
            github_profile = fetch_github_profile(username)
    
    if not github_profile or github_profile.get("error"):
        api_username = github_api_search(name)
        if api_username:
            github_profile = fetch_github_profile(api_username)
    
    if github_profile and not github_profile.get("error"):
        linkedin_from_github = github_profile.get("linkedin_from_github")
        if linkedin_from_github:
            print(f"Found LinkedIn URL in GitHub profile, scraping: {linkedin_from_github}")
            already_scraped = any(
                linkedin_from_github == d.get("profile_url") 
                for d in linkedin_data if isinstance(d, dict)
            )
            
            if not already_scraped:
                try:
                    scraped = scrape_linkedin_public(linkedin_from_github)
                    scraped["source"] = "github_bio"
                    linkedin_data.insert(0, scraped)
                    time.sleep(random.uniform(1.0, 2.0))
                except Exception as e:
                    print(f"Error scraping LinkedIn from GitHub bio: {e}")
    
    snapshot = {
        "query_name": name,
        "linkedin_searches": linkedin_searches,
        "linkedin_raw": linkedin_data,
        "github_searches": github_searches,
        "github": github_profile,
    }
    
    portfolio = find_portfolio_link([github_profile] + linkedin_data if github_profile else linkedin_data)
    snapshot["portfolio"] = portfolio
    
    df_rows = []
    for profile in linkedin_data:
        if isinstance(profile, dict):
            df_rows.append({
                "source": profile.get("source", "linkedin"),
                "profile_url": profile.get("profile_url"),
                "full_name": profile.get("full_name"),
                "title": profile.get("title"),
                "job_title": profile.get("job_title"),
                "talks_about": profile.get("talks_about"),
                "error": profile.get("error"),
            })
    
    if github_profile and not github_profile.get("error"):
        df_rows.append({
            "source": "github",
            "profile_url": github_profile.get("profile_url"),
            "full_name": github_profile.get("name"),
            "title": None,
            "job_title": None,
            "talks_about": github_profile.get("bio"),
            "error": None,
        })
    
    df = pd.DataFrame(df_rows, columns=["source", "profile_url", "full_name", "title", "job_title", "talks_about", "error"])
    
    report_file = generate_report(snapshot)
    snapshot["report_file"] = report_file
    
    print(f"\n=== Snapshot complete: {len(df)} records ===\n")
    return snapshot, df


tools = [
    {"name": "multi_source_linkedin_search", "description": "Multi-source OSINT search for LinkedIn profiles across multiple search engines.", "func": multi_source_linkedin_search},
    {"name": "multi_source_github_search", "description": "Multi-source OSINT search for GitHub profiles across multiple search engines.", "func": multi_source_github_search},
    {"name": "github_api_search", "description": "Search GitHub using official API with token support.", "func": github_api_search},
    {"name": "extract_linkedin_from_github", "description": "Extract LinkedIn URL from GitHub profile bio or blog field.", "func": extract_linkedin_from_github},
    {"name": "scrape_linkedin_public", "description": "Scrape public LinkedIn profile data.", "func": scrape_linkedin_public},
    {"name": "fetch_github_profile", "description": "Fetch GitHub profile using official API with token support.", "func": fetch_github_profile},
    {"name": "find_portfolio_link", "description": "Extract portfolio/website from LinkedIn and GitHub data.", "func": find_portfolio_link},
    {"name": "generate_report", "description": "Generate comprehensive text report from OSINT data.", "func": generate_report},
    {"name": "compare_profiles", "description": "Compare two profiles and generate strength/weakness analysis.", "func": compare_profiles},
    {"name": "generate_comparison_report", "description": "Generate comparison report between two profiles.", "func": generate_comparison_report},
    {"name": "build_professional_snapshot", "description": "Build comprehensive OSINT snapshot using multi-source search approach.", "func": build_professional_snapshot},
]