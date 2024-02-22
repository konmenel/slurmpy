# import os
from __future__ import annotations
from collections import defaultdict
from collections.abc import Iterable
import subprocess
from typing import Optional, Sequence
try:
    from typing import Self
except ImportError:
    from ._self_type import Self


class Job:
    """Object that manages the job creation and submission of `sbatch`."""

    # Public
    name: str
    shebang: str  # Default: /bin/bash -l
    commands: list[str]

    # Private
    _job_id: Optional[int]
    _args: dict[str, Optional[str]]
    _deps: dict[str, list[tuple[Job | str, Optional[int]]]]     # Format: after_str: list of (Job or job_id, time or None)
    _dep_sep: str  # Default ','

    def __init__(
        self,
        name="",
        shebang="/bin/bash -l",
        commands: list[str] = None,
        **kwargs,
    ) -> None:
        """
        Parameters
        ----------
        name : str, optional
            Optional, each job can have a name identification purposes, by default "".
        shebang : str, optional
            The shebang that will be used in the submission script, by default
            "/bin/bash -l".
        commands : list of str, optional
            A list of the commands that will be excecuted when the script
            is submitted, by default None.
        **kwargs
            Any argument of `sbatch` may be passed as a key word argument. However, to
            keep with python syntax, any hyphen (-) would be replaced with unterscore
            (_). Also, the starting hyphen or double hyphen (`-` or `--`) be be omitted.
            For instance, the arguments `--ntasks=1`, `--cpus-per-task=10` may be passed
            when creating the object as `Job(ntasks=1, cpus_per_task=10)`.

        Examples
        --------
        ```python
        from slurmpy import Job

        job = Job(
            commands=["echo hello", "echo world"],
            account="myaccount",
            ntasks=2,
            cpus_per_task=20,
            t="00:10:00"
        )
        job.submit()
        ```

        The python code is equivalent to the bash script below:
        ```bash
        #!/bin/bash -l

        #SBATCH --account=myaccount
        #SBATCH --ntasks=2
        #SBATCH --cpus-per-task=20
        #SBATCH -t 00:10:00

        echo hello
        echo world
        ```
        """
        self.name = name
        self.shebang = shebang
        self.commands = list(commands) if commands is not None else []
        self._job_id = None
        self._deps = defaultdict(list)
        self._dep_sep = ","

        self._args = {}
        for key, value in kwargs.items():
            key = self._parse_argname(key)
            value = self._parse_argvalues(value)
            self._args[key] = value

    @property
    def args(self) -> dict[str, Optional[str]]:
        """dict with str keys and optional str values : The dictionary of all arguments
        that will be passed to sbatch using the `SBATCH` directive.
        """
        return self._args

    @property
    def job_id(self) -> Optional[int]:
        """int or None :  The id of the submitted job. If the job has not been
        submitted yet `None` is returned.
        """
        if self._job_id is None:
            print("[WARNING] Job has not been submitted yet!")
        return self._job_id

    @property
    def dep_sep(self) -> str:
        """The dependencies seperator, either ',' or '?'."""
        return self._dep_sep

    @dep_sep.setter
    def dep_sep(self, sep: str) -> None:
        if sep not in (",", "?"):
            print("Only ',' , '?' dependency seperators may be used!")
            return self
        self._dep_sep = sep

    def set_dependency_sep(self, sep: str) -> Self:
        """Change the dependencies seperator to ',' or '?'.

        Parameters
        ----------
        sep : str
            The seperator.

        Returns
        -------
        Job
            Returns the `self` instance.
        """
        self.dep_sep = sep
        return self

    def add_arguments(self, **kwargs) -> Self:
        """Add an argument to sbatch.

        Parameters
        ----------
        **kwargs
            Any argument of `sbatch` may be passed as a key word argument. However, to
            keep with python syntax, any hyphen (-) would be replaced with unterscore
            (_). Also, the starting hyphen or double hyphen (`-` or `--`) be be omitted.
            For instance, the arguments `--ntasks=1`, `--cpus-per-task=10` may be passed
            as `job.add_arguments(ntasks=1, cpus_per_task=10)`.

        Returns
        -------
        Job
            Returns the `self` instance.

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

    def remove_arguments(self, *args: str) -> Self:
        """Add an argument to sbatch.

        Parameters
        ----------
        *args : unpacked list of str
            Any argument of `sbatch` may be passed as a key word argument. Also,
            the starting hyphen or double hyphen (`-` or `--`) be be omitted. For
            instance, the arguments `--ntasks`, `--cpus-per-task` may be removed
            like by calling `job.remove_arguments("ntasks", "cpus-per-tasks")`.

        Returns
        -------
        Job
            Returns the `self` instance.
        """
        for key in args:
            key = self._parse_argname(key)
            if key in self._args:
                self._args.pop(key)
        return self

    def add_account(self, account: str) -> Self:
        """Add an account argument to `sbatch`, i.e. `--account`.

        Parameters
        ----------
        account : str
            The accont id string.

        Returns
        -------
        Job
            Returns the `self` instance.
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

    def add_dependency(
        self,
        after: str,
        dep: Job | str | int,
        time: Optional[int | str] = None,
    ) -> Self:
        """Adds a dependency to this job. The dependency can be a string or an int
        inticating the job id if the dependency. In the case of a dependency that
        has not been submitted yet, the dependency can be a different object of the
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
        Job
            Returns the `self` instance.
        """
        if dep is self:
            print("[WARNING] Dependency cannot be the same some job as this one.")
            return self
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
        after = f"after{after.lower()}"
        self._deps[after].append((dep, time))
        return self

    def add_singleton_dependency(self) -> Self:
        """Adds a singleton dependency to this job.

        Returns
        -------
        Job
            Returns the `self` instance.
        """
        self._deps["singleton"] = []
        return self

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
        Job
            Returns the `self` instance.

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
        Job
            Returns the `self` instance.
        """
        for dep_list in self._deps.values():
            for dep in dep_list:
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
        arg = arg.lstrip("_")
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
        deps_list = []
        for after, value in self._deps.items():
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
