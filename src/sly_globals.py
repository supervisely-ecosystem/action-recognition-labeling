import functools
import os
import queue
from pathlib import Path
import sys
import pickle

import supervisely_lib as sly
from sly_fields_names import ItemsStatusField

import sly_functions as f

from dotenv import load_dotenv  # pip install python-dotenv\

load_dotenv("../debug.env")
load_dotenv("../secret_debug.env", override=True)

sly.logger.setLevel('DEBUG')

controller_session_id = None

my_app = sly.AppService()
api = my_app.public_api
task_id = my_app.task_id

team_id = int(os.environ['context.teamId'])
workspace_id = int(os.environ['context.workspaceId'])

team_members = api.user.get_team_members(team_id)

root_source_dir = str(Path(os.path.abspath(sys.argv[0])).parents[1])  # /annotation-controller/
sly.logger.info(f"Root source directory: {root_source_dir}")
sys.path.append(root_source_dir)

source_path = str(Path(sys.argv[0]).parents[0])  # /annotation-controller/src/
sly.logger.info(f"App source directory: {source_path}")
sys.path.append(source_path)

ui_sources_dir = os.path.join(source_path, "ui")  # /annotation-controller/src/ui/
sly.logger.info(f"UI source directory: {ui_sources_dir}")
sys.path.append(ui_sources_dir)

available_tags = {}
tags_on_video = {}

project_id = None
project_meta = None

user_stats = {
    'annotated_frames': set([]),
    'tags_created': 0
}

tag_frame_ranges = {}

technical_tags_names = [ItemsStatusField.TAG_NAME]


def update_fields(func):
    """Update state field after executing function"""

    @functools.wraps(func)
    def wrapper_updater(*args, **kwargs):
        kwargs['fields_to_update'] = {}
        exception = None

        try:
            value = func(*args, **kwargs)
        except Exception as ex:
            value = None
            exception = ex

        user_api = kwargs.get('api', None)
        app_task_id = kwargs.get('task_id', None)

        if user_api and app_task_id and len(kwargs['fields_to_update']) > 0:
            user_api.task.set_fields_from_dict(app_task_id, kwargs['fields_to_update'])

        if exception:
            raise exception

        return value

    return wrapper_updater
