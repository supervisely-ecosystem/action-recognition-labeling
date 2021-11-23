import datetime

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
