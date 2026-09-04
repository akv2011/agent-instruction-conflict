# Changes made to the upstream harness

**`local_provider.py`** goes in `src/agent_interp_envs/providers/` and is registered
as `"local"` in that package's `__init__.py`. Every other provider hardcodes its
base URL, so there was no way to point the agent loop at a model on this machine.
Reads `LOCAL_BASE_URL`, default `http://localhost:11434/v1`.

**`entrypoint_injection_block.py.txt`** goes into
`environments/precommit_hook/entrypoint.py`, immediately after the line that copies
`pyproject.toml` into the workspace. It writes files listed under `task.injections`
before the initial commit, so each experimental cell is a config change rather than
an image rebuild.
