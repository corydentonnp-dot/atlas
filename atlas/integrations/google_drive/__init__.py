"""Google Drive / Sheets integration adapter.

TODO: Implement after scaffolding is approved.
Required credentials: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET (shared)

Capabilities:
- upload_file(path, folder_id) -> str
- download_file(file_id) -> bytes
- list_files(folder_id, query) -> list[DriveFile]
- read_spreadsheet(spreadsheet_id, range) -> list[list]
- write_spreadsheet(spreadsheet_id, range, data) -> None
- create_spreadsheet(title) -> str
"""
