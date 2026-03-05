# FusionOrphanBodyFinder

A Fusion 360 add-in that finds and fixes "orphan bodies" — loose BRepBodies sitting directly inside components that also contain subcomponents.

![Demo Gif](images/FusionOrphanBodyFinder-demo.gif)

## The Problem

In well-organized Fusion 360 designs, every "Body" lives inside its own component. But it's easy to accidentally leave bodies at the wrong level of the hierarchy — for example, a component that has both child subcomponents *and* direct bodies. These "orphan bodies" make it harder to manage visibility, materials, joints, and manufacturing outputs.

This add-in scans your entire design tree, flags every component with orphan bodies, and offers to automatically wrap each one in its own new subcomponent.

## Installation

**macOS:**
```
cd ~/Library/Application\ Support/Autodesk/Autodesk\ Fusion\ 360/API/AddIns/
git clone https://github.com/erikbuild/FusionOrphanBodyFinder.git
```

**Windows:**
Download or clone this repository, then copy the `FusionOrphanBodyFinder` folder to your Fusion 360 add-ins directory:
```
%AppData%\Autodesk\Autodesk Fusion 360\API\AddIns\
```

Then in Fusion 360:

1. Go to **UTILITIES > ADD-INS** (or press **Shift+S**)
2. Select the **Add-Ins** tab
3. Find **FusionOrphanBodyFinder** in the list and click **Run**

A **"Find Orphan Bodies"** button will appear in the **INSPECT** toolbar panel.

## Configuration

The add-in reads settings from `config.json` in the add-in directory. If the file is missing, defaults are used.

```json
{
    "use_custom_panel": false,
    "panel_id": "CustomPlugins_Panel",
    "panel_name": "CUSTOM PLUGINS"
}
```

| Setting | Default | Description |
|---|---|---|
| `use_custom_panel` | `false` | When `true`, creates a dedicated toolbar panel in the Solid tab instead of using the built-in Inspect panel. |
| `panel_id` | `"Custom_Panel"` | Internal ID for the custom panel. |
| `panel_name` | `"MY CUSTOM PLUGINS"` | Display name shown in the toolbar for the custom panel. |

The `panel_id` and `panel_name` settings are only used when `use_custom_panel` is `true`. When `false`, the button appears in the Inspect panel as usual.

## Usage

1. Click **"Find Orphan Bodies"** in the INSPECT panel
2. A dialog appears with a single option: **Include Root Component** (checked by default). Uncheck this if you want to ignore orphan bodies in the top-level root component. Click **OK**.
3. The add-in scans every component in the design. For each component that has both child occurrences *and* direct bodies, you'll see a prompt:

   > Component 'Bracket Assembly' contains 2 orphan bodies: [Body1, Body2]
   >
   > Move to new subcomponents?

   - **Yes** — For each body, an input box lets you rename it (defaults to the parent component name). The body is then moved into a new child component with that name.
   - **No** — Skip this component and move on to the next.
   - **Cancel** — Stop the entire operation.

4. When finished, a summary message shows how many bodies were moved across how many components.

## What Gets Flagged

| Component contents | Flagged? |
|---|---|
| Only bodies, no subcomponents | No |
| Only subcomponents, no bodies | No |
| Both bodies and subcomponents | **Yes** |

## What "Fix" Does

For each orphan body in a flagged component:

1. Prompts you to name the body (and its new component)
2. Creates a new child component with an identity transform
3. Names the new component after your input
4. Moves the body into the new component via `moveToComponent`

The body's position in 3D space is preserved — only its location in the browser tree changes.

## Project Structure

```
FusionOrphanBodyFinder/
├── FusionOrphanBodyFinder.py        # Add-in source code
├── FusionOrphanBodyFinder.manifest  # Fusion 360 add-in manifest
├── config.json                      # Optional panel configuration
├── resources/
│   ├── 16x16.png                    # Toolbar icons
│   ├── 32x32.png
│   └── 64x64.png
├── LICENSE
└── README.md
```

## License

[MIT + Commons Clause](LICENSE)


## Made By

@erikbuild