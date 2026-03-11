import adsk.core
import adsk.fusion
import traceback
import json
import os
import re

_app = None
_ui = None
_handlers = []
_active_panel_id = None
_custom_panel_id = None

CMD_ID = 'FusionTidyCmd'
CMD_NAME = 'FusionTidy'
CMD_DESCRIPTION = 'Structural cleanup tools: find orphan bodies, clean .step suffixes, strip special characters, and remove version numbers from names.'
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
                ctrl = panel.controls.addCommand(cmd_def)
                ctrl.isPromotedByDefault = True
                ctrl.isPromoted = True

    except:
        if _ui:
            _ui.messageBox('Failed to start FusionTidy:\n{}'.format(traceback.format_exc()))


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
            _ui.messageBox('Failed to stop FusionTidy:\n{}'.format(traceback.format_exc()))


class CommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            cmd = args.command
            inputs = cmd.commandInputs
            orphan_group = inputs.addGroupCommandInput('orphanGroup', 'Orphan Bodies')
            orphan_group.children.addBoolValueInput('findOrphans', 'Find Orphan Bodies', True, '', True)
            orphan_group.children.addBoolValueInput('includeRoot', 'Include Root Component', True, '', True)

            cleanup_group = inputs.addGroupCommandInput('cleanupGroup', 'Name Cleanup')
            cleanup_group.children.addBoolValueInput('cleanStepNames', 'Clean .step from names', True, '', False)
            cleanup_group.children.addTextBoxCommandInput('stepExample', '', '<i>Bracket.STEP (1)</i> &rarr; <i>Bracket (1)</i>', 1, True)
            cleanup_group.children.addBoolValueInput('cleanSpecialChars', 'Clean special characters', True, '', False)
            cleanup_group.children.addTextBoxCommandInput('specialExample', '', '<i>Bolt M6×1.0 {rev}</i> &rarr; <i>Bolt M61.0 rev</i>', 1, True)
            cleanup_group.children.addBoolValueInput('cleanVersionNumbers', 'Clean version numbers (v1, v2, ...)', True, '', False)
            cleanup_group.children.addTextBoxCommandInput('versionExample', '', '<i>Bracket v2</i> &rarr; <i>Bracket</i>', 1, True)
            cleanup_group.children.addBoolValueInput('cleanCopySuffixes', 'Clean copy suffixes ((1), (2), ...)', True, '', False)
            cleanup_group.children.addTextBoxCommandInput('copyExample', '', '<i>M3x8 BHCS (15) (1) (1)</i> &rarr; <i>M3x8 BHCS</i>', 1, True)

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
            find_orphans = inputs.itemById('findOrphans').value
            include_root = inputs.itemById('includeRoot').value
            clean_step = inputs.itemById('cleanStepNames').value
            clean_special = inputs.itemById('cleanSpecialChars').value
            clean_versions = inputs.itemById('cleanVersionNumbers').value
            clean_copies = inputs.itemById('cleanCopySuffixes').value

            design = adsk.fusion.Design.cast(_app.activeProduct)
            if not design:
                _ui.messageBox('No active Fusion design. Please open a design first.')
                return

            root_comp = design.rootComponent

            total_bodies_moved = 0
            total_components_fixed = 0
            orphans = []

            if find_orphans:
                orphans = find_orphan_components(root_comp, include_root)

                if orphans:
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
                            break

                        if result == adsk.core.DialogResults.DialogYes:
                            moved = fix_component(comp, occ)
                            total_bodies_moved += moved
                            if moved > 0:
                                total_components_fixed += 1

                _ui.activeSelections.clear()

            total_step_renamed = 0
            if clean_step:
                total_step_renamed = clean_step_names(root_comp)

            total_special_renamed = 0
            if clean_special:
                total_special_renamed = clean_special_char_names(root_comp)

            total_versions_renamed = 0
            if clean_versions:
                total_versions_renamed = clean_version_number_names(root_comp)

            total_copies_renamed = 0
            if clean_copies:
                total_copies_renamed = clean_copy_suffix_names(root_comp)

            messages = []
            if find_orphans:
                if orphans:
                    if total_bodies_moved > 0:
                        messages.append('Moved {} bod{} across {} component{}.'.format(
                            total_bodies_moved,
                            'y' if total_bodies_moved == 1 else 'ies',
                            total_components_fixed,
                            '' if total_components_fixed == 1 else 's'
                        ))
                    else:
                        messages.append('No bodies were moved.')
                else:
                    messages.append('No orphan bodies found.')

            if clean_step:
                if total_step_renamed > 0:
                    messages.append('Cleaned .step from {} name{}.'.format(
                        total_step_renamed,
                        '' if total_step_renamed == 1 else 's'
                    ))
                else:
                    messages.append('No .step names found.')

            if clean_special:
                if total_special_renamed > 0:
                    messages.append('Cleaned special characters from {} name{}.'.format(
                        total_special_renamed,
                        '' if total_special_renamed == 1 else 's'
                    ))
                else:
                    messages.append('No special characters found.')

            if clean_versions:
                if total_versions_renamed > 0:
                    messages.append('Cleaned version numbers from {} name{}.'.format(
                        total_versions_renamed,
                        '' if total_versions_renamed == 1 else 's'
                    ))
                else:
                    messages.append('No version numbers found.')

            if clean_copies:
                if total_copies_renamed > 0:
                    messages.append('Cleaned copy suffixes from {} name{}.'.format(
                        total_copies_renamed,
                        '' if total_copies_renamed == 1 else 's'
                    ))
                else:
                    messages.append('No copy suffixes found.')

            _ui.messageBox('\n'.join(messages))

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


