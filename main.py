import requests
import os
from dotenv import load_dotenv

load_dotenv()

GH_PERSONAL_ACCESS_TOKEN = os.getenv('GH_PERSONAL_ACCESS_TOKEN')

headers = {
    "Authorization": GH_PERSONAL_ACCESS_TOKEN,
    "Accept": "application/vnd.github.v3+json"
}

# GitHub repository from which to retrieve issues
repo_url = "https://api.github.com/repos/privacy-scaling-explorations/acceleration-program/issues"

def get_issues(url):
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch issues, status code: {response.status_code}")
        return []

def print_issue_details(issues):
    for issue in issues:
        title = issue.get("title")
        tags = [label["name"] for label in issue.get("labels", [])]
        assignee_data = issue.get("assignee")
        assignee = assignee_data.get("login", "No assignee") if assignee_data else "No assignee"
        creator = issue.get("user", {}).get("login", "Unknown")

        print(f"Issue Title: {title}")
        print(f"Tags: {', '.join(tags) if tags else 'No tags'}")
        print(f"Assignee: {assignee}")
        print(f"Raised by: {creator}")
        print("----------------------------------------------------")


if __name__ == "__main__":
    issues = get_issues(repo_url)
    print_issue_details(issues)
