import datetime
from string import Formatter

import supervisely_lib as sly
from itertools import chain

import sly_globals as g
from sly_fields_names import ItemsStatusField, UserStatsField

solo_button_stages = {
    0: {
        'stage': 0,  # disabled
        'soloButtonColorText': '#3d3d3d',
        'soloButtonColorBg': 'white'
    },
    1: {
        'stage': 1,  # tagged frames
        'soloButtonColorText': 'white',
        'soloButtonColorBg': '#f8ba29'
    },
    2: {
        'stage': 2,  # untagged frames
        'soloButtonColorText': '#f8ba29',
        'soloButtonColorBg': 'white'
    }
}


def get_current_time():
    return str(datetime.datetime.now().strftime("%H:%M:%S"))


def get_tags_on_video(api, video_id):
    tags_on_video = {
        'video': [],  # list of tags here [tag1, tag2, tag3, ...]
        'frames': {}  # dict of frames here 1: [tag1, tag2, tag3, ...]
    }

    video_annotations = api.video.annotation.download(video_id)

    tags_in_annotations = video_annotations.get('tags', [])
    for current_tag in tags_in_annotations:
        tag_frame_range = current_tag.get('frameRange', None)
        if tag_frame_range:
            for current_frame in range(tag_frame_range[0], tag_frame_range[1] + 1, 1):
                tags_on_frame = tags_on_video['frames'].get(current_frame, [])
                tags_on_frame.append(current_tag)
                tags_on_video['frames'][current_frame] = tags_on_frame
        else:
            tags_on_video['video'].append(current_tag)

    return tags_on_video


def get_project_meta(api, video_id):
    project_id, dataset_id = api.video.get_destination_ids(video_id)
    return api.project.get_meta(project_id)


def strfdelta(tdelta, fmt):
    f = Formatter()
    d = {}
    l = {'D': 86400, 'H': 3600, 'M': 60, 'S': 1}
    k = list(map(lambda x: x[1], list(f.parse(fmt))))
    rem = int(tdelta.total_seconds())

    for i in ('D', 'H', 'M', 'S'):
        if i in k and i in l.keys():
            d[i], rem = divmod(rem, l[i])

    return f.format(fmt, **d)


def get_datetime_by_unix(unix_time_delta):
    delta_obj = datetime.timedelta(seconds=round(unix_time_delta))
    return strfdelta(delta_obj, "{H:02}:{M:02}:{S:02}")


def get_tags_list_by_type(tag_type, video_id):
    video_annotation = g.api.video.annotation.download(video_id)
    tags_on_video = video_annotation.get('tags', [])

    tags_list = []

    for current_tag in tags_on_video:
        if current_tag.get('name') in g.technical_tags_names:
            continue

        frame_range = current_tag.get('frameRange')
        tag_value = current_tag.get('value')

        if tag_value is not None and tag_type == 'video' and frame_range is None:
            tags_list.append(current_tag)
        elif tag_value is not None and tag_type == 'frame' and frame_range:
            tags_list.append(current_tag)

    return tags_list


def safe_dict_value_append(source_dict, key, new_value):
    list_of_values = source_dict.get(key, [])
    list_of_values.append(new_value)
    source_dict[key] = list_of_values


def frame_ranges_to_list(frame_ranges):
    unique_frames = set()
    for frame_range in frame_ranges:
        for curr_frame in range(frame_range[0], frame_range[1] + 1, 1):
            unique_frames.add(curr_frame)

    return sorted(list(unique_frames))


def frames_ranges_to_frames_list(tags2stats):
    for current_tag in tags2stats.keys():
        for current_value in tags2stats[current_tag].keys():
            frames_ranges = tags2stats[current_tag][current_value].get('frameRanges', [])
            tags2stats[current_tag][current_value]['framesList'] = frame_ranges_to_list(frames_ranges)


