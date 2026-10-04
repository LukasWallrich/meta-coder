# Project settings

Use **Project settings** in the sidebar to export files, clear generated data, or delete a project. These controls apply to the current project.

[![Project export, generated-data cleanup, and deletion controls](assets/screenshots/projects.png)](assets/screenshots/projects.png)

## Export a backup

Choose **Download project and audit** to preserve project files and the [audit history](auditing.md), with checksums. You can also open the project folder on your computer to inspect its manual, coding sheet, sources, and generated output.

Make a backup before changing a completed coding manual or coding sheet, or before clearing generated data.

## Clear generated data

Clearing output removes working extraction results while retaining the project's inputs and persistent audit history. Use this when you deliberately want to reprocess the studies. Export any results you need before confirming.

## Delete a project

Deleting a project removes its stored files, including its audit history. This is different from clearing only generated output. Read the confirmation carefully and keep a ZIP backup if the work may be needed again.

## Data locations

By default, app data is stored under:

| Platform | Location |
| --- | --- |
| macOS | `~/Library/Application Support/Meta-Coder` |
| Windows | `%LOCALAPPDATA%/Meta-Coder` |
| Linux | `$XDG_DATA_HOME/meta-coder`, or `~/.local/share/meta-coder` |

Projects are in the `projects` subdirectory. The `META_CODER_HOME` environment variable can override the app data location. API keys live separately in the operating system credential store.
