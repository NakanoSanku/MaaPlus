"""Resource bundle bootstrapping must match MaaFramework's native loader."""
import json

from maaplus_studio.project import Project


def test_new_project_has_loadable_empty_pipeline(tmp_path):
    project = Project.create(tmp_path)
    placeholder = project.path("resource/pipeline/studio-empty.json")
    assert json.loads(placeholder.read_text()) == {}


def test_existing_pipeline_is_not_modified(tmp_path):
    pipeline = tmp_path / "resource/pipeline"
    pipeline.mkdir(parents=True)
    source = b'{"ExistingTask": {"recognition": "DirectHit"}}\n'
    (pipeline / "game.jsonc").write_bytes(source)
    Project.create(tmp_path)
    assert (pipeline / "game.jsonc").read_bytes() == source
    assert not (pipeline / "studio-empty.json").exists()


def test_hidden_json_does_not_count_as_native_pipeline(tmp_path):
    hidden = tmp_path / "resource/pipeline/.backup"
    hidden.mkdir(parents=True)
    (hidden / "old.json").write_text("{}")
    project = Project.create(tmp_path)
    assert project.path("resource/pipeline/studio-empty.json").exists()