_ALLOWED_CHARS = re.compile(r'[^a-zA-Z0-9 \-\+\(\)\[\]#._]')
_STEP_PATTERN = re.compile(r'\.step', re.IGNORECASE)
_VERSION_PATTERN = re.compile(r'\s+v\d+', re.IGNORECASE)
_COPY_SUFFIX_PATTERN = re.compile(r'(\s+\(\d+\))+$')


def strip_step_extension(name):
    return _STEP_PATTERN.sub('', name)


def has_step_extension(name):
    return bool(_STEP_PATTERN.search(name))


def find_step_names(root_comp):
    results = []

    def check_component(comp):
        if has_step_extension(comp.name):
            results.append({
                'name': comp.name,
                'kind': 'component',
                'target': comp,
            })
        for body in comp.bRepBodies:
            if has_step_extension(body.name):
                results.append({
                    'name': body.name,
                    'kind': 'body',
                    'target': body,
                })

    check_component(root_comp)
    for occ in root_comp.allOccurrences:
        check_component(occ.component)

    return results


def strip_special_chars(name):
    return _ALLOWED_CHARS.sub('', name)


def has_special_chars(name):
    return bool(_ALLOWED_CHARS.search(name))


def find_special_char_names(root_comp):
    results = []

    def check_component(comp, occ=None):
        if has_special_chars(comp.name):
            results.append({
                'name': comp.name,
                'kind': 'component',
                'target': comp,
                'occurrence': occ,
            })
        for body in comp.bRepBodies:
            if has_special_chars(body.name):
                results.append({
                    'name': body.name,
                    'kind': 'body',
                    'target': body,
                    'occurrence': occ,
                })

    check_component(root_comp)
    for occ in root_comp.allOccurrences:
        check_component(occ.component, occ)

    return results


def clean_special_char_names(root_comp):
    entries = find_special_char_names(root_comp)
    if not entries:
        return 0

    renamed = 0
    for entry in entries:
        old_name = entry['name']
        suggested_name = strip_special_chars(old_name)
        kind = entry['kind']
        occ = entry['occurrence']

        if occ:
            highlight_component(occ)

        msg = "Rename {} '{}' to '{}'?".format(kind, old_name, suggested_name)
        result = _ui.messageBox(
            msg, 'Clean Special Characters',
            adsk.core.MessageBoxButtonTypes.YesNoCancelButtonType,
            adsk.core.MessageBoxIconTypes.QuestionIconType
        )

        if result == adsk.core.DialogResults.DialogCancel:
            break

        if result == adsk.core.DialogResults.DialogYes:
            ret_val, cancelled = _ui.inputBox(
                "{} '{}'\n\nEnter cleaned name:".format(kind.capitalize(), old_name),
                'Rename', suggested_name
            )
            if cancelled:
                continue

            new_name = ret_val.strip()
            if new_name:
                entry['target'].name = new_name
                renamed += 1

    _ui.activeSelections.clear()
    return renamed


def strip_version_number(name):
    result = _VERSION_PATTERN.sub('', name)
    return re.sub(r'  +', ' ', result).strip()


def has_version_number(name):
    return bool(_VERSION_PATTERN.search(name))


