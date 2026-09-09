from __future__ import annotations

import logging
from pathlib import Path

from .config import AUDIO_EXTENSIONS

logger = logging.getLogger("voxelfc")


class DropboxClient:
    """Thin wrapper around the official Dropbox SDK. Imported inside
    __init__ so this dependency isn't required just to import the module.

    Authenticates via app key/secret + refresh token (long-lived OAuth2
    flow): the SDK renews the access token by itself on every call, so the
    process can run unattended indefinitely, unlike a bare access token,
    which expires after a few hours."""

    def __init__(self, app_key: str, app_secret: str, refresh_token: str):
        import dropbox

        self._dbx_module = dropbox
        self.dbx = dropbox.Dropbox(
            oauth2_refresh_token=refresh_token,
            app_key=app_key,
            app_secret=app_secret,
        )

    def is_folder(self, path: str) -> bool:
        FolderMetadata = self._dbx_module.files.FolderMetadata
        metadata = self.dbx.files_get_metadata(path)
        return isinstance(metadata, FolderMetadata)

    def file_exists(self, path: str) -> bool:
        ApiError = self._dbx_module.exceptions.ApiError
        try:
            self.dbx.files_get_metadata(path)
            return True
        except ApiError:
            return False

    def list_audio_files(self, folder_path: str, recursive: bool = False) -> list[str]:
        """Lists audio/video files in the folder, optionally descending into
        subfolders (useful for podcast series with one folder per episode)."""
        folder_path = folder_path.rstrip("/") or "/"
        list_path = "" if folder_path == "/" else folder_path
        entries = []
        result = self.dbx.files_list_folder(list_path, recursive=recursive)
        entries.extend(result.entries)
        while result.has_more:
            result = self.dbx.files_list_folder_continue(result.cursor)
            entries.extend(result.entries)

        FileMetadata = self._dbx_module.files.FileMetadata
        paths = [
            e.path_display
            for e in entries
            if isinstance(e, FileMetadata) and e.path_lower.endswith(AUDIO_EXTENSIONS)
        ]
        return sorted(paths)

    def list_files_matching_stem(self, folder_path: str, stem: str) -> list[str]:
        """Lists every file directly in folder_path whose name starts with
        '<stem>.' - used by --archive to move all related files together,
        not just the ones a given run happened to produce."""
        folder_path = folder_path.rstrip("/") or "/"
        list_path = "" if folder_path == "/" else folder_path
        entries = []
        result = self.dbx.files_list_folder(list_path)
        entries.extend(result.entries)
        while result.has_more:
            result = self.dbx.files_list_folder_continue(result.cursor)
            entries.extend(result.entries)

        FileMetadata = self._dbx_module.files.FileMetadata
        prefix = f"{stem}."
        return sorted(
            e.path_display for e in entries if isinstance(e, FileMetadata) and e.name.startswith(prefix)
        )

    def download_file(self, dropbox_path: str, local_path: Path) -> Path:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Downloading from Dropbox: %s -> %s", dropbox_path, local_path)
        self.dbx.files_download_to_file(str(local_path), dropbox_path)
        return local_path

    def upload_file(self, local_path: Path, dropbox_path: str) -> str:
        WriteMode = self._dbx_module.files.WriteMode
        logger.info("Uploading to Dropbox: %s -> %s", local_path, dropbox_path)
        with open(local_path, "rb") as f:
            data = f.read()
        self.dbx.files_upload(data, dropbox_path, mode=WriteMode.overwrite)
        return dropbox_path

    def ensure_folder(self, dropbox_path: str) -> None:
        ApiError = self._dbx_module.exceptions.ApiError
        try:
            self.dbx.files_create_folder_v2(dropbox_path)
        except ApiError:
            pass  # folder already exists

    def write_text_file(self, dropbox_path: str, text: str) -> None:
        WriteMode = self._dbx_module.files.WriteMode
        self.dbx.files_upload(text.encode("utf-8"), dropbox_path, mode=WriteMode.overwrite)

    def read_text_file(self, dropbox_path: str) -> str | None:
        ApiError = self._dbx_module.exceptions.ApiError
        try:
            _metadata, response = self.dbx.files_download(dropbox_path)
            return response.content.decode("utf-8")
        except ApiError:
            return None

    def move_file(self, from_path: str, to_path: str) -> str:
        """Moves/renames a file. Idempotent: if from_path no longer exists
        but to_path does (e.g. resuming after a crash mid-move), assumes the
        move already happened and doesn't fail."""
        ApiError = self._dbx_module.exceptions.ApiError
        try:
            result = self.dbx.files_move_v2(from_path, to_path, autorename=True)
            return result.metadata.path_display
        except ApiError:
            if self.file_exists(to_path):
                return to_path
            raise

    def delete_file(self, dropbox_path: str) -> None:
        ApiError = self._dbx_module.exceptions.ApiError
        try:
            self.dbx.files_delete_v2(dropbox_path)
        except ApiError:
            pass  # no longer exists / already removed
