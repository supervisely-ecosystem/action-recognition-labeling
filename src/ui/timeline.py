import supervisely as sly

from supervisely import handle_exceptions

import sly_globals as g
import sly_functions as f


def init_fields(state, data):
    state['selectedSegment'] = None

    state['updatedRanges'] = {
        'frameRanges': [],
        'colors': []
    }
    state['timelineUpdatedRangesOptions'] = {
        "pointerColor": "rgba(224,56,62,0)",
        "height": "13px"
    }

    data['timelineTags'] = None

    state['timelineOptions'] = {
        "pointerColor": "rgba(224,56,62,1)"
    }

    state['selectedTimelineRow'] = None
    state['selectedSoloMode'] = 'union'

    state['rangesToPlay'] = None
    state['rangeToRemove'] = None



@g.my_app.callback("solo_button_clicked")
@sly.timeit
@g.update_fields
@g.my_app.ignore_errors_and_show_dialog_window()
@handle_exceptions
def solo_button_clicked(api: sly.Api, task_id, context, state, app_logger, fields_to_update):
    button_stats = state['selectedTimelineRow']
    next_stage = (button_stats['soloButtonStage'] + 1) % len(f.solo_button_stages)

    new_button_stats = f.solo_button_stages[next_stage]
    row_index = button_stats['index']

    tags_table = g.api.app.get_field(g.task_id, 'data.selectedTagsStats')
    tags_table[row_index]['solo_button'] = new_button_stats

    f.update_play_intervals_by_table(tags_table, state['selectedSoloMode'], fields_to_update)

    fields_to_update[f'data.selectedTagsStats[{row_index}].solo_button'] = new_button_stats


@g.my_app.callback("solo_mode_changed")
@sly.timeit
@g.update_fields
@g.my_app.ignore_errors_and_show_dialog_window()
@handle_exceptions
def solo_mode_changed(api: sly.Api, task_id, context, state, app_logger, fields_to_update):
    tags_table = g.api.app.get_field(g.task_id, 'data.selectedTagsStats')
    f.update_play_intervals_by_table(tags_table, state['selectedSoloMode'], fields_to_update)


@g.my_app.callback("remove_interval")
@sly.timeit
@g.update_fields
@g.my_app.ignore_errors_and_show_dialog_window()
@handle_exceptions
def solo_mode_changed(api: sly.Api, task_id, context, state, app_logger, fields_to_update):
    print(state)  ##state.rangeToRemove: {'tag': 'man in frame', 'value': 'True', 'range': {'interval': [124, 131]
    fields_to_update['state.selectedTagMode'] = 'frames'
    fields_to_update['state.copyFromPrevActivated'] = False

    range_to_remove = state['rangeToRemove']

    start_frame, end_frame = range_to_remove['range']['interval'][0], range_to_remove['range']['interval'][1]

    for current_frame in range(start_frame, end_frame + 1, 1):
        state['updatedTag'] = {
            'name': range_to_remove['tag'],
            'selected_value': ''
        }
        state['currentFrame'] = current_frame

        f.process_updated_tag_locally(state)

    f.update_tab_by_name('frames', state['currentFrame'])
    f.update_user_stats(fields_to_update)

    f.update_tags_on_timeline(fields_to_update)


