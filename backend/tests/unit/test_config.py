import pytest

from app.config import Settings


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("http://a:3000,http://b:3000", ["http://a:3000", "http://b:3000"]),
        ('["http://a:3000"]', ["http://a:3000"]),
    ],
)
def test_cors_origins_accepts_csv_and_json(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: list[str]
) -> None:
    monkeypatch.setenv("CORS_ORIGINS", raw)
    assert Settings(_env_file=None).cors_origins == expected


def test_api_keys_parse_from_json_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEYS", '{"k1": {"subject": "ops", "role": "viewer"}}')
    assert Settings(_env_file=None).api_keys == {"k1": {"subject": "ops", "role": "viewer"}}
