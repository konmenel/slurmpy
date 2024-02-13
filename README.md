# slurmpy
A simple python interface for working with SLURM because I am tired of bash.

## Installation
To install the library first clone this repo and cd the directory
```bash
git clone https://github.com/konmenel/slurmpy.git
cd slurmpy
```
And install it using pip
```bash
pip install .
```

## Quick start
Suppose that we have the following script that will be submitted with `sbatch`:
```bash
#!/bin/bash -l

#SBATCH --account=myaccount
#SBATCH --ntasks=2
#SBATCH --cpus-per-task=20
#SBATCH -t 00:10:00

echo hello
echo world
```

The above can be created and submitted using the following python code:
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

## More details
### instantiation
To start all you need to do is create a Job object:
```python
from slurmpy import Job

job = Job()
```
Optionally, a name, a shebang, and list of commands may be passed:
```python
job = Job("Example", "/bin/bash -l", ["echo hello world"])
```
The default values for name, shebang, command list are, `""`, `"/bin/bash -l"`, and
`[]`. Additionally, any argument of `sbatch` can be passed as a key-word argument. In
order to keep with python syntax hyphens should be replaced with underscores. Also,
intiger argument values can be pass as either strings or integers. For instance:
```python
job = Job(cpus_per_tasks=10, ntasks="2")
```

### Adding and removing arguments
More arguments be added later like so:
```python
job = Job(ntasks=10)
job.add_arguments(cpus_per_task=10)
```
Method chaining is also supported:
```python
job = Job(ntasks=10).add_arguments(cpus_per_task=10).add_argument(account="123")
```

To remove arguments you use the `remove_arguments` method:
```python
job = Job(ntasks=10)
job.remove_arguments("ntasks", "cpus-per-task")
```
**Note**: The single or double hyphen at the beginning may be omitted.
 

### Adding commands
Additionally, commands may be added using the method `add_commands` like so:
```python
job = Job(name="Example").add_commands("echo hello", "echo world")
```
or by directly appending to the command list:
```python
job.commands.append("echo hello > hello.txt")
job.commands.append("cat hello.txt")
```

### Adding dependencies
Dependency management is the true reason why this library exists. This model
allow any job to be depended an another job even before the jobs are submited.

Dependencies can be added using the method `add_dependency`. For instance,
if we would like to create a dependency of type `afterok` of a job with id 
1234 we can do it using the following:
```python
job = Job("Depended job").add_dependency(after="ok", dep=123)
```

This is equivalent to what we would do with `sbatch`. In the above we need
to know beforehand id of the dependency. However, we don't know the job's id
is it hasn't been submitted yet. What we can do is pass the a `Job` object instead
as the dependency and the library will do the rest:
```python
job1 = Job("First Job")

job2 = Job("Second Job")
job2.add_dependency(after="ok", dep=job1)
```

See the [Job submission](#job-submission) sections for information on how the dependencies are
submitted

### Job submission
To submit the job simple call the method `submit`. In the case of unsubmitted
dependencies the `submit` method will be called for all dependencies like so:
```python
job1 = Job("First Job")

job2 = Job("Second Job")
job2.add_dependency(after="ok", dep=job1)

job2.submit()   # implicitly calls job1.submit()
```

Once submitted the `job_id` is populated and can be accessed like so:
```python
print(job1.job_id, job2.job_id)
```
If not submitted yet `job_id` will be `None`.

## API Documentation
More details on methods and functions can be found in the the [doc/](doc/) directory. The
documentations was generateded using [pdoc](https://pdoc3.github.io/pdoc/). Just
open the [doc/slurmpy/index.html](doc/slurmpy/index.html) file 

