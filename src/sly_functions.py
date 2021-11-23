import datetime
from string import Formatter

import sly_globals as g

from sly_fields_names import ItemsStatusField


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
