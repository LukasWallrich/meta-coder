from meta_coder import app_settings as app_settings_mod
from meta_coder.app_settings import AppSettings, load_app_settings, save_app_settings


def test_defaults_when_no_settings_file(tmp_path, monkeypatch):
    monkeypatch.setattr(app_settings_mod, "app_data_dir", lambda: tmp_path)
    settings = load_app_settings()
    assert settings.upload_size_cap_mb == 128
    assert settings.upload_size_cap_bytes == 128 * 1024 * 1024
    assert settings.manual_generator_provider == "gemini"
    assert settings.manual_generator_model


def test_save_and_load_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(app_settings_mod, "app_data_dir", lambda: tmp_path)
    save_app_settings(
        AppSettings(
            upload_size_cap_mb=256,
            manual_generator_provider="openrouter",
            manual_generator_model="example/manual-model",
        )
    )
    loaded = load_app_settings()
    assert loaded.upload_size_cap_mb == 256
    assert loaded.manual_generator_provider == "openrouter"
    assert loaded.manual_generator_model == "example/manual-model"


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


def test_unknown_generator_provider_falls_back_with_matching_default_model():
    settings = AppSettings(
        manual_generator_provider="unknown", manual_generator_model=""
    ).clamped()
    assert settings.manual_generator_provider == "gemini"
    assert settings.manual_generator_model.startswith("gemini-")
