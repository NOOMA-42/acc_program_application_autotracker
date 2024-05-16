import pytest
from src.main import get_issues, process_tasks
from src.parser import parse_issue_meta_data, parse_milestone
from src.logger import logger

@pytest.fixture
def preload_issue():
    """ 
    Manually find the task and proposal
    issue 47 is a proposal
    """
    idx_proposal = 35

    issues = get_issues()
    tasks = process_tasks(issues)
    issue = None
    for e in issues:
        if e['url'] == f"https://api.github.com/repos/privacy-scaling-explorations/acceleration-program/issues/{idx_proposal}":
            issue = e
            title = issue.get("title", "").strip()
    if issue is not None:
        body, issue_link, assignee, creator, linked_tasks, project_complexity = parse_issue_meta_data(title, issue, tasks)
        return body, issue_link, assignee, creator, linked_tasks, project_complexity, title

def test_parse_milestone(preload_issue) -> None:
    body, issue_link, assignee, creator, linked_tasks, project_complexity , title = preload_issue
    logger.info(f"test_parse_milestone: issue_link: {issue_link} title: {title}")
    working_hour_data = parse_milestone(body, title, project_complexity)
    logger.info(working_hour_data)