import requests
import os
import time
from time import sleep
from src.parser import (
    parse_issue_meta_data,
    parse_milestone,
    parse_project_complexity,
    parse_dates_and_format,
    parse_pricing,
)
from src.csv_writer import write_to_csv
from src.logger import logger

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
                logger.warn(f"Rate limit exceeded, waiting for {wait_time} seconds...")
                sleep(wait_time)
            else:
                break

    # Reverse the list to get the oldest issue first, so that proposal can always link to the task. Otherwise, the task might not be created yet.    
    return issues[::-1]

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
    logger.debug(f"Processing proposal: {title}, {issue.get('html_url')}")
    body, issue_link, assignee, creator, linked_tasks, project_complexity = parse_issue_meta_data(title, issue, tasks)
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
    
    logger.info('preprocess_issue')
    tasks = process_tasks(issues)
    tasks = process_proposals(issues, tasks)
    
    return tasks

def process_proposals(issues, tasks):
    """  
    dependent: rely on the task to be created first
    TODO: refactor to decouple the task creation and proposal creation
    """
    for issue in issues:
        title = issue.get("title", "").strip()
        if "pull_request" in issue:
            continue

        if title.lower().startswith(("proposal: ", "proposal ")):
            proposal = process_proposal(title, issue, tasks)
            tasks[proposal["linked_tasks"]]["proposals"].append(proposal)
    return tasks

def process_tasks(issues):
    tasks = {}
    for issue in issues:
        title = issue.get("title", "").strip()
        if "pull_request" in issue:
            continue
        if title.lower().startswith(("proposal: ", "proposal ")):
            continue
        task = process_task(title, issue)
        tasks[task["task_link"]] = task
        tasks[task["task_link"]]["proposals"] = []
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


def run():
    issues = get_issues()
    tasks = preprocess_issues(issues)
    write_to_csv(tasks, output_csv_path)
    print(f"Data written to {output_csv_path}")

    metrics = generate_metrics(tasks)
    print("Metrics:")
    for key, value in metrics.items():
        print(f"{key}: {value}")
