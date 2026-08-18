# Sample project fixture

A tiny, deliberately imperfect project used to demonstrate ProjectKaizen's
CLI. It has no README/pyproject.toml/.gitignore of its own and one small
source file with a TODO, a broad `except`, and a non-deterministic call —
enough for every analyzer to have something real to say.

Run from the repository root:

```bash
projectkaizen inspect docs/sample_project
projectkaizen findings docs/sample_project --full
projectkaizen plan docs/sample_project
projectkaizen status docs/sample_project
```
