import ast
import json
import time
import datetime

from supervisely_lib.video_annotation.video_tag import VideoTag
from supervisely_lib.video_annotation.video_tag_collection import VideoTagCollection

from sly_fields_names import UserStatsField

import labeling_tool
import sly_globals as g
import sly_functions as f
import supervisely_lib as sly


def init_fields(state, data):
    state['currentJobInfo'] = {
        'isStarted': False,
        'startTime': None,
        # 'videoId': 1116678,
        'videoId': None,
        'annotationsUpdatedTime': '-',
        'framesAnnotated': 0,
        'tagsCreated': 0
    }

    data['videoInfo'] = None


def get_annotations_data(api, video_id):
    g.available_tags = f.get_available_tags(api, video_id)
    g.tags_on_video = f.get_tags_on_video(api, video_id)
    g.project_meta = sly.ProjectMeta.from_json(f.get_project_meta(api, video_id))


@g.my_app.callback("finish_labeling")
@sly.timeit
@g.update_fields
@g.my_app.ignore_errors_and_show_dialog_window()
def finish_labeling(api: sly.Api, task_id, context, state, app_logger, fields_to_update):
    fields_to_update['state.buttonsLoading.finishLabeling'] = False

    # data_to_send = {  # sending data to controller
    #     'userId': context['userId'],
    #     'taskId': g.task_id,
    #     'mode': state['userMode'],
    #
    #     'item_fields': {},
    #     'user_fields': {
    #
    #     }
    # }
    #
    # response = g.api.task.send_request(g.controller_session_id, "update_stats", data=data_to_send, timeout=3)



@g.my_app.callback("get_new_item")
@sly.timeit
@g.update_fields
@g.my_app.ignore_errors_and_show_dialog_window()
def get_new_item(api: sly.Api, task_id, context, state, app_logger, fields_to_update):
    fields_to_update['state.buttonsLoading.getItem'] = False

    annotation_controller_id = state['annControllerId']

    data_to_send = {
        'userId': context['userId'],
        'taskId': g.task_id,
        'mode': state['userMode']
    }

    response = api.task.send_request(annotation_controller_id, "get_item", data=data_to_send, timeout=3)

    current_job_fields_to_update = {
        'isStarted': True,
        'startTime': time.time(),
        'videoId': response['item_id'],
        'annotationsUpdatedTime': f.get_current_time()
    }

    for item, value in current_job_fields_to_update.items():
        fields_to_update[f'state.currentJobInfo.{item}'] = value

    get_annotations_data(api, response['item_id'])

    labeling_tool.update_tab_by_name('frames')
    labeling_tool.update_tab_by_name('videos')

    fields_to_update['data.videoInfo'] = api.video.get_info_by_id(response['item_id'])


def get_frame_ranges_by_tag_name_and_value(tag_name, tag_value):
    frame_ranges = []

    first_frame_in_range = None
    prev_frame_index = -1

    for frame_index, tags_on_frame in g.tags_on_video['frames'].items():
        for current_tag in tags_on_frame:
            if current_tag['name'] == tag_name and current_tag['value'] == tag_value:
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


def get_frame_ranges_for_every_annotated_tag(annotated_tags):
    unique_names = list(set([current_tag['name'] for current_tag in annotated_tags]))
    tag_name2frames_ranges = {unique_name: {} for unique_name in unique_names}

    for current_tag in annotated_tags:
        current_tag_value = current_tag.get('value', None)
        if current_tag_value is None:
            continue

        current_tag_name = current_tag['name']
        frame_range = current_tag.get('frameRange', None)

        if frame_range:
            frame_ranges = tag_name2frames_ranges[current_tag_name].get(current_tag_value, [])
            frame_ranges.append(frame_range)
            tag_name2frames_ranges[current_tag_name][current_tag_value] = frame_ranges
        else:
            frame_ranges = tag_name2frames_ranges[current_tag_name].get(current_tag_value, [])
            tag_name2frames_ranges[current_tag_name][current_tag_value] = frame_ranges

    return tag_name2frames_ranges


def ranges_intersected(ranges1, ranges2):
    for current_range1 in ranges1:
        for current_range2 in ranges2:
            if current_range2[0] <= current_range1[0] <= current_range2[1]:
                return True
            if current_range2[0] <= current_range1[1] <= current_range2[1]:
                return True

    return False


def filter_tags_by_status(status, video_annotations, new_tags):
    filtered_tags = []
    tags_on_video = video_annotations.get('tags', [])
    tag_frame_ranges = get_frame_ranges_for_every_annotated_tag(
        tags_on_video)  # {tag1: {value1: [[]], value2: [[]], ..}, ..}

    intersection_flag = True
    if status == 'append':
        intersection_flag = False

    elif status == 'update':
        intersection_flag = True

    for new_tag in new_tags:
        new_tag_json = new_tag.to_json()
        tag_name = new_tag_json.get('name')
        tag_value = new_tag_json.get('value')
        tag_frame_range = new_tag_json.get('frameRange', None)
        if tag_frame_range:
            if ranges_intersected([tag_frame_range],
                                  tag_frame_ranges.get(tag_name, {}).get(tag_value, [])) == intersection_flag:
                filtered_tags.append(new_tag)

    return filtered_tags


