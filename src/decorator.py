import functools
from src.logger import logger

def log_issue_error(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            if result is None:
                issue_title = args[0] if len(args) > 0 else kwargs.get('issue_title', 'Unknown')
                logger.error(f"Function {func.__name__} returned None for issue '{issue_title}'")
            return result
        except Exception as e:
            issue_title = args[0] if len(args) > 0 else kwargs.get('issue_title', 'Unknown')
            logger.error(f"Error in {func.__name__} for issue '{issue_title}': {str(e)}")
            return None
    return wrapper