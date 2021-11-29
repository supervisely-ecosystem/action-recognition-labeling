import ast
import json
import time

import sly_globals as g
import sly_functions as f
import supervisely_lib as sly


def init_fields(state, data):
    state['currentFrame'] = 0
    state['rangesToPlay'] = None


@g.my_app.callback("pointer_updated")
@sly.timeit
@g.update_fields
@g.my_app.ignore_errors_and_show_dialog_window()
def pointer_updated(api: sly.Api, task_id, context, state, app_logger, fields_to_update):
    if state['copyFromPrevActivated']:
        tags_on_frame = f.update_tab_by_name('frames', state['lastAnnotatedFrame'])
        for index, current_tag in enumerate(tags_on_frame):
            state['updatedTag'] = current_tag
            f.process_updated_tag_locally(state)

    f.update_tab_by_name('frames', state['currentFrame'])
    fields_to_update[f'data.userStats["Unsaved Tags"]'] = f.get_unsaved_tags_count()
