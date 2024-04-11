import requests
import csv
import re
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from parser import (
    parse_issue_link_from_body,
    parse_milestone,
    parse_project_complexity,
    parse_dates_and_format,
    parse_pricing,
)

load_dotenv()

GH_PERSONAL_ACCESS_TOKEN = os.getenv("GH_PERSONAL_ACCESS_TOKEN")

headers = {
    "Authorization": GH_PERSONAL_ACCESS_TOKEN,
    "Accept": "application/vnd.github.v3+json",
}

repo_url = "https://api.github.com/repos/privacy-scaling-explorations/acceleration-program/issues"
output_csv_path = "issues.csv"

def get_issues(url):
    issues = []
    while url:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            issues.extend(response.json())
            # Check the "link" header for the next page's URL
            links = response.headers.get("link", "")
            next_page = next(
                (link for link in links.split(",") if 'rel="next"' in link), None
            )
            if next_page:
                url = next_page.split(";")[0].strip("<>")
            else:
                url = None
        else:
            url = None
    return issues


def process_task(title, issue):
    body = issue.get("body", "")
    issue_link = issue.get("html_url")
    assignee_data = issue.get("assignee")
    assignee = assignee_data.get("login", "") if assignee_data else ""
    creator = issue.get("user", {}).get("login", "")
    labels = [label["name"].lower() for label in issue.get("labels", [])]

    project_complexity = parse_project_complexity(body)
    task_type = "Task"
    if "wip" in labels:
        task_type = "WIP"
    elif "self proposed open task" in labels:
        task_type = "Self Proposed Open Task"
    elif "umbrella task" in labels:
        task_type = "Umbrella Task"

    # Pricing Per Hours
    pricing_per_hours = parse_pricing(project_complexity)

    return {
        "type": task_type,
        "title": title,
        "creator": creator,
        "assignee": assignee,
        "proposals": [],
        "project_complexity": project_complexity,
        "Pricing Per Hours": pricing_per_hours,
        "task_link": issue_link,
    }


def process_proposal(title, issue, tasks):
    body = issue.get("body", "")
    issue_link = issue.get("html_url")
    assignee_data = issue.get("assignee")
    assignee = assignee_data.get("login", "") if assignee_data else ""
    creator = issue.get("user", {}).get("login", "")
    linked_tasks = parse_issue_link_from_body(body, title)
    try:
        project_complexity = tasks[linked_tasks]["project_complexity"]
    except KeyError:
        raise ValueError(f"Error: {title} linked task not found.")
    working_hour_data = parse_milestone(body, title, project_complexity)
    start_end_date = parse_dates_and_format(body)

    return {
        "creator": creator,
        "assignee": assignee,
        "link": issue_link,
        "project_complexity": project_complexity,
        "linked_tasks": linked_tasks,
        "start_end_date": start_end_date,
        **working_hour_data,
    }


def preprocess_issues(issues):
    tasks = {}
    proposals = {}

    for issue in issues:
        if "pull_request" in issue:
            continue

        title = issue.get("title", "").strip()
        if title.lower().startswith(("proposal: ", "proposal ")):
            task_links = list(tasks.keys())
            proposal = process_proposal(title, issue, tasks)
            tasks[proposal["linked_tasks"]]["proposals"].append(proposal)
        else:
            task = process_task(title, issue)
            tasks[task["task_link"]] = task
            tasks[task["task_link"]]["proposals"] = []

    return tasks


def write_to_csv(tasks, filepath):
    with open(filepath, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, quoting=csv.QUOTE_ALL)
        header = [
            "Type",
            "Title",
            "Issue Creator",
            "Assignee (Grant Liaison or WIP Task Assignee)",
            "Task Link",
            "Project Complexity",
            "Linked Proposal",
            "Proposal Link",
            "Applicant",
            "Total Duration",
            "Total FTE",
            "Total Working Hours",
            "Formatted Equation",
            "Pricing Per Hours",
            "Cost Per Milestone",
            "Start/End Date",
            "Deliverable Repo Available",
        ]
        writer.writerow(header)

        for task_link, task_info in tasks.items():
            if task_info["proposals"]:
                for proposal in task_info["proposals"]:
                    proposal_type = (
                        "Task & Proposal"
                        if len(task_info["proposals"]) == 1
                        else "Task & Competing Proposal"
                    )
                    row = [
                        proposal_type,
                        task_info["title"],
                        task_info["creator"],
                        task_info["assignee"],
                        task_link,
                        task_info["project_complexity"],
                        "Yes",
                        proposal["link"],
                        proposal["creator"],
                        proposal["total_duration_value"],
                        proposal["total_fte"],
                        proposal["total_working_hours"],
                        proposal["formatted_equation"],
                        task_info["Pricing Per Hours"],
                        proposal["format_cost_per_milestone"],
                        proposal.get("start_end_date", "NONE"),
                        "NONE",
                    ]
                    writer.writerow(row)
            else:
                row = [
                    task_info["type"],
                    task_info["title"],
                    task_info["creator"],
                    task_info["assignee"],
                    task_link,
                    task_info["project_complexity"],
                    "No",
                    "NONE",
                    "NONE",
                    "NONE",
                    "NONE",
                    "NONE",
                    "NONE",
                    "NONE",
                    "NONE",
                    "NONE",
                    "NONE",
                ]
                writer.writerow(row)


def generate_metrics(tasks):
    metrics = {
        "WIP Tasks": 0,
        "Tasks Looking for Reviewer": 0,
        "Available Tasks": 0,
        "Proposals": 0,
        "Total Tasks": 0,
    }

    for task_link, task_info in tasks.items():
        metrics["Total Tasks"] += 1

        if task_info["type"] == "WIP":
            metrics["WIP Tasks"] += 1
        elif not task_info["proposals"]:
            metrics["Available Tasks"] += 1

        if not task_info["assignee"]:
            metrics["Tasks Looking for Reviewer"] += 1

        metrics["Proposals"] += len(task_info["proposals"])

    return metrics


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


if __name__ == "__main__":
    issues = get_issues(repo_url)
    issues.reverse()
    tasks = preprocess_issues(issues)
    write_to_csv(tasks, output_csv_path)
    print(f"Data written to {output_csv_path}")

    metrics = generate_metrics(tasks)
    print("Metrics:")
    for key, value in metrics.items():
        print(f"{key}: {value}")
