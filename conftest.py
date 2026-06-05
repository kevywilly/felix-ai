# Presence of this file at the repo root puts the root on sys.path during pytest
# collection, so tests can `import felix` / `import lib` regardless of the working
# directory pytest is invoked from. (test/ has no __init__.py, so without this
# pytest would only add test/ to sys.path and `felix` would not resolve.)
