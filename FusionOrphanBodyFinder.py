import adsk.core
import adsk.fusion
import traceback
import json
import os

_app = None
_ui = None
_handlers = []
_active_panel_id = None
_custom_panel_id = None

CMD_ID = 'FusionOrphanBodyFinderCmd'
CMD_NAME = 'Find Orphan Bodies'
CMD_DESCRIPTION = 'Find components that contain both subcomponents and direct bodies, and optionally move orphan bodies into new subcomponents.'
PANEL_ID = 'InspectPanel'
FALLBACK_PANEL_ID = 'SolidScriptsAddinsPanel'

WORKSPACE_ID = 'FusionSolidEnvironment'
TAB_ID = 'SolidTab'


def load_config():
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def get_or_create_custom_panel(panel_id, panel_name):
    try:
        workspace = _ui.workspaces.itemById(WORKSPACE_ID)
        if not workspace:
            return None
        tab = workspace.toolbarTabs.itemById(TAB_ID)
        if not tab:
            return None
        panel = tab.toolbarPanels.itemById(panel_id)
        if not panel:
            panel = tab.toolbarPanels.add(panel_id, panel_name)
        return panel
    except:
        return None


def run(context):
    global _app, _ui, _active_panel_id, _custom_panel_id
    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface
        config = load_config()

        cmd_def = _ui.commandDefinitions.itemById(CMD_ID)
        if cmd_def:
            cmd_def.deleteMe()

        resource_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources')
        cmd_def = _ui.commandDefinitions.addButtonDefinition(
            CMD_ID, CMD_NAME, CMD_DESCRIPTION, resource_dir
        )

        on_created = CommandCreatedHandler()
        cmd_def.commandCreated.add(on_created)
        _handlers.append(on_created)

        panel = None
        if config.get('use_custom_panel'):
            panel_id = config.get('panel_id', 'ErikBuildPlugins_Panel')
            panel_name = config.get('panel_name', 'ERIKBUILD PLUGINS')
            _custom_panel_id = panel_id
            panel = get_or_create_custom_panel(panel_id, panel_name)

        if not panel:
            panel = _ui.allToolbarPanels.itemById(PANEL_ID)
        if not panel:
            panel = _ui.allToolbarPanels.itemById(FALLBACK_PANEL_ID)

        if panel:
            _active_panel_id = panel.id
            existing = panel.controls.itemById(CMD_ID)
            if not existing:
                panel.controls.addCommand(cmd_def)

    except:
        if _ui:
            _ui.messageBox('Failed to start FusionOrphanBodyFinder:\n{}'.format(traceback.format_exc()))


def stop(context):
    global _handlers, _active_panel_id, _custom_panel_id
    try:
        if _active_panel_id:
            panel = _ui.allToolbarPanels.itemById(_active_panel_id)
            if panel:
                ctrl = panel.controls.itemById(CMD_ID)
                if ctrl:
                    ctrl.deleteMe()
                # Remove the custom panel if no controls remain
                if _custom_panel_id and _active_panel_id == _custom_panel_id and panel.controls.count == 0:
                    panel.deleteMe()
            _active_panel_id = None
            _custom_panel_id = None

        cmd_def = _ui.commandDefinitions.itemById(CMD_ID)
        if cmd_def:
            cmd_def.deleteMe()

        _handlers = []

    except:
        if _ui:
            _ui.messageBox('Failed to stop FusionOrphanBodyFinder:\n{}'.format(traceback.format_exc()))


class CommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            cmd = args.command
            inputs = cmd.commandInputs
            inputs.addBoolValueInput('includeRoot', 'Include Root Component', True, '', True)

            on_execute = ExecuteHandler()
            cmd.execute.add(on_execute)
            _handlers.append(on_execute)
        except:
            _ui.messageBox('CommandCreated failed:\n{}'.format(traceback.format_exc()))


class ExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            cmd = args.command
            inputs = cmd.commandInputs
            include_root = inputs.itemById('includeRoot').value

            design = adsk.fusion.Design.cast(_app.activeProduct)
            if not design:
                _ui.messageBox('No active Fusion design. Please open a design first.')
                return

            root_comp = design.rootComponent
            orphans = find_orphan_components(root_comp, include_root)

            if not orphans:
                _ui.messageBox('No orphan bodies found.')
                return

            total_bodies_moved = 0
            total_components_fixed = 0

            cancelled = False
            for entry in orphans:
                comp = entry['component']
                occ = entry['occurrence']
                body_names = entry['body_names']
                body_count = entry['body_count']

                if occ:
                    highlight_component(occ)

                msg = "Component '{}' contains {} orphan bod{}:\n[{}]\n\nMove to new subcomponents?".format(
                    comp.name,
                    body_count,
                    'y' if body_count == 1 else 'ies',
                    ', '.join(body_names)
                )

                result = _ui.messageBox(
                    msg, 'Orphan Bodies Found',
                    adsk.core.MessageBoxButtonTypes.YesNoCancelButtonType,
                    adsk.core.MessageBoxIconTypes.QuestionIconType
                )

                if result == adsk.core.DialogResults.DialogCancel:
                    cancelled = True
                    break

                if result == adsk.core.DialogResults.DialogYes:
                    moved = fix_component(comp, occ)
                    total_bodies_moved += moved
                    if moved > 0:
                        total_components_fixed += 1

            _ui.activeSelections.clear()

            if total_bodies_moved > 0:
                _ui.messageBox('Done. Moved {} bod{} across {} component{}.'.format(
                    total_bodies_moved,
                    'y' if total_bodies_moved == 1 else 'ies',
                    total_components_fixed,
                    '' if total_components_fixed == 1 else 's'
                ))
            else:
                _ui.messageBox('No bodies were moved.')

        except:
            _ui.messageBox('Execute failed:\n{}'.format(traceback.format_exc()))


def find_orphan_components(root_comp, include_root):
    results = []
    seen_tokens = set()

    if include_root:
        if root_comp.bRepBodies.count > 0 and root_comp.occurrences.count > 0:
            body_names = [body.name for body in root_comp.bRepBodies]
            results.append({
                'component': root_comp,
                'occurrence': None,
                'body_count': root_comp.bRepBodies.count,
                'body_names': body_names,
                'child_count': root_comp.occurrences.count,
            })

    for occ in root_comp.allOccurrences:
        comp = occ.component
        token = comp.entityToken
        if token in seen_tokens:
            continue
        seen_tokens.add(token)

        if comp.bRepBodies.count > 0 and comp.occurrences.count > 0:
            body_names = [body.name for body in comp.bRepBodies]
            results.append({
                'component': comp,
                'occurrence': occ,
                'body_count': comp.bRepBodies.count,
                'body_names': body_names,
                'child_count': comp.occurrences.count,
            })

    return results


def fix_component(component, occurrence):
    moved = 0
    bodies_to_move = list(component.bRepBodies)

    for body in bodies_to_move:
        ret_val, cancelled = _ui.inputBox(
            "Component '{}'\nBody '{}'\n\nEnter name for new component:".format(
                component.name, body.name),
            'Rename Body', component.name
        )
        if cancelled:
            continue

        new_name = ret_val.strip()
        if not new_name:
            new_name = body.name

        body.name = new_name
        transform = adsk.core.Matrix3D.create()
        new_occ = component.occurrences.addNewComponent(transform)
        new_occ.component.name = new_name
        body.moveToComponent(new_occ)
        moved += 1

    return moved


def highlight_component(occurrence):
    _ui.activeSelections.clear()
    _ui.activeSelections.add(occurrence)