def find_version_number_names(root_comp):
    results = []

    def check_component(comp, occ=None):
        if has_version_number(comp.name):
            results.append({
                'name': comp.name,
                'kind': 'component',
                'target': comp,
                'occurrence': occ,
            })
        for body in comp.bRepBodies:
            if has_version_number(body.name):
                results.append({
                    'name': body.name,
                    'kind': 'body',
                    'target': body,
                    'occurrence': occ,
                })

    check_component(root_comp)
    for occ in root_comp.allOccurrences:
        check_component(occ.component, occ)

    return results


def clean_version_number_names(root_comp):
    entries = find_version_number_names(root_comp)
    if not entries:
        return 0

    renamed = 0
    for entry in entries:
        old_name = entry['name']
        suggested_name = strip_version_number(old_name)
        kind = entry['kind']
        occ = entry['occurrence']

        if occ:
            highlight_component(occ)

        msg = "Rename {} '{}' to '{}'?".format(kind, old_name, suggested_name)
        result = _ui.messageBox(
            msg, 'Clean Version Numbers',
            adsk.core.MessageBoxButtonTypes.YesNoCancelButtonType,
            adsk.core.MessageBoxIconTypes.QuestionIconType
        )

        if result == adsk.core.DialogResults.DialogCancel:
            break

        if result == adsk.core.DialogResults.DialogYes:
            ret_val, cancelled = _ui.inputBox(
                "{} '{}'\n\nEnter cleaned name:".format(kind.capitalize(), old_name),
                'Rename', suggested_name
            )
            if cancelled:
                continue

            new_name = ret_val.strip()
            if new_name:
                entry['target'].name = new_name
                renamed += 1

    _ui.activeSelections.clear()
    return renamed


def strip_copy_suffixes(name):
    return _COPY_SUFFIX_PATTERN.sub('', name)


def has_copy_suffixes(name):
    return bool(_COPY_SUFFIX_PATTERN.search(name))


def find_copy_suffix_names(root_comp):
    results = []

    def check_component(comp, occ=None):
        if has_copy_suffixes(comp.name):
            results.append({
                'name': comp.name,
                'kind': 'component',
                'target': comp,
                'occurrence': occ,
            })
        for body in comp.bRepBodies:
            if has_copy_suffixes(body.name):
                results.append({
                    'name': body.name,
                    'kind': 'body',
                    'target': body,
                    'occurrence': occ,
                })

    check_component(root_comp)
    for occ in root_comp.allOccurrences:
        check_component(occ.component, occ)

    return results


def clean_copy_suffix_names(root_comp):
    entries = find_copy_suffix_names(root_comp)
    if not entries:
        return 0

    renamed = 0
    for entry in entries:
        old_name = entry['name']
        suggested_name = strip_copy_suffixes(old_name)
        kind = entry['kind']
        occ = entry['occurrence']

        if occ:
            highlight_component(occ)

        msg = "Rename {} '{}' to '{}'?".format(kind, old_name, suggested_name)
        result = _ui.messageBox(
            msg, 'Clean Copy Suffixes',
            adsk.core.MessageBoxButtonTypes.YesNoCancelButtonType,
            adsk.core.MessageBoxIconTypes.QuestionIconType
        )

        if result == adsk.core.DialogResults.DialogCancel:
            break

        if result == adsk.core.DialogResults.DialogYes:
            ret_val, cancelled = _ui.inputBox(
                "{} '{}'\n\nEnter cleaned name:".format(kind.capitalize(), old_name),
                'Rename', suggested_name
            )
            if cancelled:
                continue

            new_name = ret_val.strip()
            if new_name:
                entry['target'].name = new_name
                renamed += 1

    _ui.activeSelections.clear()
    return renamed


def clean_step_names(root_comp):
    entries = find_step_names(root_comp)
    if not entries:
        return 0

    renamed = 0
    for entry in entries:
        old_name = entry['name']
        new_name = strip_step_extension(old_name)
        kind = entry['kind']

        msg = "Rename {} '{}' to '{}'?".format(kind, old_name, new_name)
        result = _ui.messageBox(
            msg, 'Clean .step Names',
            adsk.core.MessageBoxButtonTypes.YesNoCancelButtonType,
            adsk.core.MessageBoxIconTypes.QuestionIconType
        )

        if result == adsk.core.DialogResults.DialogCancel:
            break

        if result == adsk.core.DialogResults.DialogYes:
            entry['target'].name = new_name
            renamed += 1

    return renamed
