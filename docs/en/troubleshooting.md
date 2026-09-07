# Troubleshooting

| Symptom | Action |
| --- | --- |
| Command not found | Activate the installation environment or use its full command path. Reinstall launchers pointing to missing Python. |
| Cannot connect | Check `insar-pilot --status`, the port and WSL instance. Start the service if stopped. |
| Port occupied | Choose another port with `--port`. |
| Workbench occupied | Close the active window. Unexpected disconnects expire after about 15 seconds plus retry delay. |
| Map/download failed | Distinguish imagery CDN, search service, credentials and destination errors from the message. |
| Missing scientific components | Check the selected Python; Web installation does not install ISCE2/ISCE3. |
| Exit refused | Handle active tasks/workers before shutdown. Closing a tab leaves work running. |

Do not delete projects or Library data to repair the application environment. Preserve state outside temporary directories.
Qt xcb/Wayland troubleshooting applies to historical desktop releases, not 1.5.0.

[Installation](installation.md) · [User guide](user-guide.md)
