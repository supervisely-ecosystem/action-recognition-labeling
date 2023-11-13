import time
import datetime

from supervisely.video_annotation.video_tag import VideoTag
from supervisely.video_annotation.video_tag_collection import VideoTagCollection

from sly_fields_names import UserStatsField

import labeling_tool
import sly_globals as g
import sly_functions as f
import supervisely as sly


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
    data['selectedTagsStats'] = []

    state['showFinishDialog'] = False


def return_item_to_controller(context, state):
    data_to_send = get_general_data_to_send(context, state)

    response = g.api.task.send_request(g.controller_session_id, "return_item", data=data_to_send, timeout=10)

    return response


@g.my_app.callback("finish_labeling")
@sly.timeit
@g.update_fields
@g.my_app.ignore_errors_and_show_dialog_window()
def finish_labeling(api: sly.Api, task_id, context, state, app_logger, fields_to_update):
    fields_to_update['state.buttonsLoading.finishLabeling'] = False

    updated_tags = f.get_updated_tags_dict()
    f.update_tags_ranges_locally(updated_tags)

    update_job_stats(state, context, fields_to_update)
    upload_tags_to_supervisely(api, state['currentJobInfo']['videoId'], updated_tags)
    reset_local_fields(fields_to_update)

    response = return_item_to_controller(context, state)
    f.set_available_mods_by_response(response, fields_to_update)
    f.update_connected_data_by_response(response, fields_to_update)

    fields_to_update['state.currentJobInfo.isStarted'] = False


def get_video_from_controller(api, state, context, fields_to_update):
    annotation_controller_id = state['annControllerId']

    data_to_send = {
        'userId': context['userId'],
        'taskId': g.task_id,
        'mode': state['userMode']
    }

    response = api.task.send_request(annotation_controller_id, "get_item", data=data_to_send, timeout=10)

    if response["item_id"] is None:
        if state['userMode'] == 'annotator':
            g.my_app.show_modal_window("No videos in queue to annotate", "warning")
        elif state['userMode'] == 'reviewer':
            g.my_app.show_modal_window("No videos in queue to review", "warning")
        return False

    current_job_fields_to_update = {
        'isStarted': True,
        'startTime': time.time(),
        'videoId': response['item_id'],
        'annotationsUpdatedTime': f.get_current_time()
    }

    for item, value in current_job_fields_to_update.items():
        fields_to_update[f'state.currentJobInfo.{item}'] = value

    g.video_id = response['item_id']
    g.project_meta = sly.ProjectMeta.from_json(f.get_project_meta(api, g.video_id))
    return True


@g.my_app.callback("get_new_item")
@sly.timeit
@g.update_fields
@g.my_app.ignore_errors_and_show_dialog_window()
def get_new_item(api: sly.Api, task_id, context, state, app_logger, fields_to_update):
    fields_to_update['state.buttonsLoading.getItem'] = False

    has_videos_in_queue = get_video_from_controller(api, state, context, fields_to_update)  # call controller part
    if has_videos_in_queue:
        tags_on_frames = f.get_tags_list_by_type('frame', g.video_id)  # frames tags part
        g.tags2stats = f.get_tags_stats(tags_on_frames)

        tags_stats_in_table_form = f.tag_stats_to_table(g.tags2stats)
        fields_to_update['data.selectedTagsStats'] = tags_stats_in_table_form

        tags_on_video = f.get_tags_list_by_type('video', g.video_id)  # videos tags part
        g.video_tags = {current_tag['name']: current_tag['value'] for current_tag in tags_on_video}

        f.update_tab_by_name('frames')
        f.update_tab_by_name('videos')

        video_info = api.video.get_info_by_id(g.video_id)

        fields_to_update['data.videoInfo'] = {
            'frames_count': video_info.frames_count
        }
    else:
        fields_to_update['state.buttonsLoading.getItem'] = False

def get_frame_ranges_for_every_annotated_tag(annotated_tags):
    unique_names = list(set([current_tag['name'] for current_tag in annotated_tags]))
    tag_name2frames_ranges = {unique_name: {} for unique_name in unique_names}

    for current_tag in annotated_tags:
        current_tag_value = current_tag.get('value', None)
        if current_tag_value is None:
            continue

        current_tag_name = current_tag['name']
        frame_range = current_tag.get('frameRange', None)

        if frame_range is not None:
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


def get_annotated_tag_id(annotated_tags, tag_name, tag_value, frame_range=None):
    for current_tag in annotated_tags:
        current_tag_value = current_tag.get('value', None)
        if current_tag_value is None:
            continue

        current_tag_name = current_tag['name']
        tag_frame_range = current_tag.get('frameRange', None)

        if frame_range is not None:
            if current_tag_name == tag_name and current_tag_value == tag_value and frame_range == tag_frame_range:
                return current_tag['id']
        else:
            if current_tag_name == tag_name:
                return current_tag['id']

    return None


