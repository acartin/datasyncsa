from uuid import uuid4

from src.shared import file_manager
from src.shared.file_manager import FileManager


def test_file_manager_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setattr(file_manager, "STORAGE_ROOT", tmp_path)
    client_id = uuid4()
    filename = "sample.pdf"

    path = FileManager.save_upload(b"dummy-pdf", filename, client_id)
    assert path.endswith(filename)
    assert FileManager.check_file_exists(client_id, filename) is True
    assert FileManager.list_files(client_id) == [filename]

    assert FileManager.delete_document(client_id, filename) is True
    assert FileManager.check_file_exists(client_id, filename) is False
    assert FileManager.delete_client_folder(client_id) is True
