# -*- coding: utf-8 -*-
#
# Copyright 2012-2015 Spotify AB
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
#
# This file has been modified by databand.ai to support dbnd tracking.

import luigi

from luigi import LocalTarget
from luigi.contrib.spark import (
    PySparkTask as LuigiPySparkTask,
    SparkSubmitTask as LuigiSparkSubmitTask,
)


class InlinePySparkWordCount(LuigiPySparkTask):
    """
    This task runs a :py:class:`luigi.contrib.spark.PySparkTask` task
    over the target data in :py:meth:`wordcount.input` (a file in S3) and
    writes the result into its :py:meth:`wordcount.output` target (a file in S3).
    This class uses :py:meth:`luigi.contrib.spark.PySparkTask.main`.
    Example luigi configuration::
        [spark]
        spark-submit: /usr/local/spark/bin/spark-submit
        master: spark://spark.example.org:7077
        # py-packages: numpy, pandas
    """

    driver_memory = "2g"
    executor_memory = "3g"

    def input(self):
        return LocalTarget("/Users/jonnyb/development/databand/gpt-3.txt")

    def output(self):
        return LocalTarget("/Users/jonnyb/development/databand/results")

    def main(self, sc, *args):
        sc.textFile(self.input().path).flatMap(lambda line: line.split()).map(
            lambda word: (word, 1)
        ).reduceByKey(lambda a, b: a + b).saveAsTextFile(self.output().path)


class PySparkWordCount(LuigiSparkSubmitTask):
    """
    This task is the same as :py:class:`InlinePySparkWordCount` above but uses
    an external python driver file specified in :py:meth:`app`
    It runs a :py:class:`luigi.contrib.spark.SparkSubmitTask` task
    over the target data in :py:meth:`wordcount.input` (a file in S3) and
    writes the result into its :py:meth:`wordcount.output` target (a file in S3).
    This class uses :py:meth:`luigi.contrib.spark.SparkSubmitTask.run`.
    Example luigi configuration::
        [spark]
        spark-submit: /usr/local/spark/bin/spark-submit
        master: spark://spark.example.org:7077
        deploy-mode: client
    """

    driver_memory = "2g"
    executor_memory = "3g"
    total_executor_cores = luigi.IntParameter(default=100, significant=False)

    name = "PySpark Word Count"
    app = "wordcount.py"

    def app_options(self):
        # These are passed to the Spark main args in the defined order.
        return [self.input().path, self.output().path]

    def input(self):
        return LocalTarget("/Users/jonnyb/development/databand/gpt-3.txt")

    def output(self):
        return LocalTarget("/Users/jonnyb/development/databand/results")


"""
// Corresponding example Spark Job, running Word count with Spark's Python API
// This file would have to be saved into wordcount.py
import sys
from pyspark import SparkContext
if __name__ == "__main__":
    sc = SparkContext()
    sc.textFile(sys.argv[1]) \
      .flatMap(lambda line: line.split()) \
      .map(lambda word: (word, 1)) \
      .reduceByKey(lambda a, b: a + b) \
      .saveAsTextFile(sys.argv[2])
"""
