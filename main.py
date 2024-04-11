import requests
import csv
import re
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

GH_PERSONAL_ACCESS_TOKEN = os.getenv("GH_PERSONAL_ACCESS_TOKEN")
easy_cost = os.getenv("EASY")
medium_cost = os.getenv("MEDIUM")
hard_cost = os.getenv("HARD")

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
            next_page = next((link for link in links.split(",") if "rel=\"next\"" in link), None)
            if next_page:
                url = next_page.split(";")[0].strip("<>")
            else:
                url = None
        else:
            url = None
    return issues

def parse_issue_link_from_body(body, issue_title):
    # Adjust the regex if the link format in the body varies
    links = re.findall(
        r"https://github\.com/privacy-scaling-explorations/acceleration-program/issues/\d+",
        body,
    )
    if len(links) == 1:
        links = links[0]
    else:
        raise ValueError(
            f"Error: {issue_title} Multiple Issue link found in the issue body. Found {len(links)} links."
        )
    return links


def parse_milestone(body, issue_title, project_complexity):
    body = re.sub(r"\*\*|\r\n", "", body)

    # Regex patterns to find durations, FTEs, and hours
    total_duration_pattern = (
        r"Total Estimated Duration: (\d+) (hours|weeks|months|week|month|hour)"
    )
    total_fte_pattern = r"Full-time equivalent \(FTE\):[\s]*([\d.]+)"
    total_working_hours_pattern = r"Total Estimated Working Hours: (\d+) hours"

    milestone_duration_pattern = r"(?<!Total )Estimated Duration:[\s]*(\d+)[\s]*(hours|weeks|months|week|month|hour)"
    milestone_fte_pattern = r"FTE:[\s]*([\d.]+)"

    # Extract total duration and FTE
    total_duration_match = re.search(total_duration_pattern, body)
    total_fte_match = re.search(total_fte_pattern, body)
    total_working_hours_match = re.search(total_working_hours_pattern, body)

    # Default values in case not found
    total_duration_value = "error"
    total_duration_unit = "error"
    total_fte = "error" if not total_fte_match else total_fte_match.group(1)
    total_working_hours = (
        "error" if not total_working_hours_match else total_working_hours_match.group(1)
    )

    if total_duration_match:
        total_duration_value = int(total_duration_match.group(1))
        total_duration_unit = total_duration_match.group(2)

    # Find all milestones duration and FTEs
    try:
        milestones_duration = re.findall(milestone_duration_pattern, body)
        milestone_fte = re.findall(milestone_fte_pattern, body)
    except re.error:
        # Handle the regular expression error gracefully
        milestones_duration = []
        milestone_fte = []
        raise ValueError(
            f"{issue_title}, Error processing milestones in the issue body."
        )

    # Process each milestone
    formatted_equation_components = []
    format_cost_per_milestone_components = []
    total_working_hours_calculated = 0
    format_cost_per_milestone = []

    for (duration, unit), fte in zip(milestones_duration, milestone_fte):
        # Calculate milestone duration in hours
        duration = int(duration)
        if unit == "hours" or unit == "hour":
            milestone_hours = duration
        elif unit == "weeks" or unit == "week":
            milestone_hours = (
                duration * 5 * 8
            )  # Assuming 5 days per week and 8 hours per day
        elif unit == "months" or unit == "month":
            milestone_hours = (
                duration * 4 * 5 * 8
            )  # Assuming 4 weeks per month, 5 days per week, and 8 hours per day
        else:
            milestone_hours = "error"
        total_working_hours_calculated += milestone_hours * float(fte)

        # Calculate cost per milestone based on project complexity
        if project_complexity == "Easy":
            milestone_cost = duration * float(fte) * float(easy_cost)
        elif project_complexity == "Medium":
            milestone_cost = duration * float(fte) * float(medium_cost)
        elif project_complexity == "Hard":
            milestone_cost = duration * float(fte) * float(hard_cost)
        else:
            milestone_cost = "error"
        format_cost_per_milestone.append(milestone_cost)

        # Formatting the equation for each milestone
        if project_complexity == "Easy":
            formatted_equation_components.append(
                f"({duration} {unit} * {fte} FTE) * ${easy_cost}"
            )
        elif project_complexity == "Medium":
            formatted_equation_components.append(
                f"({duration} {unit} * {fte} FTE) * ${medium_cost}"
            )
        elif project_complexity == "Hard":
            formatted_equation_components.append(
                f"({duration} {unit} * {fte} FTE) * ${hard_cost}"
            )
        else:
            formatted_equation_components.append(
                f"({duration} {unit} * {fte} FTE) * $ERROR"
            )

    formatted_equation = (
        " + ".join(formatted_equation_components)
        if formatted_equation_components
        else "error"
    )
    for i, num in enumerate(format_cost_per_milestone_components, start=1):
        format_cost_per_milestone += f"m{i} = ${num:,}\n"

    # Check if the total working hours calculated is the same as the one provided in the issue body
    if total_working_hours_match and total_working_hours_calculated != int(
        total_working_hours_match.group(1)
    ):
        raise ValueError(
            f"Issue '{issue_title}': Total working hours calculated ({total_working_hours_calculated}) do not match the provided value ({total_working_hours_match.group(1)})."
        )

    return {
        "total_duration_value": total_duration_value,
        "total_duration_unit": total_duration_unit,
        "total_fte": total_fte,
        "formatted_equation": formatted_equation,
        "format_cost_per_milestone": format_cost_per_milestone,
        "total_working_hours": total_working_hours_calculated
        if total_working_hours_calculated
        else "error",
    }


