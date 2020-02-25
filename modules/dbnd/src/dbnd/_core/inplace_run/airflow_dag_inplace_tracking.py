import os

from dbnd import current_task_run
from dbnd._core.decorator.dynamic_tasks import run_dynamic_task
from dbnd._core.inplace_run.inplace_run_manager import get_dbnd_inplace_run_manager
from dbnd._core.task.task import Task
from dbnd._core.utils.uid_utils import get_job_run_uid, get_task_run_uid


def is_in_airflow_dag_run_context():
    if "AIRFLOW_CTX_DAG_ID" in os.environ:
        return True
    return False


def track_airflow_dag_run_operator_run(task_cls, call_args, call_kwargs):
    from dbnd import dbnd_run_stop

    # this part will run DAG and Operator Tasks
    dr = dbnd_run_start_airflow_dag_task()

    # this is the real run of the decorated function
    try:
        task_run = run_dynamic_task(
            parent_task_run=current_task_run(),
            task_cls=task_cls,
            call_args=call_args,
            call_kwargs=call_kwargs,
        )
        t = task_run.task
        # if we are inside run, we want to have real values, not deferred!
        if t.task_definition.single_result_output:
            return t.__class__.result.load_from_target(t.result)
            # we have func without result, just fallback to None
        return t
    finally:
        dbnd_run_stop(at_exit=False)


def dbnd_run_start_airflow_dag_task(dag_id=None, execution_date=None, task_id=None):
    if not dag_id:
        dag_id = os.environ["AIRFLOW_CTX_DAG_ID"]
    if not execution_date:
        execution_date = os.environ["AIRFLOW_CTX_EXECUTION_DATE"]
    if not task_id:
        task_id = os.environ["AIRFLOW_CTX_TASK_ID"]

    run_uid = get_job_run_uid(dag_id=dag_id, execution_date=execution_date)
    # root_task_uid = get_task_run_uid(run_uid=run_uid, task_id="DAG")
    # task_uid = get_task_run_uid(run_uid=run_uid, task_id=task_id)
    # this will create databand run with driver and root tasks.
    # we need the "root" task to be the same between different airflow tasks invocations
    # since in dbnd we must have single root task, so we create "dummy" task with dag_id name

    inplace_run_manager = get_dbnd_inplace_run_manager()
    dr = inplace_run_manager.start(
        root_task_name="DAG", run_uid=run_uid, job_name=dag_id, airflow_context=True
    )

    # now create "operator" task for current task_id,
    # we can't actually run it, we even don't know when it's going to finish
    # current execution is inside the operator, this is the only thing we know
    class InplaceAirflowOperatorTask(Task):
        _conf__task_family = task_id

    task = InplaceAirflowOperatorTask(task_version="now", task_name=task_id)
    tr = dr.create_dynamic_task_run(
        task, dr.local_engine, _uuid=get_task_run_uid(run_uid, task_id)
    )
    inplace_run_manager._start_taskrun(tr)
    return dr
