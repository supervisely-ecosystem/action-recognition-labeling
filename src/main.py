import supervisely_lib as sly
import ui as ui

import sly_globals as g
import sly_functions as f


def main():
    sly.logger.info("Script arguments", extra={
        "context.teamId": g.team_id,
        "context.workspaceId": g.workspace_id
    })

    g.my_app.compile_template(g.root_source_dir)

    data = {}
    state = {}

    ui.init(data=data, state=state)  # init data for UI widgets

    g.my_app.run(data=data, state=state)


@g.my_app.callback("is_online")
@sly.timeit
@g.update_fields
def is_online(api: sly.Api, task_id, context, state, app_logger, fields_to_update):
    try:
        request_id = context["request_id"]
        g.my_app.send_response(request_id, data={})
    except:
        pass


if __name__ == "__main__":
    sly.main_wrapper("main", main)