def parse_project_complexity(body):
    # Regex patterns to find project complexity
    project_complexity_pattern = r"Project Complexity:\s*(\w+)"
    project_complexity_match = re.search(project_complexity_pattern, body)
    return project_complexity_match.group(1) if project_complexity_match else "error"


def parse_dates_and_format(body):
    # Patterns to find the starting date and estimated delivery date for each milestone
    starting_date_pattern = r"Starting Date: (\d{4}) (\w+) (\d+)[a-z]{2}"
    delivery_date_pattern = r"Estimated delivery date: (\d{4}) (\w+) (\d+)[a-z]{2}"
    milestone_pattern = r"\*\*Milestone \d+:"
    
    start_date_match = re.search(starting_date_pattern, body)
    delivery_date_match = re.search(delivery_date_pattern, body)
    milestones_count = len(re.findall(milestone_pattern, body))

    if not start_date_match or not delivery_date_match:
        return "Error: Cannot calculate because neither start nor delivery dates are given."
    
    try:
        start_date = datetime.strptime(f"{start_date_match.group(1)} {start_date_match.group(2)} {start_date_match.group(3)}", "%Y %B %d")
        delivery_date = datetime.strptime(f"{delivery_date_match.group(1)} {delivery_date_match.group(2)} {delivery_date_match.group(3)}", "%Y %B %d")
    except ValueError:
        return "Error: Incorrect date format."

    if milestones_count == 0:
        return "Error: No milestones found."

    # Formatting start date
    formatted_dates = f"Start: {start_date.strftime('%Y/%m/%d')}\n"
    
    # Calculate and format end dates for each milestone
    total_duration = (delivery_date - start_date).days
    milestone_duration = total_duration // milestones_count

    for i in range(1, milestones_count + 1):
        end_date = start_date + timedelta(days=milestone_duration * i)
        formatted_dates += f"m{i} end: {end_date.strftime('%Y/%m/%d')}\n" if i != milestones_count else f"m{i}=end:  {end_date.strftime('%Y/%m/%d')}\n"
    
    return formatted_dates[:-1]  # Remove the last newline




def process_task(title, issue):
    body = issue.get("body", "")
    issue_link = issue.get("html_url")
    assignee_data = issue.get("assignee")
    assignee = assignee_data.get("login", "") if assignee_data else ""
    creator = issue.get("user", {}).get("login", "")

    project_complexity = parse_project_complexity(body)
    task_type = "Task"
    if title.lower().startswith("[wip]"):
        task_type = "WIP Task"
    elif title.lower().startswith("self proposed open task"):
        task_type = "Self Proposed Task"

    # Pricing Per Hours
    if project_complexity == "Easy":
        pricing_per_hours = easy_cost
    elif project_complexity == "Medium":
        pricing_per_hours = medium_cost
    elif project_complexity == "Hard":
        pricing_per_hours = hard_cost
    else:
        pricing_per_hours = "error"

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
    except:
        raise ValueError(f"Error: {title} linked task not found.")
    working_hour_data = parse_milestone(body, title, project_complexity)

    return {
        "creator": creator,
        "assignee": assignee,
        "link": issue_link,
        "project_complexity": project_complexity,
        **working_hour_data,
        "linked_tasks": linked_tasks,
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
        writer.writerow(
            [
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
        )

        for task_link, task_info in tasks.items():
            if task_info["proposals"]:
                for proposal in task_info["proposals"]:
                    proposal_type = "Task & Proposal" if len(task_info["proposals"]) == 1 else "Task & Competing Proposal"
                    writer.writerow(
                        [
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
                        ]
                    )
            else:
                writer.writerow(
                    [
                        task_info["type"],
                        task_info["title"],
                        task_info["creator"],
                        task_info["assignee"],
                        task_link,
                        task_info["project_complexity"],
                        "No",
                        "",
                    ]
                )

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
            next_page = next((link for link in links.split(",") if "rel=\"next\"" in link), None)
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