def format_tags_on_frames_to_stats(tags2stats, tags_on_frames):
    video_tags = False

    for current_tag in tags_on_frames:
        tag_id = current_tag.get('id')
        name = current_tag.get('name')
        value = current_tag.get('value')
        frame_range = current_tag.get('frameRange', None)

        if name and value is not None:
            tags_values = tags2stats.get(name, {})

            tag_value_stats = tags_values.get(value, {})

            tag_color = g.project_meta.get_tag_meta(current_tag['name']).to_json()['color']

            safe_dict_value_append(tag_value_stats, 'ids', tag_id)  # updating ids
            safe_dict_value_append(tag_value_stats, 'frameRanges', frame_range)  # updating frame range
            safe_dict_value_append(tag_value_stats, 'colors', tag_color)  # updating colors

            tags_values[value] = tag_value_stats
            tags2stats[name] = tags_values

        if not video_tags and frame_range is None:
            video_tags = True

    if not video_tags:
        frames_ranges_to_frames_list(tags2stats)


def get_tags_stats(tags_on_frames):
    tags2stats = {}

    format_tags_on_frames_to_stats(tags2stats, tags_on_frames)
    return tags2stats


def init_solo_button():
    solo_button_params = {
        'stage': 0,
    }
    solo_button_params.update(solo_button_stages[0])
    return solo_button_params


def tag_stats_to_table(tags2stats):
    table = []
    for tag_key in tags2stats.keys():
        for tag_value in tags2stats[tag_key].keys():
            row_init = {
                'tag': tag_key,
                'value': tag_value,
                'solo_button': init_solo_button()
            }

            row_init.update(tags2stats[tag_key][tag_value])

            table.append(row_init)
    return table


def get_frames_ranges_from_list(frames_list):
    frame_ranges = []

    first_frame_in_range = None
    prev_frame_index = -1

    for frame_index in frames_list:

        if first_frame_in_range is None:
            first_frame_in_range = frame_index
            prev_frame_index = frame_index

        elif frame_index - 1 == prev_frame_index:
            prev_frame_index = frame_index

        else:
            frame_ranges.append([first_frame_in_range, prev_frame_index])

            first_frame_in_range = frame_index
            prev_frame_index = frame_index

    if first_frame_in_range is not None:
        if [first_frame_in_range, prev_frame_index] not in frame_ranges:
            frame_ranges.append([first_frame_in_range, prev_frame_index])

    return frame_ranges


def get_frames_list_from_ranges(frames_ranges):
    frames_set = set()

    for frame_range in frames_ranges:
        for current_frame in range(frame_range[0], frame_range[1] + 1, 1):
            frames_set.add(current_frame)

    return list(frames_set)


def tag_is_updated(name, value, frame_num):
    tags_on_frame = g.updated_tags.get(frame_num, [])
    for current_tag in tags_on_frame:
        if current_tag['name'] == name and current_tag['value'] == value:
            return True

    return False


def get_available_tags(frame_num):
    available_fields = []
    project_tags = g.project_meta.to_json().get('tags', [])  # use to unpack available tags

    for current_tag in project_tags:
        if current_tag.get('values', None) is not None:  # ONLY TAGS WITH VALUES
            available_fields.append({
                'name': current_tag.get('name', ''),
                'color': current_tag.get('color', ''),
                'available_values': current_tag['values'],
                'selected_value': '',
                'updated': tag_is_updated(current_tag.get('name', ''), None, frame_num)
            })

    return available_fields


def get_video_tags():
    tags_on_video = []

    for tag_name, tag_value in g.video_tags.items():
        tags_on_video.append({'name': tag_name,
                              'value': tag_value,
                              'updated': tag_is_updated(tag_name, tag_value, 'video')})

    return tags_on_video


def get_frames_tags(current_frame):
    tags_on_frame = []

    for current_tag in g.tags2stats.keys():
        for current_value in g.tags2stats[current_tag].keys():
            frames_list = g.tags2stats[current_tag][current_value].get('framesList', [])
            if current_frame in frames_list:
                tags_on_frame.append({'name': current_tag,
                                      'value': current_value,
                                      'updated': tag_is_updated(current_tag, current_value, current_frame)})

    return tags_on_frame


def create_sly_tag(updated_tag):
    created_tag = g.project_meta.get_tag_meta(updated_tag['name']).to_json()
    created_tag['value'] = updated_tag['selected_value']

    return created_tag


