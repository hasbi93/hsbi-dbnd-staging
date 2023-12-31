# © Copyright Databand.ai, an IBM Company 2022

from dbnd import parameter
from dbnd_spark.spark_config import SparkEngineConfig


class SparkLocalEngineConfig(SparkEngineConfig):
    """Apache Spark local deployment"""

    # we don't want spark class to inherit from this one, as it should has Config behaviour
    _conf__task_family = "spark_local"

    conn_id = parameter.value(
        default="spark_default",
        description="Set the local spark connection settings (SPARK_HOME)",
    )

    enable_spark_context_inplace = parameter(
        default=False, description="Disable spawning a new spark, use in memory."
    )

    conn_uri = parameter(
        default="docker://local?master=local",
        description="Set Airflow connection URI to be used.",
    )

    def get_spark_ctrl(self, task_run):
        from dbnd_spark.local.local_spark import LocalSparkExecutionCtrl

        return LocalSparkExecutionCtrl(task_run=task_run)
