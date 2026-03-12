# FusionTidy

![Version 1.1](https://img.shields.io/badge/version-1.1-blue)

A Fusion 360 add-in for cleaning up messy design trees. Finds orphan bodies, strips `.step` suffixes, removes special characters, and cleans version numbers from component and body names.

![Demo Gif](images/fusiontidy-FusionOrphanBodyFinder-demo.gif)

## Why?

Imported STEP files and iterative design work leave behind a mess: bodies at the wrong level of the hierarchy, `.STEP` cluttering every name, stray special characters, leftover `v1`/`v2` version tags. FusionTidy walks your entire design tree and offers to fix each issue one at a time, so you stay in control.

## Installation

**macOS:**
```
cd ~/Library/Application\ Support/Autodesk/Autodesk\ Fusion\ 360/API/AddIns/
git clone https://github.com/erikbuild/FusionTidy.git
```

**Windows:**
Download or clone this repository, then copy the `FusionTidy` folder to your Fusion 360 add-ins directory:
```
%AppData%\Autodesk\Autodesk Fusion 360\API\AddIns\
```

Then in Fusion 360:

1. Go to **UTILITIES > ADD-INS** (or press **Shift+S**)
2. Select the **Add-Ins** tab
3. Find **FusionTidy** in the list and click **Run**

A **"FusionTidy"** button will appear in the **INSPECT** toolbar panel.

## Usage

Click the **FusionTidy** button to open the options dialog. Each feature can be toggled independently — run them all at once or just the ones you need.

### Orphan Bodies

Finds components that contain both subcomponents and direct bodies. For each match, you can move the orphan bodies into their own new subcomponents.

| Component contents | Flagged? |
|---|---|
| Only bodies, no subcomponents | No |
| Only subcomponents, no bodies | No |
| Both bodies and subcomponents | **Yes** |

Options:
- **Find Orphan Bodies** — Enable or disable the orphan body scan.
- **Include Root Component** — Whether to check the top-level root component.

For each flagged component, you'll be prompted:
- **Yes** — Name each body and move it into a new child component.
- **No** — Skip this component.
- **Cancel** — Stop the scan.

The body's position in 3D space is preserved — only its location in the browser tree changes.

### Name Cleanup

Four independent cleanup passes for component and body names:

- **Clean .step from names** — Strips `.step` / `.STEP` / `.Step` from anywhere in the name. Prompts for each match with Yes/No/Cancel.
- **Clean special characters** — Finds names with characters outside the allowed set (`a-z A-Z 0-9 - + ( ) [ ] # . _` and spaces). Prompts to rename with a suggested cleaned version, editable before confirming.
- **Clean version numbers** — Finds `v1`, `V2`, `v12`, etc. (preceded by a space) and offers to strip them. Prompts with an editable suggested name.
- **Clean copy suffixes** — Strips trailing `(1)`, `(15) (1) (1)`, etc. from names. Prompts with an editable suggested name.

All four highlight the affected component in the browser tree as they go.

### Demo

A messy design tree with `.step` suffixes, special characters, version numbers, and copy suffixes — cleaned up in one pass:

![Options dialog with messy tree](images/fusiontidy-demo1.png)

**Step 1 — Clean .step from names:**

![Clean .step prompt](images/fusiontidy-demo2.png)

**Step 2 — Clean special characters:**

![Clean special characters prompt](images/fusiontidy-demo3.png)

![Editable rename dialog](images/fusiontidy-demo4.png)

**Step 3 — Clean version numbers:**

![Clean version numbers prompt](images/fusiontidy-demo5.png)

![Editable rename dialog](images/fusiontidy-demo6.png)

**Step 4 — Clean copy suffixes:**

![Clean copy suffixes prompt](images/fusiontidy-demo7.png)

![Editable rename dialog](images/fusiontidy-demo9.png)

**Result:**

![Cleaned design tree](images/fusiontidy-demo10.png)

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

## Project Structure

```
FusionTidy/
├── erikbuild-FusionTidy.py        # Add-in source code
├── erikbuild-FusionTidy.manifest  # Fusion 360 add-in manifest
├── config.json                    # Optional panel configuration
├── resources/
│   ├── 16x16.png                  # Toolbar icons
│   ├── 32x32.png
│   └── 64x64.png
├── tests/                         # Unit tests
├── LICENSE
└── README.md
```

## License

[MIT + Commons Clause](LICENSE)


## Made By

@erikbuild
