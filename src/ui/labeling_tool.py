import ast
import json
import time

import sly_globals as g
import sly_functions as f
import supervisely_lib as sly


def init_fields(state, data):
    state['selectedTagMode'] = 'frames'
    state['tagsOnFrame'] = []
    state['tagsOnVideo'] = []

    state['lastAnnotatedFrame'] = None
    state['updatedTag'] = None


def get_available_tags():
    available_fields = []
    for current_tag in g.available_tags:
        if current_tag.get('values', None) is not None:  # ONLY TAGS WITH VALUES
            available_fields.append({
                'name': current_tag.get('name', ''),
                'color': current_tag.get('color', ''),
                'available_values': current_tag['values'],
                'selected_value': None
            })

    return available_fields


def create_sly_tag(updated_tag):
    created_tag = g.project_meta.get_tag_meta(updated_tag['name']).to_json()
    created_tag['value'] = updated_tag['selected_value']

    return created_tag


def update_tag_locally(current_frame, updated_tag):
    tags_on_frame = g.tags_on_video['frames'].get(current_frame, [])

    for tag_index, tag_on_frame in enumerate(tags_on_frame):
        if updated_tag['name'] == tag_on_frame['name']:
            if len(updated_tag['selected_value']) > 0:
                tags_on_frame[tag_index]['value'] = updated_tag['selected_value']
            else:
                tags_on_frame.pop(tag_index)
            break
    else:
        if updated_tag['selected_value'] is not None and len(updated_tag['selected_value']) > 0:
            tags_on_frame.append(create_sly_tag(updated_tag))

    g.tags_on_video['frames'][current_frame] = tags_on_frame


def update_tab_by_name(tab_name, current_frame=0):
    tab_content = get_available_tags()

    if tab_name == 'videos':
        state_name = 'tagsOnVideo'
        g.api.app.set_field(g.task_id, f'state.{state_name}', tab_content)

    if tab_name == 'frames':
        state_name = 'tagsOnFrame'
        tags_on_frame = g.tags_on_video['frames'].get(current_frame, [])

        for tag_on_frame in tags_on_frame:
            for tag_index, available_tag in enumerate(tab_content):
                if available_tag['name'] == tag_on_frame['name'] and \
                        tag_on_frame.get('value', '') in available_tag['available_values']:
                    tab_content[tag_index]['selected_value'] = tag_on_frame['value']
                    break

        g.api.app.set_field(g.task_id, f'state.{state_name}', tab_content)

    return tab_content


@g.my_app.callback("clean_values")
@sly.timeit
@g.update_fields
@g.my_app.ignore_errors_and_show_dialog_window()
def clean_values(api: sly.Api, task_id, context, state, app_logger, fields_to_update):
    fields_to_update['state.buttonsLoading.cleanAllValues'] = False

    tags_on_frame = state['tagsOnFrame']
    for index, current_tag in enumerate(tags_on_frame):
        tags_on_frame[index]['selected_value'] = None

    fields_to_update['state.tagsOnFrame'] = tags_on_frame


@g.my_app.callback("frame_tag_updated")
@sly.timeit
@g.update_fields
# @g.my_app.ignore_errors_and_show_dialog_window()
def frame_tag_updated(api: sly.Api, task_id, context, state, app_logger, fields_to_update):
    if state['updatedTag'].get('selected_value', None) is not None:
        fields_to_update['state.lastAnnotatedFrame'] = state['currentFrame']
        update_tag_locally(state['currentFrame'], state['updatedTag'])

        g.user_stats['tags_created'] += 1

        g.user_stats['annotated_frames'].add(state['currentFrame'])  # MOVE TO SEP FUNC
        fields_to_update['state.currentJobInfo.framesAnnotated'] = len(g.user_stats['annotated_frames'])
        fields_to_update['state.currentJobInfo.tagsCreated'] = g.user_stats['tags_created']


@g.my_app.callback("copy_from_preview")
@sly.timeit
@g.update_fields
# @g.my_app.ignore_errors_and_show_dialog_window()
def copy_from_preview(api: sly.Api, task_id, context, state, app_logger, fields_to_update):
    fields_to_update['state.buttonsLoading.copyValuesFromPreview'] = False

    tags_on_card = update_tab_by_name('frames', current_frame=state['lastAnnotatedFrame'])

    for tag in tags_on_card:
        update_tag_locally(state['currentFrame'], tag)
        g.user_stats['tags_created'] += 1

    g.user_stats['annotated_frames'].add(state['currentFrame'])  # MOVE TO SEP FUNC
    fields_to_update['state.currentJobInfo.framesAnnotated'] = len(g.user_stats['annotated_frames'])
    fields_to_update['state.currentJobInfo.tagsCreated'] = g.user_stats['tags_created']


