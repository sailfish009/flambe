from typing import Any, Dict, Optional, List, Callable
import sys
import tempfile
from copy import deepcopy

import flambe
from flambe.compile import Component
from flambe.compile import dump_one_config


class Script(Component):
    """Implement a Script computable.

    This object can be used to turn any script into a Flambé runnable.
    This is useful when you want to keep your code unchanged. Note
    however that this runnable does not enable checkpointing or
    linking to internal components as it does not have any attributes.

    To use this object, your script needs to be in a pip installable,
    containing all dependencies. The script is run with the following
    command:

    .. code-block:: bash

        python -m script.py --arg1 value1 --arg2 value2

    """

    def __init__(self,
                 script: str,
                 pos_args: List[Any],
                 keyword_args: Optional[Dict[str, Any]] = None,
                 max_steps: Optional[int] = None,
                 metric_fn: Optional[Callable[[str], float]] = None) -> None:
        """Initialize a Script.

        Parameters
        ----------
        path: str
            The path to the script
        args: List[Any]
            Argument List
        kwargs: Optional[Dict[str, Any]]
            Keyword argument dictionary

        """
        self.script = script
        self.args = pos_args
        if keyword_args is None:
            self.kwargs: Dict[str, Any] = {}
        else:
            self.kwargs = keyword_args

        self.max_steps = max_steps
        self.metric_fn = metric_fn
        self._step = 0

        self.register_attrs('_step')

    def metric(self) -> float:
        """Override to read a metric from your script's output."""
        env = flambe.get_env()
        if self.metric_fn is not None:
            return self.metric_fn(env.output_path)
        return 0.0

    def run(self) -> bool:
        """Run the evaluation.

        Returns
        -------
        bool
            Whether to continue execution.

        """
        env = flambe.get_env()

        with tempfile.NamedTemporaryFile() as fp:
            dump_one_config(env, fp)

            # Flatten the arguments into a list to pass to sys.argv
            parser_args_flat = [str(item) for item in self.args]
            parser_args_flat += [str(item) for items in self.kwargs.items() for item in items]

            # Execute the script
            sys_save = deepcopy(sys.argv)
            sys.argv = [''] + parser_args_flat  # add dummy sys[0]
            exec(open(self.script, 'r').read())
            sys.argv = sys_save

        self._step += 1
        continue_ = True
        if self.max_steps is None or self._step >= self.max_steps:
            continue_ = False
        return continue_
