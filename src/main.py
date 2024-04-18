import requests
import csv
import re
import os
import time
from time import sleep
from dotenv import load_dotenv
from datetime import datetime, timedelta
from parser import (
    parse_issue_link_from_body,
    parse_milestone,
    parse_project_complexity,
    parse_dates_and_format,
    parse_pricing,
)
from csv_writer import write_to_csv
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(filename='app.log', encoding='utf-8', level=logging.DEBUG, format='%(levelname)s:%(asctime)s %(message)s')

load_dotenv()

GH_PERSONAL_ACCESS_TOKEN = os.getenv("GH_PERSONAL_ACCESS_TOKEN")

headers = {
    "Authorization": GH_PERSONAL_ACCESS_TOKEN,
    "Accept": "application/vnd.github.v3+json",
}

repo_url = "https://api.github.com/repos/privacy-scaling-explorations/acceleration-program/issues"
output_csv_path = "issues.csv"


def get_issues():
    issues = []
    url = repo_url
    for status in ["open", "closed"]:
        page = 1
        while True:
            params = {
                "page": page,
                "per_page": 50,  # Reduce the per_page value
                "state": status,
            }
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                issues.extend(response.json())
                if len(response.json()) == 50:
                    page += 1
                else:
                    break
            elif response.status_code == 403 and "rate limit" in response.text.lower():
                # Rate limit exceeded, wait for the reset time
                reset_time = int(response.headers["X-RateLimit-Reset"])
                now = time.time()
                wait_time = reset_time - now + 10  # Add 10 seconds buffer
                print(f"Rate limit exceeded, waiting for {wait_time} seconds...")
                sleep(wait_time)
            else:
                break

    return issues


def process_task(title, issue):
    body = issue.get("body", "")
    issue_link = issue.get("html_url")
    state = issue.get("state")
    assignee_data = issue.get("assignee")
    assignee = assignee_data.get("login", "") if assignee_data else ""
    creator = issue.get("user", {}).get("login", "")
    labels = [label["name"].lower() for label in issue.get("labels", [])]

    project_complexity = parse_project_complexity(body)
    task_type = "Closed Task" if state == "closed" else "Task"
    logger.debug(f"{title}; {task_type}; {state}")
    if "wip" in labels:
        task_type = "Closed WIP" if state == "closed" else "WIP"
    elif "self proposed open task" in labels:
        task_type = (
            "Closed Self Proposed Open Task"
            if state == "closed"
            else "Self Proposed Open Task"
        )
    elif "umbrella task" in labels:
        task_type = "Closed Umbrella Task" if state == "closed" else "Umbrella Task"

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
    """ 
    get task and proposal separately
    """

    tasks = {}
    proposals = {}
    logger.info('preprocess_issue')
    
    # Task
    for issue in issues:
        title = issue.get("title", "").strip()
        if "pull_request" in issue:
            continue
        if title.lower().startswith(("proposal: ", "proposal ")):
            continue
        task = process_task(title, issue)
        tasks[task["task_link"]] = task
        tasks[task["task_link"]]["proposals"] = []

    # Proposal
    for issue in issues:
        title = issue.get("title", "").strip()
        if "pull_request" in issue:
            continue

        if title.lower().startswith(("proposal: ", "proposal ")):
            task_links = list(tasks.keys())
            proposal = process_proposal(title, issue, tasks)
            tasks[proposal["linked_tasks"]]["proposals"].append(proposal)
    
    return tasks


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


if __name__ == "__main__":
    issues = get_issues()
    issues.reverse()
    tasks = preprocess_issues(issues)
    write_to_csv(tasks, output_csv_path)
    print(f"Data written to {output_csv_path}")

    metrics = generate_metrics(tasks)
    print("Metrics:")
    for key, value in metrics.items():
        print(f"{key}: {value}")
