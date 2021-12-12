import ast
import json
import time

import sly_globals as g
import sly_functions as f
import supervisely_lib as sly


def init_fields(state, data):
    state['currentFrame'] = 0
    state['rangesToPlay'] = None

    state['videoInPlay'] = False
    state['videoPlayedInterval'] = [0, 0]


@g.my_app.callback("pointer_updated")
@sly.timeit
@g.update_fields
@g.my_app.ignore_errors_and_show_dialog_window()
def pointer_updated(api: sly.Api, task_id, context, state, app_logger, fields_to_update):
    fields_to_update['state.selectedTagMode'] = 'frames'

    if state['copyFromPrevActivated']:
        tags_on_frame = f.update_tab_by_name('frames', state['lastAnnotatedFrame'])
        for index, current_tag in enumerate(tags_on_frame):
            state['updatedTag'] = current_tag
            f.process_updated_tag_locally(state)
        f.update_tags_on_timeline(fields_to_update)

    f.update_tab_by_name('frames', state['currentFrame'])
    f.update_user_stats(fields_to_update)


@g.my_app.callback("interval_played")
@sly.timeit
@g.update_fields
@g.my_app.ignore_errors_and_show_dialog_window()
def pointer_updated(api: sly.Api, task_id, context, state, app_logger, fields_to_update):
    fields_to_update['state.selectedTagMode'] = 'frames'
    fields_to_update['state.copyFromPrevActivated'] = False

    if state['copyFromPrevActivated']:
        start_frame, end_frame = state['videoPlayedInterval'][0], state['videoPlayedInterval'][1]

        for current_frame in range(start_frame, end_frame + 1, 1):
            tags_on_frame, _ = f.get_tags_on_frame('frames', current_frame=state['lastAnnotatedFrame'])

            for index, current_tag in enumerate(tags_on_frame):
                state['updatedTag'] = current_tag
                state['currentFrame'] = current_frame
                f.process_updated_tag_locally(state)
        f.update_tags_on_timeline(fields_to_update)

    f.update_tab_by_name('frames', state['currentFrame'])
    f.update_user_stats(fields_to_update)

