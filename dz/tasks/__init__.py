from builder import check_repo, build_and_deploy
from deploy import user_manage_py_command

def monkey_patch_celery_db_models_Task():
    """
    Monkeypatch to allow us to get the date_done from celery'd database
    result backend. This appears to be a regression in celery's
    get_task_meta implementation specific to the database backend, and
    there doesn't seem to be another way to get date_done.

    Issue filed: https://github.com/ask/celery/issues/issue/325
    """
    from celery.db.models import Task
    if hasattr(Task, "_old_to_dict"):
        return

    Task._old_to_dict = Task.to_dict

    def replacement_to_dict(self):
        result = self._old_to_dict()
        result["date_done"] = self.date_done
        return result

    Task.to_dict = replacement_to_dict


def undo_monkey_patch_celery_db_models_Task():
    """
    Un-apply the above monkeypatch.
    """
    from celery.db.models import Task

    if not hasattr(Task, "_old_to_dict"):
        return

    Task.to_dict = Task._old_to_dict

    delattr(Task, "_old_to_dict")
