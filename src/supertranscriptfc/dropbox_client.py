from __future__ import annotations

import logging
from pathlib import Path

from .config import AUDIO_EXTENSIONS

logger = logging.getLogger("supertranscriptfc")


class DropboxClient:
    """Wrapper fino sobre o SDK oficial do Dropbox. Import feito dentro do
    __init__ para nao exigir a dependencia so' para importar o modulo.

    Autentica via app key/secret + refresh token (fluxo OAuth2 de longa
    duracao): o SDK renova o access token sozinho a cada chamada, entao o
    processo pode rodar sem intervencao manual indefinidamente, ao contrario
    de um access token avulso, que expira em poucas horas."""

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
        """Lista arquivos de audio/video na pasta, opcionalmente descendo em
        subpastas (util para series de podcast com uma pasta por episodio)."""
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

    def delete_file(self, dropbox_path: str) -> None:
        ApiError = self._dbx_module.exceptions.ApiError
        try:
            self.dbx.files_delete_v2(dropbox_path)
        except ApiError:
            pass  # ja nao existe / ja foi removido
