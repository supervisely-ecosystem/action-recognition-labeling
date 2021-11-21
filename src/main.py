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


#  @TODO: publish API method video.add_tag
#  @TODO: publish update_fields decorator

if __name__ == "__main__":
    sly.main_wrapper("main", main)
