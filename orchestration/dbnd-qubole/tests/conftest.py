# © Copyright Databand.ai, an IBM Company 2022

# inline conftest

pytest_plugins = [
    "dbnd_run.testing.pytest_dbnd_run_plugin",
    "dbnd.testing.pytest_dbnd_markers_plugin",
    "dbnd.testing.pytest_dbnd_home_plugin",
]
