from rmstory.storage import translations


def test_connect_with_no_backend_configured_defaults_to_filesystem_in_cwd(tmp_path, monkeypatch):
    monkeypatch.delenv("MULTILANG_DB_BACKEND", raising=False)
    monkeypatch.delenv("MULTILANG_DB_PATH", raising=False)
    monkeypatch.delenv("RMSTORY_STRINGS_PATH", raising=False)
    monkeypatch.chdir(tmp_path)

    conn = translations.connect()
    translations.store(conn, "greeting", "en", "Hello")

    assert (tmp_path / "rmstory" / "strings").is_dir()
    assert translations.fetch(conn, "greeting", "en") == "Hello"


def test_connect_default_path_honors_multilang_db_path_env_var(tmp_path, monkeypatch):
    monkeypatch.delenv("MULTILANG_DB_BACKEND", raising=False)
    custom = tmp_path / "custom-strings"
    monkeypatch.setenv("MULTILANG_DB_PATH", str(custom))

    translations.connect()

    assert custom.is_dir()


def test_connect_default_path_honors_rmstory_strings_path_env_var(tmp_path, monkeypatch):
    monkeypatch.delenv("MULTILANG_DB_BACKEND", raising=False)
    monkeypatch.delenv("MULTILANG_DB_PATH", raising=False)
    custom = tmp_path / "other-strings"
    monkeypatch.setenv("RMSTORY_STRINGS_PATH", str(custom))

    translations.connect()

    assert custom.is_dir()


def test_connect_does_not_override_explicit_backend(tmp_path, monkeypatch):
    monkeypatch.delenv("MULTILANG_DB_BACKEND", raising=False)
    monkeypatch.delenv("MULTILANG_DB_PATH", raising=False)

    conn = translations.connect("filesystem", path=str(tmp_path / "explicit"))

    assert (tmp_path / "explicit").is_dir()
    assert conn is not None


def test_connect_respects_multilang_db_backend_env_var_unchanged(tmp_path, monkeypatch):
    monkeypatch.setenv("MULTILANG_DB_BACKEND", "filesystem")
    monkeypatch.setenv("MULTILANG_DB_PATH", str(tmp_path / "env-configured"))

    translations.connect()

    assert (tmp_path / "env-configured").is_dir()
