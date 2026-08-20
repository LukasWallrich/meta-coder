from meta_coder import app_settings as app_settings_mod
from meta_coder.app_settings import AppSettings, load_app_settings, save_app_settings


def test_defaults_when_no_settings_file(tmp_path, monkeypatch):
    monkeypatch.setattr(app_settings_mod, "app_data_dir", lambda: tmp_path)
    settings = load_app_settings()
    assert settings.upload_size_cap_mb == 128
    assert settings.upload_size_cap_bytes == 128 * 1024 * 1024


def test_save_and_load_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(app_settings_mod, "app_data_dir", lambda: tmp_path)
    save_app_settings(AppSettings(upload_size_cap_mb=256))
    assert load_app_settings().upload_size_cap_mb == 256


def test_out_of_range_value_is_clamped(tmp_path, monkeypatch):
    monkeypatch.setattr(app_settings_mod, "app_data_dir", lambda: tmp_path)
    save_app_settings(AppSettings(upload_size_cap_mb=999999))
    assert load_app_settings().upload_size_cap_mb == app_settings_mod.MAX_UPLOAD_SIZE_CAP_MB
    save_app_settings(AppSettings(upload_size_cap_mb=0))
    assert load_app_settings().upload_size_cap_mb == app_settings_mod.MIN_UPLOAD_SIZE_CAP_MB


def test_corrupt_settings_file_falls_back_to_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(app_settings_mod, "app_data_dir", lambda: tmp_path)
    (tmp_path / "app_settings.json").write_text("not json", encoding="utf-8")
    assert load_app_settings().upload_size_cap_mb == 128
