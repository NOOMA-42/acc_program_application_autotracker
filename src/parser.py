import requests
import csv
import re
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

easy_cost = os.getenv("EASY")
medium_cost = os.getenv("MEDIUM")
hard_cost = os.getenv("HARD")


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
    format_cost_per_milestone = ""

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
            milestone_cost = milestone_hours * float(fte) * float(easy_cost)
        elif project_complexity == "Medium":
            milestone_cost = milestone_hours * float(fte) * float(medium_cost)
        elif project_complexity == "Hard":
            milestone_cost = milestone_hours * float(fte) * float(hard_cost)
        else:
            milestone_cost = "error"
        format_cost_per_milestone_components.append(milestone_cost)

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
        format_cost_per_milestone += f"m{i} = ${num}; "

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
    body = re.sub(r"\*\*|\\r\\n", "", body)  # Remove unnecessary patterns

    # Patterns to find the starting date, estimated delivery date, and duration for each milestone
    starting_date_pattern = r"Starting Date: (\w+) (\d+)(?:th|rd|st|nd)?,? (\d{4})"
    delivery_date_pattern = r"Estimated delivery date: (\w+) (\d+)(?:th|rd|st|nd)?,? (\d{4})"
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