def remove_frame_index_locally(name, value, current_frame):
    frames_list = g.tags2stats[name][value]['framesList']
    safe_dict_value_append(g.updated_tags, current_frame, {'name': name,
                                                           'value': value})
    try:
        frame_index = frames_list.index(current_frame)
        g.tags2stats[name][value]['framesList'].pop(frame_index)

        annotated_frames_list = list(g.user_stats['annotated_frames'])
        annotated_frames_list.pop(current_frame)
        g.user_stats['annotated_frames'] = set(annotated_frames_list)

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
            'solo_button': init_solo_button()

        }


def add_frame_index_locally(name, value, current_frame):
    init_tag_locally(name, value)

    frames_list = set(g.tags2stats[name][value]['framesList'])
    frames_list.add(current_frame)
    g.tags2stats[name][value]['framesList'] = list(frames_list)

    g.user_stats['annotated_frames'].add(current_frame)
    safe_dict_value_append(g.updated_tags, current_frame, {'name': name,
                                                           'value': value})


def fill_available_tags_by_values(tab_content, tags_on_frame):
    for tag_on_frame in tags_on_frame:
        for tag_index, available_tag in enumerate(tab_content):
            if available_tag['name'] == tag_on_frame['name']:
                tab_content[tag_index]['updated'] = tag_on_frame['updated']
                if tag_on_frame.get('value', '') in available_tag['available_values']:
                    tab_content[tag_index]['selected_value'] = tag_on_frame['value']
                break


def update_video_tag_locally(updated_tag):
    if updated_tag['selected_value'] is not None:
        g.video_tags[updated_tag['name']] = updated_tag['selected_value']
        g.user_stats['tags_changed'].add(f'{updated_tag["name"]}:{updated_tag["selected_value"]}')

    else:
        g.video_tags[updated_tag['name']] = None
        g.user_stats['tags_removed'].add(f'{updated_tag["name"]}:{""}')

    safe_dict_value_append(g.updated_tags, 'video', {'name': updated_tag['name'],
                                                     'value': g.video_tags[updated_tag['name']]})


def process_updated_tag_locally(state):
    if state['updatedTag']['selected_value'] == '':
        state['updatedTag']['selected_value'] = None

    if state['tagType'] == 'frame':
        update_frame_tag_locally(state['currentFrame'], state['updatedTag'])

    if state['tagType'] == 'video':
        update_video_tag_locally(state['updatedTag'])


def update_frame_tag_locally(current_frame, updated_tag):
    tags_on_frame = get_frames_tags(current_frame)

    for tag_index, tag_on_frame in enumerate(tags_on_frame):
        if updated_tag['name'] == tag_on_frame['name']:
            remove_frame_index_locally(tag_on_frame['name'], tag_on_frame['value'], current_frame)
            if updated_tag['selected_value'] is not None:
                add_frame_index_locally(tag_on_frame['name'], updated_tag['selected_value'], current_frame)

                g.user_stats['tags_changed'].add(f'{tag_on_frame["name"]}:{current_frame}')
            else:
                safe_dict_value_append(g.updated_tags, current_frame, {'name': updated_tag['name'],
                                                                       'value': None})

                g.user_stats['tags_removed'].add(f'{tag_on_frame["name"]}:{current_frame}')
            break
    else:
        if updated_tag['selected_value'] is not None:
            add_frame_index_locally(updated_tag['name'], updated_tag['selected_value'], current_frame)

            g.user_stats['tags_created'].add(f'{updated_tag["name"]}:{current_frame}')


def get_tags_on_frame(tab_name, current_frame=0):
    tab_content = get_available_tags(current_frame)

    if tab_name == 'videos':  # VIDEOS
        state_name = 'tagsOnVideo'
        tags_on_card = get_video_tags()

    else:  # FRAMES
        state_name = 'tagsOnFrame'
        tags_on_card = get_frames_tags(current_frame)

    fill_available_tags_by_values(tab_content, tags_on_card)

    return tab_content, state_name


def update_tab_by_name(tab_name, current_frame=0):
    tab_content, state_name = get_tags_on_frame(tab_name, current_frame)
    g.api.app.set_field(g.task_id, f'state.{state_name}', tab_content)

    return tab_content


