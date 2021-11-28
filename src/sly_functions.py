import datetime
from string import Formatter

import sly_globals as g
from sly_fields_names import ItemsStatusField

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


def get_available_tags(api, video_id):
    project_meta = get_project_meta(api, video_id)  # use to unpack available tags
    return project_meta.get('tags', [])


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
        if current_tag.get('name') in g.technical_tags_names: # DEBUG
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


def format_tags_on_frames_to_stats(tags2stats, tags_on_frames):
    for current_tag in tags_on_frames:
        tag_id = current_tag.get('id')
        name = current_tag.get('name')
        value = current_tag.get('value')
        frame_range = current_tag.get('frameRange')

        if name and value is not None and frame_range is not None:
            tags_values = tags2stats.get(name, {})

            tag_value_stats = tags_values.get(value, {})

            tag_color = g.project_meta.get_tag_meta(current_tag['name']).to_json()['color']

            safe_dict_value_append(tag_value_stats, 'ids', tag_id)  # updating ids
            safe_dict_value_append(tag_value_stats, 'frameRanges', frame_range)  # updating frame range
            safe_dict_value_append(tag_value_stats, 'colors', tag_color)  # updating colors

            tags_values[value] = tag_value_stats
            tags2stats[name] = tags_values

    for current_tag in tags2stats.keys():
        for current_value in tags2stats[current_tag].keys():
            frames_ranges = tags2stats[current_tag][current_value].get('frameRanges', [])
            tags2stats[current_tag][current_value]['framesList'] = frame_ranges_to_list(frames_ranges)


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


def get_unsaved_tags_count():
    counter = 0
    for value in g.updated_tags.values():
        counter += len(value)
    return counter


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

