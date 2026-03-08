# Debugging Notes

## Import System Bug (2026-03-08)

**Root cause:** All source files use `bot.src.*` absolute imports but `bot` is not installed as a package.

**Symptoms:**
- `ModuleNotFoundError: No module named 'bot'` on any import of src modules
- pytest cannot collect tests
- Runtime startup fails immediately

**Fix path:**
1. Add `__init__.py` to: `src/`, `src/core/`, `src/ingestion/`, `src/models/`, `src/providers/`
2. Add `packages = [{include = "src"}]` to `[tool.poetry]` in `pyproject.toml` (or rename `src/` to `bot/`)
3. Run `poetry install` (without `--no-root`) to install the package in editable mode
4. Alternatively rename `src/` -> `bot/` and update `packages = [{include = "bot"}]`

**Note:** Tests patch `bot.src.*` path strings explicitly (e.g., `patch("bot.src.ingestion.embeddings.OpenAI")`),
so whatever the top-level package name is, the patch strings must match.

---

## conninfo URI Bug (database.py lines 30-36)

**Root cause:** f-string concatenation without URI separator characters.

**Broken:**
```python
conninfo = (
    f"postgresql://{os.getenv('POSTGRES_USER')}"
    f"{os.getenv('POSTGRES_PASSWORD')}"
    f"{os.getenv('DB_HOST', 'astrodb')}"
    f"{os.getenv('DB_PORT', '5432')}"
    f"{os.getenv('POSTGRES_DB')}"
)
```
Produces: `postgresql://userpasswordhostport5432db`

**Fixed:**
```python
conninfo = (
    f"postgresql://{os.getenv('POSTGRES_USER')}"
    f":{os.getenv('POSTGRES_PASSWORD')}"
    f"@{os.getenv('DB_HOST', 'astrodb')}"
    f":{os.getenv('DB_PORT', '5432')}"
    f"/{os.getenv('POSTGRES_DB')}"
)
```

---

## asyncio.create_task in __init__ (message_buffer.py line 23)

**Root cause:** `asyncio.create_task()` requires a running event loop. Calling it in `__init__`
means MessageBuffer cannot be constructed outside an async context.

**Fix:** Add an `async def start()` method and move `create_task` there:
```python
async def start(self) -> None:
    self._flush_task = asyncio.create_task(self._periodic_flush())
```

Call `await buffer.start()` after construction inside the bot's async entry point.

---

## Config Path Bug (config.py lines 11-13)

**Root cause:** `Path.joinpath("/")` with an absolute argument discards all preceding path components.

```python
ENV_DIR: Path = BASE_DIR.joinpath("/")  # always returns Path("/")
DEV_ENV_FILEPATH: Path = ENV_DIR / ".env.dev"  # always "/.env.dev"
```

This is dead code — `load_dotenv()` is called without arguments on line 14 anyway (searches cwd).
Remove the BASE_DIR/ENV_DIR/DEV_ENV_FILEPATH block, or pass the path explicitly to `load_dotenv()`.
