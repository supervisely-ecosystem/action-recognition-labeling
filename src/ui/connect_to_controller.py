import ast
import json

import sly_globals as g
import supervisely_lib as sly


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
        'Videos Annotated': '0',
        'Tags Added': '0',
        'Tags Changed': '0',
        'Time in Work': '00:00:00'
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

        g.controller_session_id = task_id
        fields_to_update['state.controllerConnected'] = True

        connected_data = {
            'Status': "Connected",
            'Session ID': g.controller_session_id,
            'Admin Nickname': response.get('admin_nickname', None),
            'Videos for Annotation': response.get('items_for_annotation_count', None),
            'Videos for Review': response.get('items_for_review_count', None)
        }

        fields_to_update['data.connectedData'] = connected_data

    elif rc == -1:
        raise UserWarning(
            f'User with your ID is already connected: /apps/{g.workspace_id}/sessions/{response["taskId"]}')
    else:
        raise ValueError('Cannot connect to controller')
