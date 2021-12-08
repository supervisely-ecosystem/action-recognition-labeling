import ast
import json

import sly_globals as g
import supervisely_lib as sly

import sly_functions as f

from sly_fields_names import UserStatsField


def init_fields(state, data):
    state['userMode'] = None

    state['connectingAnnotationController'] = False
    state['controllerConnected'] = False

    state['annControllerId'] = None
    state['showAppModeSelector'] = False

    data["ssOptionsAnnotationController"] = {
        "sessionTags": ["deployed_nn_embeddings"],
        "showLabel": False,
        "size": "small"
    }

    data['teamId'] = g.team_id

    data['connectedData'] = {

        'Status': "Connected",
        'Session ID': None,
        'Admin Nickname': None,
        'Uptime': None,
        'Videos Available': None,
        'Videos for Annotation': None,
        'Videos for Review': None
    }

    data['userStats'] = {
        'Videos Annotated': None,
        'Tags Created': 0,
        'Time in Work': None,
        'Frames Annotated': None,
        'Unsaved Tags': 0
    }


@g.my_app.callback("connect_to_controller")
@sly.timeit
@g.update_fields
@g.my_app.ignore_errors_and_show_dialog_window()
def connect_to_controller(api: sly.Api, task_id, context, state, app_logger, fields_to_update):
    task_id = state['annControllerId']
    fields_to_update['state.connectingAnnotationController'] = False

    response = api.task.send_request(task_id, "connect_user", data={'userId': context['userId'],
                                                                    'taskId': g.task_id}, timeout=3)
    rc = response['rc']

    if rc == 0:
        f.set_available_mods_by_response(response, fields_to_update)
        f.update_connected_data_by_response(response, fields_to_update)
        f.update_user_stats_by_response(response, fields_to_update)

        g.controller_session_id = task_id
        fields_to_update['state.controllerConnected'] = True
    elif rc == -1:
        raise UserWarning(
            f'User with your ID is already connected: /apps/{g.workspace_id}/sessions/{response["taskId"]}')
    else:
        raise ValueError('Cannot connect to controller')