def get_existing_tag_id(tags_on_video, tag_name, tag_value, tag_frame_range=None):
    for tag_on_video in tags_on_video:
        frame_range = tag_on_video.get('frameRange', None)

        if tag_on_video.get('name', '') == tag_name and tag_on_video.get('value', '') == tag_value:

            if frame_range and tag_frame_range:
                if ranges_intersected([tag_frame_range], [frame_range]):
                    return tag_on_video['id']
            else:
                return tag_on_video['id']

    return -1


def upload_tags_by_status(api, video_id, status, tags_to_upload, video_annotations=None):
    if len(tags_to_upload) == 0:
        return -1

    if status == 'append':
        tags_collection = VideoTagCollection(tags_to_upload)
        video_info = g.api.video.get_info_by_id(video_id)
        video_ann = sly.VideoAnnotation((video_info.frame_height, video_info.frame_width),
                                        frames_count=video_info.frames_count, tags=tags_collection)
        api.video.annotation.append(video_id, video_ann)

    elif status == 'update':
        tags_on_video = video_annotations.get('tags', [])

        for tag_to_upload in tags_to_upload:
            tag_to_upload_json = tag_to_upload.to_json()
            tag_name = tag_to_upload_json.get('name')
            tag_value = tag_to_upload_json.get('value')
            tag_frame_range = tag_to_upload_json.get('frameRange', None)

            if tag_frame_range:
                tag_id = get_existing_tag_id(tags_on_video, tag_name, tag_value, tag_frame_range)
                if tag_id != -1:
                    api.video.tag.update_value(tag_id=tag_id, tag_value=tag_value)  # update tag value
                    api.video.tag.update_frame_range(tag_id=tag_id, frame_range=tag_frame_range)

            else:
                tag_id = get_existing_tag_id(tags_on_video, tag_name, tag_value)
                if tag_id != -1:
                    api.video.tag.update_value(tag_id=tag_id, tag_value=tag_value)  # update tag value


def upload_frames_tags_to_video(api, video_id):
    video_tags = []

    for current_tag in g.available_tags:
        for current_value in current_tag.get('values', []):
            tag_frames_ranges = get_frame_ranges_by_tag_name_and_value(current_tag['name'], current_value)

            if len(tag_frames_ranges) > 0:
                g.tag_frame_ranges[f'{current_tag["name"]}: {current_value}'] = {
                        'color': [current_tag['color'] for _ in range(len(tag_frames_ranges))],
                        'ranges': tag_frames_ranges
                    }  # temporal

            for current_frames_range in tag_frames_ranges:
                tag_meta = g.project_meta.get_tag_meta(current_tag['name'])
                video_tags.append(VideoTag(tag_meta, value=current_value, frame_range=current_frames_range))

    if len(video_tags) > 0:
        video_annotations = api.video.annotation.download(video_id)
        tags_to_append = filter_tags_by_status(status='append', video_annotations=video_annotations,
                                               new_tags=video_tags)
        tags_to_update = filter_tags_by_status(status='update', video_annotations=video_annotations,
                                               new_tags=video_tags)

        upload_tags_by_status(api, video_id, 'append', tags_to_append)
        upload_tags_by_status(api, video_id, 'update', tags_to_update, video_annotations)


def convert_datetime_time_to_unix(datetime_time):
    init_date = datetime.datetime(1900, 1, 1, 00, 00)
    current_date = datetime.datetime.strptime(datetime_time, '%H:%M:%S')

    return round((current_date - init_date).total_seconds())


@g.my_app.callback("save_annotations_manually")
@sly.timeit
@g.update_fields
@g.my_app.ignore_errors_and_show_dialog_window()
def save_annotations_manually(api: sly.Api, task_id, context, state, app_logger, fields_to_update):
    fields_to_update['state.buttonsLoading.saveAnn'] = False

    current_job_info = state['currentJobInfo']
    current_job_info['annotationsUpdatedTime'] = f.get_current_time()

    upload_frames_tags_to_video(api, current_job_info['videoId'])

    fields_to_update['state.currentJobInfo'] = current_job_info

    old_user_stats = g.api.task.get_field(task_id=task_id, field='data.userStats')

    time_in_work = time.time() - state['currentJobInfo']['startTime']
    unix_time_in_work = time_in_work + convert_datetime_time_to_unix(old_user_stats.get("Time in Work", "00:00:00"))

    user_stats = {
        'Frames Annotated': state['currentJobInfo']['framesAnnotated'] + old_user_stats.get('Frames Annotated', 0),
        'Tags Created': state['currentJobInfo']['tagsCreated'] + old_user_stats.get('Tags Created', 0),
        'Time in Work': f'{f.get_datetime_by_unix(unix_time_in_work)}'
    }

    for key, value in user_stats.items():
        fields_to_update[f'data.userStats.{key}'] = value

    data_to_send = {  # sending data to controller
        'userId': context['userId'],
        'taskId': g.task_id,
        'mode': state['userMode'],

        'item_fields': {},
        'user_fields': {
            UserStatsField.FRAMES_ANNOTATED: user_stats['Frames Annotated'],
            UserStatsField.TAGS_CREATED: user_stats['Tags Created'],
            UserStatsField.WORK_TIME: unix_time_in_work
        }
    }

    response = g.api.task.send_request(g.controller_session_id, "update_stats", data=data_to_send, timeout=3)

    fields_to_update['data.timelineTags'] = g.tag_frame_ranges


