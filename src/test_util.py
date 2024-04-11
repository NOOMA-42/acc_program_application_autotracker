import time
import requests


def test_get_issues_title(url):
    issues_titles = []
    while url:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            issues = response.json()
            for issue in issues:
                issues_titles.append(issue.get("title", ""))
            # Check the "link" header for the next page's URL
            links = response.headers.get("link", "")
            next_page = next(
                (link for link in links.split(",") if 'rel="next"' in link), None
            )
            if next_page:
                url = next_page.split(";")[0].strip("<>")
            else:
                url = None
        elif response.status_code == 429:  # Too Many Requests
            # Get the rate limit reset time from the headers
            reset_time = float(response.headers["X-RateLimit-Reset"])
            current_time = time.time()
            delay = reset_time - current_time + 1  # Add an extra second for safety
            print(f"Rate limit reached. Waiting {delay} seconds before retrying...")
            time.sleep(delay)
        else:
            url = None
    return issues_titles
