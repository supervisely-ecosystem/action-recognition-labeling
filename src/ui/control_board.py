import ast
import json
import time

import sly_globals as g
import sly_functions as f
import supervisely_lib as sly


def init_fields(state, data):
    state['buttonsLoading'] = {
        "getItem": False,
        "saveAnn": False,
        "finishLabeling": False
    }

    state['currentJobInfo'] = {
        'isStarted': False,
        'startTime': None,
        'videoId': None,
        'annotationsUpdatedTime': '-'
    }


@g.my_app.callback("get_new_item")
@sly.timeit
@g.update_fields
@g.my_app.ignore_errors_and_show_dialog_window()
def get_new_item(api: sly.Api, task_id, context, state, app_logger, fields_to_update):
    fields_to_update['state.buttonsLoading.getItem'] = False

    annotation_controller_id = state['annControllerId']

    data_to_send = {
        'userId': context['userId'],
        'taskId': g.task_id,
        'mode': state['userMode']
    }

    response = api.task.send_request(annotation_controller_id, "get_item", data=data_to_send, timeout=3)

    fields_to_update['state.currentJobInfo'] = {
        'isStarted': True,
        'startTime': time.time(),
        'videoId': response['item_id'],
        'annotationsUpdatedTime': f.get_current_time()
    }



