import re
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from src.logger import logger

load_dotenv()

easy_cost = os.getenv("EASY")
medium_cost = os.getenv("MEDIUM")
hard_cost = os.getenv("HARD")


def parse_issue_link_from_body(body, issue_title):
    """  
    A parser for proposal
    """

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

def parse_issue_meta_data(title, issue, tasks):
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
    return body,issue_link,assignee,creator,linked_tasks,project_complexity

def parse_milestone(body, issue_title, project_complexity):
    body = clean_body(body)
    
    total_duration_value, total_duration_unit = extract_total_duration(body)
    total_fte = extract_total_fte(body)
    total_working_hours = extract_total_working_hours(body)

    milestones_duration, milestone_fte = extract_milestone_data(body, issue_title)

    formatted_equation_components, format_cost_per_milestone_components, total_working_hours_calculated = process_milestones(
        milestones_duration, milestone_fte, project_complexity
    )

    formatted_equation = format_equation(formatted_equation_components)
    format_cost_per_milestone = format_cost_components(format_cost_per_milestone_components)

    validate_total_working_hours(total_working_hours, total_working_hours_calculated, issue_title)

    total_cost = calculate_total_cost(format_cost_per_milestone_components)

    return {
        "total_duration_value": total_duration_value,
        "total_duration_unit": total_duration_unit,
        "total_fte": total_fte,
        "formatted_equation": formatted_equation,
        "format_cost_per_milestone": format_cost_per_milestone,
        "total_cost": total_cost,
        "total_working_hours": total_working_hours_calculated if total_working_hours_calculated else "error",
    }

def clean_body(body):
    return re.sub(r"\*\*|\r\n", "", body)

def extract_total_duration(body):
    pattern = r"Total Estimated Duration: (\d+) (hours|weeks|months|week|month|hour)"
    match = re.search(pattern, body)
    if match:
        return int(match.group(1)), match.group(2)
    return "error", "error"

def extract_total_fte(body):
    pattern = r"Full-time equivalent \(FTE\):[\s]*([\d.]+)"
    match = re.search(pattern, body)
    return "error" if not match else match.group(1)

def extract_total_working_hours(body):
    pattern = r"Total Estimated Working Hours: (\d+) (hours|hrs)"
    match = re.search(pattern, body)
    return "error" if not match else match.group(1)

def extract_milestone_data(body, issue_title):
    try:
        duration_pattern = r"(?<!Total )Estimated Duration:[\s]*(\d+(?:\.\d+)?)[\s]*(hours|weeks|months|week|month|hour|days|day)"
        fte_pattern = r"FTE:[\s]*([\d.]+)"
        milestones_duration = re.findall(duration_pattern, body)
        milestone_fte = re.findall(fte_pattern, body)
        return milestones_duration, milestone_fte
    except re.error:
        logger.error(f"{issue_title}, Error processing milestones in the issue body.")

def process_milestones(milestones_duration, milestone_fte, project_complexity):
    formatted_equation_components = []
    format_cost_per_milestone_components = []
    total_working_hours_calculated = 0

    cost_factors = {
        "Easy": float(easy_cost),
        "Medium": float(medium_cost),
        "Hard": float(hard_cost),
    }

    for (duration, unit), fte in zip(milestones_duration, milestone_fte):
        milestone_hours = calculate_milestone_hours(duration, unit)
        total_working_hours_calculated += milestone_hours * float(fte)

        milestone_cost = milestone_hours * float(fte) * cost_factors.get(project_complexity, "error")
        format_cost_per_milestone_components.append(milestone_cost)

        formatted_equation_components.append(
            f"({duration} {unit} * {fte} FTE) * ${cost_factors.get(project_complexity, 'ERROR')}"
        )

    return formatted_equation_components, format_cost_per_milestone_components, total_working_hours_calculated

def calculate_milestone_hours(duration, unit):
    duration = float(duration)
    if unit in ["hours", "hour"]:
        return duration
    elif unit in ["weeks", "week"]:
        return duration * 5 * 8  # Assuming 5 days per week and 8 hours per day
    elif unit in ["months", "month"]:
        return duration * 4 * 5 * 8  # Assuming 4 weeks per month, 5 days per week, and 8 hours per day
    elif unit in ["days", "day"]:
        return duration * 8
    return "error"

def format_equation(components):
    return " + ".join(components) if components else "error"

def format_cost_components(components):
    return "".join(f"m{i+1} = ${num}; " for i, num in enumerate(components))

def validate_total_working_hours(provided_hours, calculated_hours, issue_title):
    if provided_hours != "error" and calculated_hours != int(provided_hours):
        raise ValueError(
            f"Issue '{issue_title}': Total working hours calculated ({calculated_hours}) do not match the provided value ({provided_hours})."
        )

def calculate_total_cost(cost_components):
    total_cost = 0
    for cost in cost_components:
        if cost != "error":
            total_cost += cost
    return total_cost