def filter_tags_by_status(status, remote_tags_frames, remote_tags_video, new_tags):
    filtered_tags = []

    tag_frame_ranges = get_frame_ranges_for_every_annotated_tag(
        remote_tags_frames)  # {tag1: {value1: [[]], value2: [[]], ..}, ..}

    for new_tag in new_tags:
        new_tag_json = new_tag.to_json()
        tag_name = new_tag_json.get('name')
        tag_value = new_tag_json.get('value')
        new_tag_frame_range = new_tag_json.get('frameRange', None)
        if new_tag_frame_range is not None:  # FRAMES TAGS
            old_tag_frame_ranges = tag_frame_ranges.get(tag_name, {}).get(tag_value, [])
            if status == 'append':
                if not ranges_intersected([new_tag_frame_range], old_tag_frame_ranges) and new_tag_frame_range != [-1,
                                                                                                                   -1]:
                    filtered_tags.append(new_tag)
            elif status == 'update':
                if ranges_intersected([new_tag_frame_range],
                                      old_tag_frame_ranges) and new_tag_frame_range not in old_tag_frame_ranges:
                    filtered_tags.append(new_tag)
        else:  # VIDEO TAGS
            tag_id = get_annotated_tag_id(remote_tags_video, tag_name, tag_value)
            if tag_id is not None and status == 'update':
                filtered_tags.append(new_tag)
            elif tag_id is None and status == 'append':
                filtered_tags.append(new_tag)

    return filtered_tags


def get_existing_tag_id(current_tag, tag_frame_range=None):
    frame_ranges = current_tag['frameRanges']
    ids = current_tag['ids']

    for frame_range, tag_id in zip(frame_ranges, ids):
        if ranges_intersected([tag_frame_range], [frame_range]):
            return tag_id
    else:
        return None


def update_tag_frame_range_by_id_locally(current_tag, tag_id, new_tag_frame_range):
    if tag_id in current_tag['ids'] and tag_id != -1:
        index = current_tag['ids'].index(tag_id)
        current_tag['frameRanges'][index] = new_tag_frame_range
    else:
        current_tag['ids'].append(-1)
        current_tag['frameRanges'].append(new_tag_frame_range)


def renew_tags_by_status(api, video_id, status, tags_to_upload):
    if len(tags_to_upload) == 0:
        return -1

    if status == 'append':
        tags_collection = VideoTagCollection(tags_to_upload)
        video_info = g.api.video.get_info_by_id(video_id)
        video_ann = sly.VideoAnnotation((video_info.frame_height, video_info.frame_width),
                                        frames_count=video_info.frames_count, tags=tags_collection)
        api.video.annotation.append(video_id, video_ann)

    elif status == 'update':
        tags_on_frames = f.get_tags_list_by_type('frame', g.video_id)
        tags_on_video = f.get_tags_list_by_type('video', g.video_id)

        remote_tags_frames = f.get_tags_stats(tags_on_frames)
        # remote_tags_video = f.get_tags_stats(tags_on_video)

        for tag_to_upload in tags_to_upload:
            tag_to_upload_json = tag_to_upload.to_json()
            tag_name = tag_to_upload_json.get('name')
            tag_value = tag_to_upload_json.get('value')
            new_tag_frame_range = tag_to_upload_json.get('frameRange', None)

            if new_tag_frame_range is not None:  # FRAME TAGS
                current_tag = remote_tags_frames[tag_name][tag_value]
                tag_id = get_existing_tag_id(current_tag, new_tag_frame_range)
                if tag_id is not None:
                    api.video.tag.update_frame_range(tag_id=tag_id, frame_range=new_tag_frame_range)
                    update_tag_frame_range_by_id_locally(current_tag, tag_id, new_tag_frame_range)

                else:
                    meta_tag_id = g.project_meta.get_tag_meta(tag_name=tag_name).to_json()['id']
                    api.video.tag.add_tag(
                        project_meta_tag_id=meta_tag_id,
                        video_id=g.video_id,
                        value=tag_value,
                        frame_range=new_tag_frame_range
                    )
                    update_tag_frame_range_by_id_locally(current_tag, -1, new_tag_frame_range)

            else:  # VIDEO TAGS
                tag_id = get_annotated_tag_id(tags_on_video, tag_name, tag_value)
                api.video.tag.update_value(tag_id=tag_id, tag_value=tag_value)  # update tag value

    elif status == 'remove':
        for remote_tag_id in tags_to_upload:
            api.video.tag.remove_from_video(tag_id=remote_tag_id)


