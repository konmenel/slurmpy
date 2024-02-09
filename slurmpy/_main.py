# import os
from __future__ import annotations
from typing import Optional, Sequence, Self
from collections.abc import Iterable
import subprocess


class Job:
    """_summary_"""

    # Public
    name: str
    shebang: str  # Default: /bin/bash -l
    commands: list[str]

    # Private
    _job_id: Optional[int]
    _args: dict[str, Optional[str]]
    # _deps format: (<after>, <job-instance>, <time>)
    # i.e. ('ok', jobx, None) or ('', jobx, 10)
    _deps: list[tuple[str, Job | str, Optional[int]]]
    _dep_sep: str  # Default ','

    def __init__(
        self, name="", shebang="/bin/bash -l", commands=None, **kwargs
    ) -> None:
        self.name = name
        self.shebang = shebang
        self.commands = commands if commands is not None else []
        self._job_id = None
        self._deps = []
        self._dep_sep = ","

        self._args = {}
        for key, value in kwargs.items():
            key = self._parse_argname(key)
            value = self._parse_argvalues(value)
            self._args[key] = value

    @property
    def args(self) -> dict:
        return self._args

    @property
    def job_id(self) -> Optional[int]:
        if self._job_id is None:
            print("[WARNING] Job has not been submitted yet!")
        return self._job_id

    def add_arguments(self, **kwargs) -> Self:
        """Add an argument to sbatch.

        Returns
        -------
        Self
            Returns the `self` instance

        Example
        -------
        The following:
        ```python
        import slurmpy

        job = slurmpy.Job()
        job.add_argument(ntasks=1)
        ```
        is equivilant to the following bash script:
        ```bash
        #!/bin/bash -l

        #SBATCH --ntasks=1
        ```
        """
        for key, value in kwargs.items():
            key = self._parse_argname(key)
            value = self._parse_argvalues(value)
            self._args[key] = value
        return self

    def __str__(self) -> str:
        return self.get_script_body()

    def get_args_str(self) -> str:
        """Returns all the arguments in a string that can be used in the command-line
        i.e. `--ntasks=1 -N 2`

        Returns
        -------
        str
            The arguments string.
        """
        return " ".join(
            (self._arg_to_str(key, value) for key, value in self._args.items())
        )

    def add_dependency_job(
        self, after: str, dep: Job | str | int, time: Optional[int | str] = None
    ) -> Self:
        """_summary_

        Parameters
        ----------
        after : str
            _description_
        dep : Job
            _description_

        Returns
        -------
        Self
            Returns the `self` instance
        """
        if after is None:
            after = ""
        if isinstance(time, int):
            time = str(time)
        if isinstance(dep, int):
            dep = str(dep)
        self._deps.append((after, dep, time))
        return self

    def add_sigleton_dependency(self) -> Self:
        self._deps.append(("singleton", None, None))

    def add_commands(self, *commands: str) -> Self:
        """_summary_

        Parameters
        ----------
        *commands : str
            _description_

        Returns
        -------
        Self
            Returns the `self` instance
        """
        self.commands.extend(commands)

    def set_dependency_sep(self, sep: str) -> Self:
        """Change the dependencies seperator (',' or '?').

        Parameters
        ----------
        sep : str
            The sepperator

        Returns
        -------
        Self
            Returns the `self` instance
        """
        if sep not in (",", "?"):
            print("Only ',' , '?' dependency seperators may be used!")
            return self
        self._dep_sep = sep
        return self

    def get_script_body(self) -> str:
        body = f"#!{self.shebang}"
        directives = self._sbatch_directives()
        if directives:
            body += "\n\n" + directives
        if self.commands:
            body += "\n\n" + self._commands_str()
        return body

    def get_full_command(self) -> str:
        dep_str = self._dep_str()
        if dep_str:
            dep_str += ' '
        cmd = "\n".join(
            (f"sbatch --parsable {dep_str}<<\'EOF\'", self.get_script_body(), "EOF")
        )
        return cmd

    def submit(self) -> Self:
        """_summary_

        Returns
        -------
        Self
            Returns the `self` instance
        """
        for _, dep, _ in self._deps:
            if isinstance(dep, Job) and dep._job_id is None:
                dep.submit()

        cmd = self.get_full_command()
        proc = subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE)
        jobid = proc.stdout.decode()
        assert len(jobid) > 0, jobid
        self._job_id = int(jobid)
        print(f"{f'{self.name}: ' if self.name else ''}Submitted batch job {jobid}")
        return self

    # Private methods
    @staticmethod
    def _parse_argname(arg: str) -> str:
        if len(arg) > 1:
            true_arg = arg.replace("_", "-")
            return f"--{true_arg}"
        if len(arg) == 1:
            return f"-{arg}"
        return ""

    @staticmethod
    def _parse_argvalues(value: None | int | str | Sequence[str | int]) -> str:
        if isinstance(value, str):
            return value
        if value is None:
            return ""
        if isinstance(value, Iterable):
            return ",".join(map(str, value))
        return str(value)

    @staticmethod
    def _arg_to_str(argname: str, argvalue: Optional[str]) -> str:
        arg = argname
        if argvalue:
            if len(argname) == 2:
                arg += " "
            else:
                arg += "="
            arg += argvalue
        return arg

    def _sbatch_directives(self) -> str:
        directives = "\n".join(
            (
                f"#SBATCH {self._arg_to_str(argname, argval)}"
                for argname, argval in self._args.items()
            )
        )
        return directives

    def _commands_str(self) -> str:
        return "\n".join(self.commands)

    def _dep_list_str(self) -> str:
        dep_list = ",".join(
            (
                (
                    f"after{after}"
                    f":{job.job_id if isinstance(job, Job) else job}"
                    f"{f'+{time}' if time else ''}"
                )
                if after != "singleton" else after
                for after, job, time in self._deps
            )
        )
        return dep_list

    def _dep_str(self) -> str:
        if len(self._deps) == 0:
            return ""
        dep_str = f"-d {self._dep_list_str()}"
        return dep_str
