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


def create_sly_tag(updated_tag):
    created_tag = g.project_meta.get_tag_meta(updated_tag['name']).to_json()
    created_tag['value'] = updated_tag['selected_value']

    return created_tag


def remove_frame_index_locally(name, value, current_frame):
    frames_list = g.tags2stats[name][value]['framesList']
    f.safe_dict_value_append(g.updated_tags, current_frame, {'name': name,
                                                             'value': value})
    try:
        frame_index = frames_list.index(current_frame)
        g.tags2stats[name][value]['framesList'].pop(frame_index)
    except Exception as ex:
        sly.logger.warn(f'locally tag remove failed: {ex}')


def init_tag_locally(name, value):
    if g.tags2stats.get(name, None) is None:
        g.tags2stats[name] = {}

    if g.tags2stats[name].get(value, None) is None:
        g.tags2stats[name][value] = {
            'framesRanges': [],
            'colors': [],
            'framesList': [],
            'solo_button': f.init_solo_button()

        }


def add_frame_index_locally(name, value, current_frame):
    init_tag_locally(name, value)

    frames_list = set(g.tags2stats[name][value]['framesList'])
    frames_list.add(current_frame)
    g.tags2stats[name][value]['framesList'] = list(frames_list)

    f.safe_dict_value_append(g.updated_tags, current_frame, {'name': name,
                                                             'value': value})


def get_available_tags(frame_num):
    available_fields = []
    project_tags = g.project_meta.to_json().get('tags', [])  # use to unpack available tags
    for current_tag in project_tags:
        if current_tag.get('values', None) is not None:  # ONLY TAGS WITH VALUES
            available_fields.append({
                'name': current_tag.get('name', ''),
                'color': current_tag.get('color', ''),
                'available_values': current_tag['values'],
                'selected_value': None,
                'updated': tag_is_updated(current_tag.get('name', ''), None, frame_num)
            })

    return available_fields


def get_tags_on_frame(current_frame):
    tags_on_frame = []

    for current_tag in g.tags2stats.keys():
        for current_value in g.tags2stats[current_tag].keys():
            frames_list = g.tags2stats[current_tag][current_value].get('framesList', [])
            if current_frame in frames_list:
                tags_on_frame.append({'name': current_tag,
                                      'value': current_value,
                                      'updated': tag_is_updated(current_tag, current_value, current_frame)})

    return tags_on_frame


def tag_is_updated(name, value, frame_num):
    tags_on_frame = g.updated_tags.get(frame_num, [])
    for current_tag in tags_on_frame:
        if current_tag['name'] == name and current_tag['value'] == value:
            return True

    return False


def fill_available_tags_by_values(tab_content, tags_on_frame):
    for tag_on_frame in tags_on_frame:
        for tag_index, available_tag in enumerate(tab_content):
            if available_tag['name'] == tag_on_frame['name'] and \
                    tag_on_frame.get('value', '') in available_tag['available_values']:
                tab_content[tag_index]['selected_value'] = tag_on_frame['value']
                tab_content[tag_index]['updated'] = tag_on_frame['updated']

                break


def update_tab_by_name(tab_name, current_frame=0):
    tab_content = get_available_tags(current_frame)

    if tab_name == 'videos':
        state_name = 'tagsOnVideo'
        g.api.app.set_field(g.task_id, f'state.{state_name}', tab_content)

    if tab_name == 'frames':
        state_name = 'tagsOnFrame'
        tags_on_frame = get_tags_on_frame(current_frame)
        fill_available_tags_by_values(tab_content, tags_on_frame)
        g.api.app.set_field(g.task_id, f'state.{state_name}', tab_content)

    return tab_content


def update_tag_locally(current_frame, updated_tag):
    tags_on_frame = get_tags_on_frame(current_frame)

    for tag_index, tag_on_frame in enumerate(tags_on_frame):
        if updated_tag['name'] == tag_on_frame['name']:
            remove_frame_index_locally(tag_on_frame['name'], tag_on_frame['value'], current_frame)
            if updated_tag['selected_value'] is not None:
                add_frame_index_locally(tag_on_frame['name'], updated_tag['selected_value'], current_frame)
            break
    else:
        if updated_tag['selected_value'] is not None:
            add_frame_index_locally(updated_tag['name'], updated_tag['selected_value'], current_frame)


def process_updated_tag_locally(state):
    if state['updatedTag']['selected_value'] == '':
        state['updatedTag']['selected_value'] = None

    update_tag_locally(state['currentFrame'], state['updatedTag'])


# def process_value


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
        process_updated_tag_locally(state)

    update_tab_by_name('frames', current_frame=state['currentFrame'])
    fields_to_update[f'data.userStats["Unsaved Tags"]'] = f.get_unsaved_tags_count()


@g.my_app.callback("frame_tag_updated")
@sly.timeit
@g.update_fields
# @g.my_app.ignore_errors_and_show_dialog_window()
def frame_tag_updated(api: sly.Api, task_id, context, state, app_logger, fields_to_update):
    if state['updatedTag'].get('selected_value', None) is not None and state['visibleChange'] or \
            state['updatedTag'].get('selected_value', None) == '':

        fields_to_update['state.visibleChange'] = False

        process_updated_tag_locally(state)

        if state['updatedTag']['selected_value'] is not None:
            g.user_stats['tags_created'] += 1

        update_tab_by_name('frames', current_frame=state['currentFrame'])

        g.user_stats['annotated_frames'].add(state['currentFrame'])  # MOVE TO SEP FUNC
        fields_to_update['state.currentJobInfo.framesAnnotated'] = len(g.user_stats['annotated_frames'])
        fields_to_update['state.currentJobInfo.tagsCreated'] = g.user_stats['tags_created']
        fields_to_update[f'data.userStats["Unsaved Tags"]'] = f.get_unsaved_tags_count()

#
# @g.my_app.callback("copy_from_preview")
# @sly.timeit
# @g.update_fields
# # @g.my_app.ignore_errors_and_show_dialog_window()
# def copy_from_preview(api: sly.Api, task_id, context, state, app_logger, fields_to_update):
#     fields_to_update['state.buttonsLoading.copyValuesFromPreview'] = False
#
#     tags_on_card = update_tab_by_name('frames', current_frame=state['lastAnnotatedFrame'])
#
#     for tag in tags_on_card:
#         update_tag_locally(state['currentFrame'], tag)
#         g.user_stats['tags_created'] += 1
#
#     g.user_stats['annotated_frames'].add(state['currentFrame'])  # MOVE TO SEP FUNC
#     fields_to_update['state.currentJobInfo.framesAnnotated'] = len(g.user_stats['annotated_frames'])
#     fields_to_update['state.currentJobInfo.tagsCreated'] = g.user_stats['tags_created']
