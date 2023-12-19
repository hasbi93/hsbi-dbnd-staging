# © Copyright Databand.ai, an IBM Company 2022

from dbnd import config
from dbnd_run.tasks.basics import dbnd_sanity_check


if __name__ == "__main__":
    config.set("databand", "env", "gcp_k8s")
    dbnd_sanity_check.dbnd_run()
