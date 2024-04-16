import pytest
from slurmpy import Job


class TestJob:
    def test_init(self):
        name = "Test"
        shebang = "/usr/bin/sh"
        commands = ["echo hello world"]
        job = Job(name, shebang, commands, abc=10)
        assert job.name == "Test"
        assert job.shebang == "/usr/bin/sh"
        assert len(job.commands) == len(commands)
        assert all(job.commands[i] == commands[i] for i in range(len(commands)))
        expected_out = f"#!{shebang}\n\n#SBATCH --abc=10\n\n{commands[0]}"
        assert expected_out == str(job)

    def test_args(self):
        job = Job(
            qwe_qwe="--qwe-qwe",
            __abc="--abc",
            _a="-a",
            b="-b",
            integer=10,
            qwe_abc="--qwe-abc",
            none=None,
        )
        expected_out = (
            "--qwe-qwe=--qwe-qwe --abc=--abc -a -a -b -b --integer=10 "
            "--qwe-abc=--qwe-abc --none"
        )
        assert job.get_args_str() == expected_out

        job = Job()
        job.add_arguments(
            qwe_qwe="--qwe-qwe",
            __abc="--abc",
            _a="-a",
            b="-b",
            integer=10,
            qwe_abc="--qwe-abc",
            none=None,
        )
        expected_out = (
            "--qwe-qwe=--qwe-qwe --abc=--abc -a -a -b -b --integer=10 "
            "--qwe-abc=--qwe-abc --none"
        )
        assert job.get_args_str() == expected_out

    def test_commands(self):
        commands = [
            "echo hello world",
            "echo This is a test",
            "echo Malicious code > /virus",
        ]
        job = Job(commands=commands)
        new_line_char = "\n"
        assert (
            f"#!/bin/bash -l\n\n{new_line_char.join(commands)}" == job.get_script_body()
        )

        job = Job()
        job.add_commands(*commands)
        new_line_char = "\n"
        assert (
            f"#!/bin/bash -l\n\n{new_line_char.join(commands)}" == job.get_script_body()
        )

    def test_chaining(self):
        job1 = Job("test", "shebang", qwe=None, qwe_qwe=123)
        job2 = Job("test", "shebang").add_arguments(qwe=None, qwe_qwe=123)
        assert str(job1) == str(job2)

        job3 = job1.add_dependency("ok", job2)
        assert job3 is job1

    def test_dependecies(self):
        job1 = Job("Job1")

        job2 = Job("Job2")
        job2.add_dependency("any", job1, 10)

        job3 = Job("Job3").add_dependency("", 1234, 4321).add_dependency("notok", 100)

        job4 = Job("Job4").add_dependency("singleton", None).add_dependency("ok", 101)
        job4.dep_sep = "?"

        job5 = Job("Job4").add_singleton_dependency()

        cmd_head = "sbatch --parsable -d "
        cmd_tail = " <<'EOF'\n#!/bin/bash -l\nEOF"

        assert job2._deps["afterany"][0][0] is job1
        assert job2._deps["afterany"][0][1] is None
        assert (
            job3.get_full_command()
            == cmd_head + "after:1234+4321,afternotok:100" + cmd_tail
        )
        assert job4.get_full_command() == cmd_head + "singleton?afterok:101" + cmd_tail
        assert job5.get_full_command() == cmd_head + "singleton" + cmd_tail
