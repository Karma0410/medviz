# Architecture example

```
pipeline/
 ├── worker/
 │    ├── main.py // entrypoint
 │    ├── queue.py
 │    ├── db.py
 │    └── modules/*.py
 ├── pyproject.toml
 └── uv.lock
 ```