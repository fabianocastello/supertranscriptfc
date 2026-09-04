from __future__ import annotations

import logging
from pathlib import Path

from .config import AUDIO_EXTENSIONS

logger = logging.getLogger("supertranscriptfc")


class DropboxClient:
    """Wrapper fino sobre o SDK oficial do Dropbox. Import feito dentro do
    __init__ para nao exigir a dependencia so' para importar o modulo."""

    def __init__(self, access_token: str):
        import dropbox

        self._dbx_module = dropbox
        self.dbx = dropbox.Dropbox(access_token)

    def list_audio_files(self, folder_path: str) -> list[str]:
        """Lista arquivos de audio/video na pasta (nao recursivo)."""
        folder_path = folder_path.rstrip("/")
        entries = []
        result = self.dbx.files_list_folder(folder_path)
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
        return paths

    def download_file(self, dropbox_path: str, local_path: Path) -> Path:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Baixando do Dropbox: %s -> %s", dropbox_path, local_path)
        self.dbx.files_download_to_file(str(local_path), dropbox_path)
        return local_path

    def upload_file(self, local_path: Path, dropbox_path: str) -> str:
        WriteMode = self._dbx_module.files.WriteMode
        logger.info("Enviando para o Dropbox: %s -> %s", local_path, dropbox_path)
        with open(local_path, "rb") as f:
            data = f.read()
        self.dbx.files_upload(data, dropbox_path, mode=WriteMode.overwrite)
        return dropbox_path

    def ensure_folder(self, dropbox_path: str) -> None:
        ApiError = self._dbx_module.exceptions.ApiError
        try:
            self.dbx.files_create_folder_v2(dropbox_path)
        except ApiError:
            pass  # pasta ja existe
