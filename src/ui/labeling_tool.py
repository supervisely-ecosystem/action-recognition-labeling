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
    state['visibleChange'] = False

    state['copyFromPrevActivated'] = False


@g.my_app.callback("clean_values")
@sly.timeit
@g.update_fields
# @g.my_app.ignore_errors_and_show_dialog_window()
def clean_values(api: sly.Api, task_id, context, state, app_logger, fields_to_update):
    fields_to_update['state.buttonsLoading.cleanAllValues'] = False

    tags_on_frame = state['tagsOnFrame']
    for index, current_tag in enumerate(tags_on_frame):
        tags_on_frame[index]['selected_value'] = ''

        state['updatedTag'] = current_tag
        f.process_updated_tag_locally(state)

    f.update_tab_by_name('frames', current_frame=state['currentFrame'])
    fields_to_update[f'data.userStats["Unsaved Tags"]'] = f.get_unsaved_tags_count()


@g.my_app.callback("frame_tag_updated")
@sly.timeit
@g.update_fields
# @g.my_app.ignore_errors_and_show_dialog_window()
def frame_tag_updated(api: sly.Api, task_id, context, state, app_logger, fields_to_update):
    if state['updatedTag'].get('selected_value', None) is not None and state['visibleChange']:
        fields_to_update['state.visibleChange'] = False

        f.process_updated_tag_locally(state)

        if state['updatedTag']['selected_value'] is not None:
            g.user_stats['tags_created'] += 1

        f.update_tab_by_name('frames', current_frame=state['currentFrame'])

        g.user_stats['annotated_frames'].add(state['currentFrame'])  # MOVE TO SEP FUNC
        fields_to_update['state.currentJobInfo.framesAnnotated'] = len(g.user_stats['annotated_frames'])
        fields_to_update['state.currentJobInfo.tagsCreated'] = g.user_stats['tags_created']
        fields_to_update[f'data.userStats["Unsaved Tags"]'] = f.get_unsaved_tags_count()

