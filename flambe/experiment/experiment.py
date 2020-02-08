from typing import Optional, Dict

import ray

from flambe.compile import Schema, Registrable, YAMLLoadType
from flambe.search import Algorithm
from flambe.runner.runnable import Environment
from flambe.experiment.pipeline import Pipeline
from flambe.experiment.stage import Stage


class Experiment(Registrable):

    def __init__(self,
                 name: str,
                 save_path: str = 'flambe_output',
                 pipeline: Optional[Dict[str, Schema]] = None,
                 algorithm: Optional[Dict[str, Algorithm]] = None,
                 reduce: Optional[Dict[str, int]] = None,
                 cpus_per_trial: Dict[str, int] = None,
                 gpus_per_trial: Dict[str, int] = None) -> None:
        """Iniatilize an experiment.

        Parameters
        ----------
        name : str
            The name of the experiment to run.
        pipeline : Optional[Dict[str, Schema]], optional
            A set of Searchable schemas, possibly including links.
        save_path : Optional[str], optional
            A save path for the experiment.
        algorithm : Optional[Dict[str, Algorithm]], optional
            A set of hyperparameter search algorithms, one for each
            defined stage. Defaults to grid searching for all.
        reduce : Optional[Dict[str, int]], optional
            A set of reduce operations, one for each defined stage.
            Defaults to no reduction.
        cpus_per_trial : int
            The number of CPUs to allocate per trial.
            Note: if the object you are searching over spawns ray
            remote tasks, then you should set this to 1.
        gpus_per_trial : int
            The number of GPUs to allocate per trial.
            Note: if the object you are searching over spawns ray
            remote tasks, then you should set this to 0.

        """
        self.name = name
        self.save_path = save_path
        self.pipeline = pipeline if pipeline is not None else dict()
        self.algorithm = algorithm if algorithm is not None else dict()
        self.reduce = reduce if reduce is not None else dict()
        self.cpus_per_trial: Dict[str, int] = dict()
        self.gpus_per_trial: Dict[str, int] = dict()

    @classmethod
    def yaml_load_type(cls) -> YAMLLoadType:
        return YAMLLoadType.KWARGS

    def run(self, env: Optional[Environment] = None):
        """Execute the Experiment.

        Parameters
        ----------
        env : Environment, optional
            An optional environment object.

        """
        # Set up envrionment
        env = env if env is not None else Environment(self.save_path)
        if not ray.is_initialized():
            # TODO fix for remote usage i.e. detect if auto is needed
            # ray.init("auto", local_mode=env.debug)
            ray.init(local_mode=env.debug)

        stage_to_id: Dict[str, int] = {}
        pipeline = Pipeline(self.pipeline)

        # Construct and execute stages as a DAG
        for name, schema in pipeline.arguments.items():
            # Get dependencies
            sub_pipeline = pipeline.sub_pipeline(name)
            depedency_ids = [stage_to_id[d] for d in sub_pipeline.dependencies]

            # Construct the stage
            stage = ray.remote(Stage).remote(
                name=name,
                pipeline=sub_pipeline,
                algorithm=self.algorithm.get(name, None),
                reductions=self.reduce.get(name, None),
                dependencies=depedency_ids,  # Passing object ids sets the order of computation
                cpus_per_trial=self.cpus_per_trial.get(name, 1),
                gpus_per_trial=self.gpus_per_trial.get(name, 0),
                environment=env
            )

            # Execute the stage remotely
            object_id = stage.run.remote()
            # Keep the object id, to use as future dependency
            stage_to_id[name] = object_id

        # Wait until the extperiment is done
        # TODO progress tracking
        ray.get(list(stage_to_id.values()))