def get_tags_to_process(updated_tags):
    tags_to_process = []

    for tag_name, tag_values in updated_tags.items():
        for tag_value in tag_values:
            try:
                tag_frames_ranges = g.tags2stats[tag_name][tag_value]['frameRanges']
                if tag_frames_ranges is not None:  # FRAME TAGS
                    tag_meta = g.project_meta.get_tag_meta(tag_name)

                    if len(tag_frames_ranges) == 0:
                        tags_to_process.append(
                            VideoTag(tag_meta, value=tag_value, frame_range=[-1, -1]))  # signal to remove

                    for current_frames_range in tag_frames_ranges:
                        tags_to_process.append(VideoTag(tag_meta, value=tag_value, frame_range=current_frames_range))
            except Exception:
                pass

            video_tag_value = g.video_tags.get(tag_name, '')
            if video_tag_value != '':  # VIDEO TAGS
                tag_meta = g.project_meta.get_tag_meta(tag_name)
                tags_to_process.append(VideoTag(tag_meta, value=tag_value, frame_range=None))

    return tags_to_process


def remove_existing_ids(remote_tags_frames, remote_tags_video, tags_to_process):
    for current_tag in tags_to_process:
        if current_tag.frame_range != [-1, -1]:
            try:
                if current_tag.frame_range is not None:  # FRAMES TAGS
                    index = remote_tags_frames[current_tag.name][current_tag.value]['frameRanges'].index(
                        current_tag.frame_range)
                    remote_tags_frames[current_tag.name][current_tag.value]['frameRanges'].pop(index)
                    remote_tags_frames[current_tag.name][current_tag.value]['ids'].pop(index)

                else:  # VIDEO TAGS
                    remote_tags_video[current_tag.name][current_tag.value]['ids'].pop()
            except Exception:
                pass


def collect_ids_to_remove(remote_tags, ids_to_remove):
    for current_tag_values in remote_tags.values():
        for current_tag in current_tag_values.values():
            ids_to_remove.extend(current_tag['ids'])


def filter_by_tags_to_process(remote_tags_frames, remote_tags_video, tags_to_process):
    filtered_frames_tags = {key: {} for key in remote_tags_frames.keys()}
    filtered_videos_tags = {key: {} for key in remote_tags_video.keys()}

    for current_tag in tags_to_process:
        if current_tag.frame_range is not None:  # FRAMES TAGS
            try:
                filtered_frames_tags[current_tag.name][current_tag.value] = remote_tags_frames[current_tag.name][
                    current_tag.value]
            except Exception as ex:  # DEBUG
                sly.logger.warning(ex)

    updated_video_tags = g.updated_tags.get('video', [])
    for current_tag in updated_video_tags:
        remote_tags = remote_tags_video.get(current_tag['name'], None)
        if remote_tags is not None:
            for remote_tag_value in remote_tags.keys():
                filtered_videos_tags[current_tag['name']][remote_tag_value] = remote_tags_video[current_tag['name']][
                    remote_tag_value]

    return filtered_frames_tags, filtered_videos_tags


def get_remote_tags():
    tags_on_frames = f.get_tags_list_by_type('frame', g.video_id)
    tags_on_video = f.get_tags_list_by_type('video', g.video_id)

    remote_tags_frames = f.get_tags_stats(tags_on_frames)
    remote_tags_video = f.get_tags_stats(tags_on_video)

    return remote_tags_frames, remote_tags_video


def get_tags_to_remove(tags_to_process):
    tags_ids_to_remove = []

    remote_tags_frames, remote_tags_video = get_remote_tags()

    remote_tags_frames, remote_tags_video = filter_by_tags_to_process(remote_tags_frames, remote_tags_video,
                                                                      tags_to_process)
    remove_existing_ids(remote_tags_frames, remote_tags_video, tags_to_process)

    collect_ids_to_remove(remote_tags_frames, tags_ids_to_remove)
    collect_ids_to_remove(remote_tags_video, tags_ids_to_remove)

    return tags_ids_to_remove


