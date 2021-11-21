import supervisely_lib as sly
import sly_globals as g

import connect_to_controller


@sly.timeit
def init(state, data):

    connect_to_controller.init_fields(state=state, data=data)





