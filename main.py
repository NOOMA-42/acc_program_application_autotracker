import requests
import csv
import re
import os
from dotenv import load_dotenv

load_dotenv()

GH_PERSONAL_ACCESS_TOKEN = os.getenv('GH_PERSONAL_ACCESS_TOKEN')

headers = {
    "Authorization": GH_PERSONAL_ACCESS_TOKEN,
    "Accept": "application/vnd.github.v3+json"
}

repo_url = "https://api.github.com/repos/privacy-scaling-explorations/acceleration-program/issues"
output_csv_path = "issues.csv"

def get_issues(url):
    response = requests.get(url, headers=headers)
    return response.json() if response.status_code == 200 else []

def parse_issue_link_from_body(body):
    # Adjust the regex if the link format in the body varies
    links = re.findall(r"https://github\.com/privacy-scaling-explorations/acceleration-program/issues/\d+", body)
    return links

def preprocess_issues(issues):
    proposals = {}
    tasks = {}
    for issue in issues:
        if "pull_request" in issue:
            continue

        title = issue.get("title", "")
        body = issue.get("body", "")
        issue_link = issue.get("html_url")
        assignee_data = issue.get("assignee")
        assignee = assignee_data.get("login", "") if assignee_data else ""
        creator = issue.get("user", {}).get("login", "")

        if title.lower().startswith(("proposal: ", "proposal ")):
            linked_tasks = parse_issue_link_from_body(body)
            for task_link in linked_tasks:
                if task_link not in proposals:
                    proposals[task_link] = []
                proposals[task_link].append({"creator": creator, "assignee": assignee, "link": issue_link})
        else:
            tasks[issue_link] = {"creator": creator, "assignee": assignee, "proposals": proposals.get(issue_link, [])}

    return tasks

def write_to_csv(tasks, filepath):
    with open(filepath, mode="w", newline='', encoding='utf-8') as file:
        writer = csv.writer(file, quoting=csv.QUOTE_ALL)
        writer.writerow(["Type", "Issue Creator", "Assignee (Grant Liaison)", "Task Link", "Has Proposal?", "Proposal Link"])

        for task_link, task_info in tasks.items():
            for proposal in task_info["proposals"]:
                writer.writerow(["Task & Proposal", task_info["creator"], task_info["assignee"], task_link, "Yes", proposal["link"]])

            if not task_info["proposals"]:
                writer.writerow(["Task", task_info["creator"], task_info["assignee"], task_link, "No", ""])

if __name__ == "__main__":
    issues = get_issues(repo_url)
    tasks = preprocess_issues(issues)
    write_to_csv(tasks, output_csv_path)
    print(f"Data written to {output_csv_path}")