def upload_frame_tags(api, video_id, updated_tags):
    tags_to_process = get_tags_to_process(updated_tags)

    if len(tags_to_process) > 0:
        tags_on_frames = f.get_tags_list_by_type('frame', g.video_id)
        tags_on_video = f.get_tags_list_by_type('video', g.video_id)

        tags_to_append = filter_tags_by_status(status='append', remote_tags_frames=tags_on_frames,
                                               remote_tags_video=tags_on_video,
                                               new_tags=tags_to_process)
        tags_to_update = filter_tags_by_status(status='update', remote_tags_frames=tags_on_frames,
                                               remote_tags_video=tags_on_video,
                                               new_tags=tags_to_process)

        renew_tags_by_status(api, video_id, 'append', tags_to_append)
        renew_tags_by_status(api, video_id, 'update', tags_to_update)

    tags_ids_to_remove = get_tags_to_remove(tags_to_process)
    renew_tags_by_status(api, video_id, 'remove', tags_ids_to_remove)


def upload_tags_to_supervisely(api, video_id, updated_tags):
    upload_frame_tags(api, video_id, updated_tags)


def convert_datetime_time_to_unix(datetime_time):
    init_date = datetime.datetime(1900, 1, 1, 00, 00)
    current_date = datetime.datetime.strptime(datetime_time, '%H:%M:%S')

    return round((current_date - init_date).total_seconds())


def get_updated_user_stats(state):
    old_user_stats = g.api.task.get_field(task_id=g.task_id, field='data.userStats')

    time_in_work = time.time() - state['currentJobInfo']['startTime']
    unix_time_in_work = time_in_work + convert_datetime_time_to_unix(old_user_stats.get("Time in Work", "00:00:00"))

    user_stats = {
        'Frames Annotated': state['currentJobInfo']['framesAnnotated'] + old_user_stats.get('Frames Annotated', 0),
        'Tags Created': state['currentJobInfo']['tagsCreated'] + old_user_stats.get('Tags Created', 0),
        'Time in Work': f'{f.get_datetime_by_unix(unix_time_in_work)}'
    }

    return user_stats


def update_user_stats_remotely(user_stats, fields_to_update):
    for key, value in user_stats.items():
        fields_to_update[f'data.userStats.{key}'] = value


def get_user_data_to_send(state, user_stats):
    old_user_stats = g.api.task.get_field(task_id=g.task_id, field='data.userStats')
    time_in_work = time.time() - state['currentJobInfo']['startTime']
    unix_time_in_work = time_in_work + convert_datetime_time_to_unix(old_user_stats.get("Time in Work", "00:00:00"))

    return {'user_fields': {
        UserStatsField.FRAMES_ANNOTATED: user_stats['Frames Annotated'],
        UserStatsField.TAGS_CREATED: user_stats['Tags Created'],
        UserStatsField.WORK_TIME_UNIX: unix_time_in_work,
        UserStatsField.WORK_TIME: f.get_datetime_by_unix(unix_time_in_work)
    }}


def get_item_data_to_send(state, user_stats):
    return {'item_fields': {
    }}


def get_general_data_to_send(context, state):
    data_to_send = {
        'userId': context['userId'],
        'taskId': g.task_id,
        'mode': state['userMode'],
    }

    return data_to_send


def update_job_stats(state, context, fields_to_update):
    fields_to_update['state.currentJobInfo.annotationsUpdatedTime'] = f.get_current_time()

    user_stats = get_updated_user_stats(state)
    update_user_stats_remotely(user_stats, fields_to_update)

    data_to_send = get_general_data_to_send(context, state)
    data_to_send.update(get_user_data_to_send(state, user_stats))
    data_to_send.update(get_item_data_to_send(state, user_stats))

    response = g.api.task.send_request(g.controller_session_id, "update_stats", data=data_to_send, timeout=10)


def reset_local_fields(fields_to_update):
    g.updated_tags = {}
    g.user_stats.update({
        'tags_created': set(),
        'tags_removed': set(),
        'tags_changed': set(),
    })

    fields_to_update[f'data.userStats["Unsaved Tags"]'] = 0


@g.my_app.callback("save_annotations_manually")
@sly.timeit
@g.update_fields
# @g.my_app.ignore_errors_and_show_dialog_window()
def save_annotations_manually(api: sly.Api, task_id, context, state, app_logger, fields_to_update):
    fields_to_update['state.buttonsLoading.saveAnn'] = False

    updated_tags = f.get_updated_tags_dict()
    f.update_tags_ranges_locally(updated_tags)

    update_job_stats(state, context, fields_to_update)
    upload_tags_to_supervisely(api, state['currentJobInfo']['videoId'], updated_tags)

    tags_on_frames = f.get_tags_list_by_type('frame', g.video_id)  # update tags on timeline
    g.tags2stats = f.get_tags_stats(tags_on_frames)

    reset_local_fields(fields_to_update)

    for current_tab_name in ['frames', 'videos']:
        f.update_tab_by_name(current_tab_name, current_frame=state['currentFrame'])

    f.update_tags_on_timeline(fields_to_update)
