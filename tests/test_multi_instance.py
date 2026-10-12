import sys
import tempfile
from pathlib import Path
from src.bot.core.config import parse_instance_args
from src.main import ProcessLock
import src.bot.core.config as config


def test_parse_instance_args_defaults(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py"])
    monkeypatch.delenv("BOT_INSTANCE", raising=False)
    monkeypatch.delenv("BOT_ENV_FILE", raising=False)

    inst, env = parse_instance_args()
    assert inst == ""
    assert env == ""


def test_parse_instance_args_cli_flags(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py", "--instance", "bot2", "--env", ".env.custom"])
    monkeypatch.delenv("BOT_INSTANCE", raising=False)
    monkeypatch.delenv("BOT_ENV_FILE", raising=False)
    inst, env = parse_instance_args()
    assert inst == "bot2"
    assert env == ".env.custom"


def test_parse_instance_args_equals_and_short_flags(monkeypatch):
    monkeypatch.delenv("BOT_INSTANCE", raising=False)
    monkeypatch.delenv("BOT_ENV_FILE", raising=False)

    monkeypatch.setattr(sys, "argv", ["main.py", "-i", "bot3", "-e", ".env.test"])
    inst, env = parse_instance_args()
    assert inst == "bot3"
    assert env == ".env.test"

    monkeypatch.setattr(sys, "argv", ["main.py", "--instance=bot4", "--env=.env.test4"])
    inst, env = parse_instance_args()
    assert inst == "bot4"
    assert env == ".env.test4"


def test_parse_instance_args_inferred_from_env(monkeypatch):
    monkeypatch.delenv("BOT_INSTANCE", raising=False)
    monkeypatch.delenv("BOT_ENV_FILE", raising=False)

    monkeypatch.setattr(sys, "argv", ["main.py", "--env", ".env.bot2"])
    inst, env = parse_instance_args()
    assert inst == "bot2"
    assert env == ".env.bot2"


def test_parse_instance_args_env_var(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py"])
    monkeypatch.setenv("BOT_INSTANCE", "worker3")
    monkeypatch.setenv("BOT_ENV_FILE", "config/worker3.env")

    inst, env = parse_instance_args()
    assert inst == "worker3"
    assert env == "config/worker3.env"


def test_refresh_settings_path_isolation(monkeypatch):
    monkeypatch.setattr(config, "INSTANCE_NAME", "isolated_bot")
    monkeypatch.delenv("DB_FILE", raising=False)
    monkeypatch.delenv("LOG_FILE", raising=False)
    monkeypatch.delenv("LOCK_FILE", raising=False)
    monkeypatch.delenv("BACKUP_DIR", raising=False)

    config.refresh_settings()

    assert "bot_isolated_bot.db" in str(config.DB_FILE)
    assert "bot_isolated_bot.log" in str(config.LOG_FILE)
    assert "bot_isolated_bot.lock" in str(config.LOCK_FILE)

    # Reset back to default
    monkeypatch.setattr(config, "INSTANCE_NAME", "")
    config.refresh_settings()
    assert str(config.DB_FILE).endswith("bot.db")
    assert str(config.LOG_FILE).endswith("bot.log")
    assert str(config.LOCK_FILE).endswith("bot.lock")


def test_process_lock_independent_instances():
    """Verify two different instance lock files can be acquired concurrently."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lock1_path = Path(tmpdir) / "bot.lock"
        lock2_path = Path(tmpdir) / "bot_bot2.lock"

        lock1 = ProcessLock(lock1_path)
        lock2 = ProcessLock(lock2_path)

        assert lock1.acquire() is True
        assert lock2.acquire() is True

        # Duplicate of instance 1 should fail
        lock1_dup = ProcessLock(lock1_path)
        assert lock1_dup.acquire() is False

        # Release lock 1
        lock1.release()
        assert lock1_dup.acquire() is True

        lock1_dup.release()
        lock2.release()
