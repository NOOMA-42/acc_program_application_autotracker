import csv


def get_csv_header():
    return [
        "Type",
        "Title",
        "Status",
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
        "Total Cost",
        "Cost Per Milestone",
        "Start/End Date",
        "Deliverable Repo Available",
    ]


def get_csv_row(proposal_type, task_info, proposal, task_link):
    return [
        proposal_type,
        task_info["title"],
        "",
        task_info["creator"],
        task_info["assignee"],
        task_link,
        task_info["project_complexity"],
        "Yes" if proposal else "No",
        proposal["link"] if proposal else "NONE",
        proposal["creator"] if proposal else "NONE",
        proposal["total_duration_value"] if proposal else "NONE",
        proposal["total_fte"] if proposal else "NONE",
        proposal["total_working_hours"] if proposal else "NONE",
        proposal["formatted_equation"] if proposal else "NONE",
        task_info["Pricing Per Hours"],
        proposal["total_cost"] if proposal else "NONE",
        proposal["format_cost_per_milestone"] if proposal else "NONE",
        proposal.get("start_end_date", "NONE") if proposal else "NONE",
        "NONE",
    ]


def write_to_csv(tasks, filepath):
    with open(filepath, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, quoting=csv.QUOTE_ALL)
        writer.writerow(get_csv_header())

        for task_link, task_info in tasks.items():
            if task_info["proposals"]:
                for proposal in task_info["proposals"]:
                    if len(task_info["proposals"]) == 1 and task_info["type"] == "Closed Task":
                        proposal_type = "Closed Task & Closed Proposal" 
                    elif len(task_info["proposals"]) == 1 and task_info["type"] == "Task":
                        proposal_type = "Task & Proposal" 
                    else:
                        proposal_type = "Task & Competing Proposal"
                    row = get_csv_row(proposal_type, task_info, proposal, task_link)
                    writer.writerow(row)
            else:
                row = get_csv_row(task_info["type"], task_info, None, task_link)
                writer.writerow(row)
