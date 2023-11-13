from supervisely import handle_exceptions

import sly_globals as g
import sly_functions as f
import supervisely as sly


def init_fields(state, data):
    state['selectedTagMode'] = 'frames'
    state['tagsOnFrame'] = []
    state['tagsOnVideo'] = []

    state['lastAnnotatedFrame'] = None
    state['updatedTag'] = None
    state['visibleChange'] = False

    state['copyFromPrevActivated'] = False

    state['tagType'] = 'frame'


@g.my_app.callback("clean_values")
@sly.timeit
@g.update_fields
# @g.my_app.ignore_errors_and_show_dialog_window()
@handle_exceptions
def clean_values(api: sly.Api, task_id, context, state, app_logger, fields_to_update):
    fields_to_update['state.buttonsLoading.cleanAllValues'] = False

    tags_on_frame = state['tagsOnFrame']
    for index, current_tag in enumerate(tags_on_frame):
        tags_on_frame[index]['selected_value'] = ''

        state['updatedTag'] = current_tag
        f.process_updated_tag_locally(state)

    f.update_tab_by_name('frames', current_frame=state['currentFrame'])
    f.update_user_stats(fields_to_update)
    f.update_tags_on_timeline(fields_to_update)


@g.my_app.callback("tag_updated")
@sly.timeit
@g.update_fields
# @g.my_app.ignore_errors_and_show_dialog_window()
@handle_exceptions
def tag_updated(api: sly.Api, task_id, context, state, app_logger, fields_to_update):
    if state['updatedTag'].get('selected_value', None) is not None and state['visibleChange']:
        fields_to_update['state.visibleChange'] = False

        f.process_updated_tag_locally(state)

        if state['tagType'] == 'frame':
            f.update_tab_by_name('frames', current_frame=state['currentFrame'])

        if state['tagType'] == 'video':
            f.update_tab_by_name('videos')

        f.update_user_stats(fields_to_update)
        f.update_tags_on_timeline(fields_to_update)




