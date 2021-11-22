import supervisely_lib as sly
import sly_globals as g

import connect_to_controller
import control_board
import video_player


@sly.timeit
def init(state, data):

    connect_to_controller.init_fields(state=state, data=data)
    control_board.init_fields(state=state, data=data)
    video_player.init_fields(state=state, data=data)





