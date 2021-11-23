import ast
import json
import time

import sly_globals as g
import sly_functions as f
import supervisely_lib as sly
import labeling_tool

def init_fields(state, data):
    state['currentFrame'] = 0


@g.my_app.callback("pointer_updated")
@sly.timeit
@g.update_fields
@g.my_app.ignore_errors_and_show_dialog_window()
def pointer_updated(api: sly.Api, task_id, context, state, app_logger, fields_to_update):
    labeling_tool.update_tab_by_name('frames', state['currentFrame'])
