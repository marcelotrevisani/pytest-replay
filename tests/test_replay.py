import pytest


@pytest.fixture
def suite(testdir):
    testdir.makepyfile(
        test_1="""
            def test_foo():
                pass
            def test_bar():
                pass
        """,
        test_2="""
            def test_zz():
                pass
        """,
        test_3="""
            def test_foobar():
                pass
        """,
    )


def test_normal_execution(suite, testdir):
    """Ensure scripts are created and the tests are executed when using --replay."""
    dir = testdir.tmpdir / "replay"
    result = testdir.runpytest("test_1.py", f"--replay-record-dir={dir}")

    result.stdout.fnmatch_lines(f"*replay dir: {dir}")

    replay_file = dir / ".pytest-replay.txt"
    contents = replay_file.readlines(True)
    expected = ["test_1.py::test_foo\n", "test_1.py::test_bar\n"]
    assert contents == expected
    assert result.ret == 0

    result = testdir.runpytest(f"--replay={replay_file}")
    assert result.ret == 0
    result.stdout.fnmatch_lines(["test_1.py*100%*", "*= 2 passed, 2 deselected in *="])


@pytest.mark.parametrize("do_crash", [True, False])
def test_crash(testdir, do_crash):
    testdir.makepyfile(
        test_crash="""
        import os
        def test_crash():
            if {do_crash}:
                os._exit(1)
        def test_normal():
            pass
    """.format(
            do_crash=do_crash
        )
    )
    dir = testdir.tmpdir / "replay"
    result = testdir.runpytest_subprocess(f"--replay-record-dir={dir}")

    contents = (dir / ".pytest-replay.txt").read()
    test_id = "test_crash.py::test_normal"
    if do_crash:
        assert test_id not in contents
        assert result.ret != 0
    else:
        assert test_id in contents
        assert result.ret == 0


def test_xdist(testdir):
    testdir.makepyfile(
        """
        import pytest
        @pytest.mark.parametrize('i', range(10))
        def test(i):
            pass
    """
    )
    dir = testdir.tmpdir / "replay"
    procs = 2
    testdir.runpytest_subprocess("-n", str(procs), f"--replay-record-dir={dir}")

    files = dir.listdir()
    assert len(files) == procs
    test_ids = []
    for f in files:
        test_ids.extend(x.strip() for x in f.readlines())
    expected_ids = [f"test_xdist.py::test[{x}]" for x in range(10)]
    assert sorted(test_ids) == sorted(expected_ids)


@pytest.mark.parametrize("reverse", [True, False])
def test_alternate_serial_parallel_does_not_erase_runs(suite, testdir, reverse):
    """xdist and normal runs should not erase each other's files."""
    command_lines = [
        ("-n", "2", "--replay-record-dir=replay"),
        ("--replay-record-dir=replay",),
    ]
    if reverse:
        command_lines.reverse()
    for command_line in command_lines:
        result = testdir.runpytest_subprocess(*command_line)
        assert result.ret == 0
    assert set(x.basename for x in (testdir.tmpdir / "replay").listdir()) == {
        ".pytest-replay.txt",
        ".pytest-replay-gw0.txt",
        ".pytest-replay-gw1.txt",
    }


def test_cwd_changed(testdir):
    """Ensure that the plugin works even if some tests changes cwd."""
    testdir.tmpdir.join("subdir").ensure(dir=1)
    testdir.makepyfile(
        """
        import os
        def test_1():
            os.chdir('subdir')
        def test_2():
            pass
    """
    )
    dir = testdir.tmpdir / "replay"
    result = testdir.runpytest_subprocess("--replay-record-dir={}".format("replay"))
    replay_file = dir / ".pytest-replay.txt"
    contents = replay_file.readlines(True)
    expected = ["test_cwd_changed.py::test_1\n", "test_cwd_changed.py::test_2\n"]
    assert contents == expected
    assert result.ret == 0
