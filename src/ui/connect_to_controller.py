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


def set_available_mods_by_response(response, fields_to_update):
    if response['can_annotate'] and response['can_review']:
        fields_to_update['state.userAvailableMods'] = ['annotator', 'reviewer']
        fields_to_update['state.userMode'] = 'annotator'
    elif response['can_annotate']:
        fields_to_update['state.userMode'] = 'annotator'
        fields_to_update['state.userAvailableMods'] = ['annotator']
    elif response['can_review']:
        fields_to_update['state.userMode'] = 'reviewer'
        fields_to_update['state.userAvailableMods'] = ['reviewer']
    else:
        raise UserWarning(
            f'You have no annotating or reviewing rights. Please call Annotation Controller admin.')


def update_user_stats_by_response(response, fields_to_update):
    if response.get('user_stats') is not None:
        user_stats = {
            'Videos Annotated': response['user_stats'].get('items_annotated', 0),
            'Frames Annotated': response['user_stats'].get('frames_annotated', 0),
            'Tags Created': response['user_stats'].get('tags_created', 0),
            'Time in Work': f.get_datetime_by_unix(response['user_stats'].get(UserStatsField.WORK_TIME_UNIX))
            if response['user_stats'].get(UserStatsField.WORK_TIME_UNIX) is not None else f.get_datetime_by_unix(0)
        }

        for key, value in user_stats.items():
            fields_to_update[f'data.userStats.{key}'] = value


def update_connected_data_by_response(response, fields_to_update):
    connected_data = {
        'Status': "Connected",
        'Session ID': g.controller_session_id,
        'Admin Nickname': response.get('admin_nickname', None),
        'Videos for Annotation': response.get('items_for_annotation_count', None),
        'Videos for Review': response.get('items_for_review_count', None)
    }
    fields_to_update['data.connectedData'] = connected_data


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
        set_available_mods_by_response(response, fields_to_update)
        update_connected_data_by_response(response, fields_to_update)
        update_user_stats_by_response(response, fields_to_update)

        g.controller_session_id = task_id
        fields_to_update['state.controllerConnected'] = True
    elif rc == -1:
        raise UserWarning(
            f'User with your ID is already connected: /apps/{g.workspace_id}/sessions/{response["taskId"]}')
    else:
        raise ValueError('Cannot connect to controller')