def update_user_stats(fields_to_update):
    fields_to_update['state.currentJobInfo.framesAnnotated'] = len(g.user_stats['annotated_frames'])
    fields_to_update['state.currentJobInfo.tagsCreated'] = len(g.user_stats['tags_created'])

    # fields_to_update[f'data.userStats["Frames Annotated"]'] = get_unsaved_tags_count()
    # fields_to_update[f'data.userStats["Tags Created"]'] = get_unsaved_tags_count()
    fields_to_update[f'data.userStats["Unsaved Tags"]'] = len(g.user_stats['tags_created'] |
                                                              g.user_stats['tags_changed'] |
                                                              g.user_stats['tags_removed'])


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
            'Time in Work': get_datetime_by_unix(response['user_stats'].get(UserStatsField.WORK_TIME_UNIX))
            if response['user_stats'].get(UserStatsField.WORK_TIME_UNIX) is not None else get_datetime_by_unix(0)
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


def update_tags_ranges_locally(updated_tags):
    for tag_name, tag_values in updated_tags.items():
        for tag_value in tag_values:
            try:
                frames_list = g.tags2stats[tag_name][tag_value].get('framesList')
                if frames_list is not None:
                    frames_list = sorted(frames_list)
                    get_frames_ranges_from_list(frames_list)
                    g.tags2stats[tag_name][tag_value]['frameRanges'] = get_frames_ranges_from_list(frames_list)
            except Exception:
                pass


def get_updated_tags_dict():
    updated_tags = {}

    for tag_point, updated_combinations in g.updated_tags.items():

        for updated_combination in updated_combinations:
            if updated_combination['value'] is not None:
                safe_dict_value_append(updated_tags, updated_combination['name'], updated_combination['value'])

    for updated_tag in updated_tags.keys():
        updated_tags[updated_tag] = list(set(updated_tags[updated_tag]))

    return updated_tags


def update_tags_on_timeline(fields_to_update):
    updated_tags = get_updated_tags_dict()
    update_tags_ranges_locally(updated_tags)
    tags_stats_in_table_form = tag_stats_to_table(g.tags2stats)
    fields_to_update['data.selectedTagsStats'] = tags_stats_in_table_form  # update tags

    updated_frames_indexes = [potential_frame_index for potential_frame_index in g.updated_tags.keys()
                              if type(potential_frame_index) == int]

    updated_tags_ranges = get_frames_ranges_from_list(sorted(list(updated_frames_indexes)))  # update changed tags line
    fields_to_update['state.updatedRanges'] = {
        'frameRanges': updated_tags_ranges,
        'colors': ["#f8ba29" for _ in range(len(updated_tags_ranges))]
    }


def reverse_ranges(frames_ranges, frames_count):
    all_frames = set([current_frame for current_frame in range(frames_count)])
    filled_frames = get_frames_list_from_ranges(frames_ranges)

    unfilled_frames = all_frames - set(filled_frames)
    return get_frames_ranges_from_list(unfilled_frames)


def get_ranges_to_play(solo_mode, tags_table):
    raw_ranges = []

    video_info = g.api.app.get_field(g.task_id, 'data.videoInfo')

    for row in tags_table:
        if row['solo_button']['stage'] == 1:  # tagged frames
            raw_ranges.append(get_frames_list_from_ranges(row['frameRanges']))
        elif row['solo_button']['stage'] == 2:  # untagged frames
            reversed_ranges = reverse_ranges(row['frameRanges'], video_info['frames_count'])
            raw_ranges.append(get_frames_list_from_ranges(reversed_ranges))

    if len(raw_ranges) == 0:
        return []

    if solo_mode == 'union':
        return get_frames_ranges_from_list(sorted(list(set(chain.from_iterable(raw_ranges)))))
    elif solo_mode == 'intersection':
        raw_ranges = list(map(set, raw_ranges))
        return get_frames_ranges_from_list(sorted(list(set.intersection(*raw_ranges))))
    else:
        return -1


def update_play_intervals_by_table(tags_table, play_mode, fields_to_update):
    ranges_to_play = get_ranges_to_play(play_mode, tags_table)
    fields_to_update[f'state.rangesToPlay'] = ranges_to_play if len(ranges_to_play) > 0 else None
    fields_to_update[f'state.videoPlayerOptions.intervalsNavigation'] = True if len(ranges_to_play) > 0 else False