def parse_project_complexity(body):
    # Regex patterns to find project complexity
    project_complexity_pattern = r"Project Complexity:\s*(\w+)"
    project_complexity_match = re.search(project_complexity_pattern, body)
    return project_complexity_match.group(1) if project_complexity_match else "error"


def parse_dates_and_format(body):
    body = re.sub(r"\*\*|\\r\\n", "", body)  # Remove unnecessary patterns

    # Patterns to find the starting date, estimated delivery date, and duration for each milestone
    starting_date_pattern = r"Starting Date: (\w+) (\d+)(?:th|rd|st|nd)?,? (\d{4})"
    delivery_date_pattern = (
        r"Estimated delivery date: (\w+) (\d+)(?:th|rd|st|nd)?,? (\d{4})"
    )
    duration_pattern = (
        r"(?!Total)\sEstimated Duration: (\d+) (hours|weeks|months|week|month|hour)"
    )
    milestone_pattern = r"Milestone:? (\d+)\s*"

    start_dates = []
    delivery_dates = []
    durations = []
    milestones_count = 0

    for milestone_match in re.finditer(milestone_pattern, body):
        milestone_index = int(milestone_match.group(1))
        milestone_start = milestone_match.end()
        if milestone_index > milestones_count:
            milestones_count = milestone_index

        # Extract start date, delivery date, and duration for the current milestone
        start_date_match = re.search(starting_date_pattern, body[milestone_start:])
        delivery_date_match = re.search(delivery_date_pattern, body[milestone_start:])
        duration_match = re.search(duration_pattern, body[milestone_start:])

        if start_date_match:
            try:
                start_date = datetime.strptime(
                    f"{start_date_match.group(2)} {start_date_match.group(1)} {start_date_match.group(3)}",
                    "%d %b %Y",
                )
            except ValueError:
                start_date = datetime.strptime(
                    f"{start_date_match.group(2)} {start_date_match.group(1)} {start_date_match.group(3)}",
                    "%d %B %Y",
                )
            start_dates.append(start_date)
        else:
            start_dates.append(None)

        if delivery_date_match:
            try:
                delivery_date = datetime.strptime(
                    f"{delivery_date_match.group(2)} {delivery_date_match.group(1)} {delivery_date_match.group(3)}",
                    "%d %b %Y",
                )
            except ValueError:
                delivery_date = datetime.strptime(
                    f"{delivery_date_match.group(2)} {delivery_date_match.group(1)} {delivery_date_match.group(3)}",
                    "%d %B %Y",
                )
            except ValueError:
                ValueError(f"Error: Invalid delivery date format.")
            delivery_dates.append(delivery_date)
        else:
            delivery_dates.append(None)

        if duration_match:
            duration_value = int(duration_match.group(1))
            duration_unit = duration_match.group(2)
            durations.append((duration_value, duration_unit))
        else:
            durations.append(None)

    # Calculate and format end dates for each milestone
    formatted_dates = ""
    for i in range(milestones_count):
        start_date = start_dates[i]
        delivery_date = delivery_dates[i]
        duration_value, duration_unit = durations[i] or (None, None)

        if start_date and duration_value and duration_unit:
            if duration_unit == "hours" or duration_unit == "hour":
                end_date = start_date + timedelta(hours=duration_value)
            elif duration_unit == "weeks" or duration_unit == "week":
                end_date = start_date + timedelta(weeks=duration_value)
            elif duration_unit == "months" or duration_unit == "month":
                end_date = start_date + timedelta(weeks=duration_value * 4)
            else:
                return "Error: Invalid duration unit."
            formatted_dates += (
                f"Start Date for Milestone {i+1}: {start_date.strftime('%Y %b %d')}, "
            )
            formatted_dates += (
                f"End Date for Milestone {i+1}: {end_date.strftime('%B %d, %Y')}; "
            )
        elif delivery_date and duration_value and duration_unit:
            if duration_unit == "hours" or duration_unit == "hour":
                start_date = delivery_date - timedelta(hours=duration_value)
            elif duration_unit == "weeks" or duration_unit == "week":
                start_date = delivery_date - timedelta(weeks=duration_value)
            elif duration_unit == "months" or duration_unit == "month":
                start_date = delivery_date - timedelta(weeks=duration_value * 4)
            else:
                return "Error: Invalid duration unit."
            formatted_dates += (
                f"Start Date for Milestone {i+1}: {start_date.strftime('%Y %b %d')}, "
            )
            formatted_dates += (
                f"End Date for Milestone {i+1}: {delivery_date.strftime('%B %d, %Y')}; "
            )
        else:
            continue

    if formatted_dates == "":
        return "NONE"
    return formatted_dates


def parse_pricing(project_complexity):
    if project_complexity == "Easy":
        pricing_per_hours = easy_cost
    elif project_complexity == "Medium":
        pricing_per_hours = medium_cost
    elif project_complexity == "Hard":
        pricing_per_hours = hard_cost
    else:
        pricing_per_hours = "error"
    return pricing_per_hours
