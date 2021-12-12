import ast
import json
import time
from itertools import chain

import sly_globals as g
import sly_functions as f
import supervisely_lib as sly

from functools import lru_cache


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


def reverse_ranges(frames_ranges, frames_count):
    all_frames = set([current_frame for current_frame in range(frames_count)])
    filled_frames = f.get_frames_list_from_ranges(frames_ranges)

    unfilled_frames = all_frames - set(filled_frames)
    return f.get_frames_ranges_from_list(unfilled_frames)


# @lru_cache(maxsize=5)
def get_ranges_to_play(solo_mode, tags_table):
    raw_ranges = []

    video_info = g.api.app.get_field(g.task_id, 'data.videoInfo')

    for row in tags_table:
        if row['solo_button']['stage'] == 1:  # tagged frames
            raw_ranges.append(f.get_frames_list_from_ranges(row['frameRanges']))
        elif row['solo_button']['stage'] == 2:  # untagged frames
            reversed_ranges = reverse_ranges(row['frameRanges'], video_info['frames_count'])
            raw_ranges.append(f.get_frames_list_from_ranges(reversed_ranges))

    if len(raw_ranges) == 0:
        return []

    if solo_mode == 'union':
        return f.get_frames_ranges_from_list(sorted(list(set(chain.from_iterable(raw_ranges)))))
    elif solo_mode == 'intersection':
        raw_ranges = list(map(set, raw_ranges))
        return f.get_frames_ranges_from_list(sorted(list(set.intersection(*raw_ranges))))
    else:
        return -1


@g.my_app.callback("solo_button_clicked")
@sly.timeit
@g.update_fields
@g.my_app.ignore_errors_and_show_dialog_window()
def solo_button_clicked(api: sly.Api, task_id, context, state, app_logger, fields_to_update):
    button_stats = state['selectedTimelineRow']
    next_stage = (button_stats['soloButtonStage'] + 1) % len(f.solo_button_stages)

    new_button_stats = f.solo_button_stages[next_stage]
    row_index = button_stats['index']

    tags_table = g.api.app.get_field(g.task_id, 'data.selectedTagsStats')
    tags_table[row_index]['solo_button'] = new_button_stats

    ranges_to_play = get_ranges_to_play(state['selectedSoloMode'], tags_table)

    fields_to_update[f'state.rangesToPlay'] = ranges_to_play if len(ranges_to_play) > 0 else None
    fields_to_update[f'data.selectedTagsStats[{row_index}].solo_button'] = new_button_stats


@g.my_app.callback("solo_mode_changed")
@sly.timeit
@g.update_fields
@g.my_app.ignore_errors_and_show_dialog_window()
def solo_mode_changed(api: sly.Api, task_id, context, state, app_logger, fields_to_update):
    tags_table = g.api.app.get_field(g.task_id, 'data.selectedTagsStats')
    ranges_to_play = get_ranges_to_play(state['selectedSoloMode'], tags_table)
    fields_to_update[f'state.rangesToPlay'] = ranges_to_play if len(ranges_to_play) > 0 else None


@g.my_app.callback("remove_interval")
@sly.timeit
@g.update_fields
@g.my_app.ignore_errors_and_show_dialog_window()
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


