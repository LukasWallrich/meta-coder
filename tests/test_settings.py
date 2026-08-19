from meta_coder.settings import RunSettings, load_run_settings, save_run_settings


class FakeProject:
    def __init__(self, tmp_path):
        self.path = tmp_path


def test_defaults_when_no_settings_file(tmp_path):
    settings = load_run_settings(FakeProject(tmp_path))
    assert settings.parallel_requests == 1
    assert settings.request_delay_sec == 0


def test_save_and_load_round_trip(tmp_path):
    project = FakeProject(tmp_path)
    save_run_settings(project, RunSettings(model="gemini-x", parallel_requests=5, request_delay_sec=10))
    reloaded = load_run_settings(project)
    assert reloaded.model == "gemini-x"
    assert reloaded.parallel_requests == 5
    assert reloaded.request_delay_sec == 10


def test_clamps_out_of_range_values(tmp_path):
    project = FakeProject(tmp_path)
    save_run_settings(project, RunSettings(parallel_requests=999, request_delay_sec=-5))
    reloaded = load_run_settings(project)
    assert reloaded.parallel_requests == 32
    assert reloaded.request_delay_sec == 0


def test_corrupt_settings_file_falls_back_to_defaults(tmp_path):
    project = FakeProject(tmp_path)
    settings_path = tmp_path / ".meta_coder" / "run_settings.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text("not json", encoding="utf-8")
    settings = load_run_settings(project)
    assert settings.parallel_requests == 1
