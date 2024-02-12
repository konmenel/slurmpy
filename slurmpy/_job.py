# import os
from __future__ import annotations
from typing import Optional, Sequence, Self
from collections import defaultdict
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

        Examples
        --------
        The following:
        ```python
        import slurmpy

        job = slurmpy.Job()
        job.add_argument(ntasks=1)
        ```
        is equivalent to the following bash script:
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

    def add_account(self, account: str) -> Self:
        """Add an account argument to `sbatch`, i.e. `--account`.

        Parameters
        ----------
        account : str
            The accont id string.

        Returns
        -------
        Self
            Returns the `self` instance
        """
        for arg in ("-A", "--account"):
            if arg in self._args:
                self._args[arg] = str(account)
                return self
        return self.add_arguments(account=account)

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

    def add_dependencies_job(
        self, after: str, dep: Job | str | int, time: Optional[int | str] = None
    ) -> Self:
        """Adds a dependency to this job. The dependency can be a string or an int
        inticating the job id if the dependency. In the case of a dependency that
        has not been submitted yet, the dependency can be a different object of this
        `Job` class.

        Parameters
        ----------
        after : str
            The type of the dependency as explained in the documentation of `sbatch`.

            Options:
            `""` or `None` : equivalent to `after`
            `"ok"` : `afterok`
            `"notok"` : `afternotok`
            `"any"` : `afterany`
            `"burstbuffer"` : `afterburstbuffer`
            `"corr"` : `aftercorr`
            `"singleton"` : `singleton`
        dep : Job or str or int
            The job that this job is depended on. In case if `singleton` this is
            ignored.
        time : int or str, optional
            Only used in the case of `after` type. If specified the time in minutes
            after which the job will begin after the dependency is has started or is
            concelled.

        Returns
        -------
        Self
            Returns the `self` instance
        """
        if after == "singleton":
            return self.add_singleton_dependency()
        if after is None:
            after = ""
        if isinstance(time, int):
            time = str(time)
        if isinstance(dep, int):
            dep = str(dep)
        if after and time:
            time = None

        after = after.lower()
        self._deps.append((after, dep, time))
        return self

    def add_singleton_dependency(self) -> Self:
        """Adds a singleton dependency to this job.

        Returns
        -------
        Self
            Returns the `self` instance
        """
        self._deps.append(("singleton", None, None))

    def add_commands(self, *commands: str) -> Self:
        """Add commands that will be excecuted when the job begins. Each command
        must be a valid command of the shell that is being used, i.e. bash by default.
        Also, each command will be treated as a seperate line in the equivalent shell
        script.

        Parameters
        ----------
        *commands : str
            The unpacked list of commands. See Examples.

        Returns
        -------
        Self
            Returns the `self` instance

        Examples
        --------
        ```python
        import slurmpy

        job = slurmpy.Job()
        job.add_commands("echo hello", "echo world")
        ```
        The above python code is equivalent to the following bash script:
        ```bash
        #!/bin/bash -l

        echo hello
        echo world
        ```
        """
        self.commands.extend(commands)

    def set_dependency_sep(self, sep: str) -> Self:
        """Change the dependencies seperator (',' or '?').

        Parameters
        ----------
        sep : str
            The seperator.

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
        """Get the body of the script that will be submited, i.e. the equivalent
        bash script.

        Returns
        -------
        str
            The entire string of the scipt.

        Examples
        --------
        ```python
        import slurmpy

        job = slurmpy.Job(ntasks=1)
        job.add_commands("echo hello world")

        print(job.get_script_body())
        ```
        Output:
        ```console
        #!/bin/bash -l

        #SBATCH --ntasks=1

        echo hello world
        ```
        """
        body = f"#!{self.shebang}"
        directives = self._sbatch_directives()
        if directives:
            body += "\n\n" + directives
        if self.commands:
            body += "\n\n" + self._commands_str()
        return body

    def get_full_command(self) -> str:
        """Returns the full `sbatch` command that will be ran on job submission.

        Returns
        -------
        str
            The full command.

        Notes
        -----
        The `--parsable` option is always included as an argument to `sbatch`
        for internal parsing purposes.

        Examples
        --------
        ```python
        import slurmpy

        job = slurmpy.Job(ntasks=1)
        job.add_commands("echo hello world")

        print(job.get_full_command())
        ```
        Output:
        ```console
        sbatch --parsable <<'EOF'
        #!/bin/bash -l

        #SBATCH --ntasks=1

        echo hello world
        'EOF'
        ```
        """
        dep_str = self._dep_str()
        if dep_str:
            dep_str += " "
        cmd = "\n".join(
            (f"sbatch --parsable {dep_str}<<'EOF'", self.get_script_body(), "'EOF'")
        )
        return cmd

    def submit(self) -> Self:
        """Submits this corrend job. In case of dependencies that were pass as `Job`
        objects, the `submit` method will be executed for the all the dependencies that
        were not submitted.

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
        jobid = proc.stdout.decode().strip()
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
        deps = defaultdict(list)
        for after, dep, time in self._deps:
            deps[f"after{after}" if after != "singleton" else after].append((dep, time))

        deps_list = []
        for after, value in deps.items():
            if after == "singleton":
                deps_list.append("singleton")
                continue

            jobs = (
                (
                    f"{job.job_id if isinstance(job, Job) else job}"
                    f"{f'+{time}' if time else ''}"
                )
                for job, time in value
            )
            after_str = f"{after}:" + ":".join(jobs)
            deps_list.append(after_str)

        deps_list = self._dep_sep.join(deps_list)
        return deps_list

    def _dep_str(self) -> str:
        if len(self._deps) == 0:
            return ""

        dep_str = f"-d {self._dep_list_str()}"
        return dep_str
