# -*- coding: utf-8 -*-
#
# Copyright 2012-2015 Spotify AB
# Modifications copyright (C) 2018 databand.ai
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
# This file has been modified by databand.ai to support dbnd orchestration and tracking.


import io
import os
import signal
import subprocess

from targets.config import get_local_tempfile


class FileWrapper(object):
    """
    Wrap `file` in a "real" so stuff can be added to it after creation.
    """

    def __init__(self, file_object):
        self._subpipe = file_object

    def __getattr__(self, name):
        # forward calls to 'write', 'close' and other methods not defined below
        return getattr(self._subpipe, name)

    def __enter__(self, *args, **kwargs):
        # instead of returning whatever is returned by __enter__ on the subpipe
        # this returns self, so whatever custom injected methods are still available
        # this might cause problems with custom file_objects, but seems to work
        # fine with standard python `file` objects which is the only default use
        return self

    def __exit__(self, *args, **kwargs):
        return self._subpipe.__exit__(*args, **kwargs)

    def __iter__(self):
        return iter(self._subpipe)


class InputPipeProcessWrapper(object):
    def __init__(self, command, input_pipe=None):
        """
        Initializes a InputPipeProcessWrapper instance.

        :param command: a subprocess.Popen instance with stdin=input_pipe and
                        stdout=subprocess.PIPE.
                        Alternatively, just its args argument as a convenience.
        """
        self._command = command

        self._input_pipe = input_pipe
        self._original_input = True

        if input_pipe is not None:
            try:
                input_pipe.fileno()
            except AttributeError:
                # subprocess require a fileno to work, if not present we copy to disk first
                self._original_input = False
                self._tmp_file = get_local_tempfile("databand-process_tmp")
                with open(self._tmp_file, "wb") as f:
                    self._tmp_file = f.name
                    while True:
                        chunk = input_pipe.read(io.DEFAULT_BUFFER_SIZE)
                        if not chunk:
                            break
                        f.write(chunk)
                    input_pipe.close()

                self._input_pipe = FileWrapper(
                    io.BufferedReader(io.FileIO(self._tmp_file, "r"))
                )

        self._process = (
            command
            if isinstance(command, subprocess.Popen)
            else self.create_subprocess(command)
        )
        # we want to keep a circular reference to avoid garbage collection
        # when the object is used in, e.g., pipe.read()
        self._process._selfref = self

    def create_subprocess(self, command):
        """
        http://www.chiark.greenend.org.uk/ucgi/~cjwatson/blosxom/2009-07-02-python-sigpipe.html
        """

        def subprocess_setup():
            # Python installs a SIGPIPE handler by default. This is usually not what
            # non-Python subprocesses expect.
            signal.signal(signal.SIGPIPE, signal.SIG_DFL)

        return subprocess.Popen(
            command,
            stdin=self._input_pipe,
            stdout=subprocess.PIPE,
            preexec_fn=subprocess_setup,
            close_fds=True,
        )

    def _finish(self):
        # Need to close this before input_pipe to get all SIGPIPE messages correctly
        self._process.stdout.close()
        if not self._original_input and os.path.exists(self._tmp_file):
            os.remove(self._tmp_file)

        if self._input_pipe is not None:
            self._input_pipe.close()

        self._process.wait()  # deadlock?
        if self._process.returncode not in (0, 141, 128 - 141):
            # 141 == 128 + 13 == 128 + SIGPIPE - normally processes exit with 128 + {reiceived SIG}
            # 128 - 141 == -13 == -SIGPIPE, sometimes python receives -13 for some subprocesses
            raise RuntimeError(
                "Error reading from pipe. Subcommand exited with non-zero exit status %s."
                % self._process.returncode
            )

    def close(self):
        self._finish()

    def __del__(self):
        self._finish()

    def __enter__(self):
        return self

    def _abort(self):
        """
        Call _finish, but eat the exception (if any).
        """
        try:
            self._finish()
        except KeyboardInterrupt:
            raise
        except BaseException:
            pass

    def __exit__(self, type, value, traceback):
        if type:
            self._abort()
        else:
            self._finish()

    def __getattr__(self, name):
        if name in ["_process", "_input_pipe"]:
            raise AttributeError(name)
        try:
            return getattr(self._process.stdout, name)
        except AttributeError:
            return getattr(self._input_pipe, name)

    def __iter__(self):
        for line in self._process.stdout:
            yield line
        self._finish()

    def readable(self):
        return True

    def writable(self):
        return False

    def seekable(self):
        return False


class OutputPipeProcessWrapper(object):
    WRITES_BEFORE_FLUSH = 10000

    def __init__(self, command, output_pipe=None):
        self.closed = False
        self._command = command
        self._output_pipe = output_pipe
        self._process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=output_pipe, close_fds=True
        )
        self._flushcount = 0

    def write(self, *args, **kwargs):
        self._process.stdin.write(*args, **kwargs)
        self._flushcount += 1
        if self._flushcount == self.WRITES_BEFORE_FLUSH:
            self._process.stdin.flush()
            self._flushcount = 0

    def writeLine(self, line):
        assert "\n" not in line
        self.write(line + "\n")

    def _finish(self):
        """
        Closes and waits for subprocess to exit.
        """
        if self._process.returncode is None:
            self._process.stdin.flush()
            self._process.stdin.close()
            self._process.wait()
            self.closed = True

    def __del__(self):
        if not self.closed:
            self.abort()

    def __exit__(self, type, value, traceback):
        if type is None:
            self.close()
        else:
            self.abort()

    def __enter__(self):
        return self

    def close(self):
        self._finish()
        if self._process.returncode == 0:
            if self._output_pipe is not None:
                self._output_pipe.close()
        else:
            raise RuntimeError("Error when executing command %s" % self._command)

    def abort(self):
        self._finish()

    def __getattr__(self, name):
        if name in ["_process", "_output_pipe"]:
            raise AttributeError(name)
        try:
            return getattr(self._process.stdin, name)
        except AttributeError:
            return getattr(self._output_pipe, name)

    def readable(self):
        return False

    def writable(self):
        return True

    def seekable(self):
        return False


class BaseWrapper(object):
    def __init__(self, stream, *args, **kwargs):
        self._stream = stream
        try:
            super(BaseWrapper, self).__init__(stream, *args, **kwargs)
        except TypeError:
            pass

    def __getattr__(self, name):
        if name == "_stream":
            raise AttributeError(name)
        return getattr(self._stream, name)

    def __enter__(self):
        self._stream.__enter__()
        return self

    def __exit__(self, *args):
        self._stream.__exit__(*args)

    def __iter__(self):
        try:
            for line in self._stream:
                yield line
        finally:
            self.close()


class IOPipeline(object):
    """
    Interface for format specifications.
    """

    @classmethod
    def pipe_reader(cls, input_pipe):
        raise NotImplementedError()

    @classmethod
    def pipe_writer(cls, output_pipe):
        raise NotImplementedError()

    def __rshift__(self, other):
        return ChainFormat(self, other)


class ChainFormat(IOPipeline):
    def __init__(self, *args, **kwargs):
        self.args = args
        try:
            self.input = args[0].input
        except AttributeError:
            pass
        try:
            self.output = args[-1].output
        except AttributeError:
            pass
        if not kwargs.get("check_consistency", True):
            return
        for x in range(len(args) - 1):
            try:
                if args[x].output != args[x + 1].input:
                    raise TypeError(
                        "The format chaining is not valid, %s expect %s"
                        " but %s provide %s"
                        % (
                            args[x + 1].__class__.__name__,
                            args[x + 1].input,
                            args[x].__class__.__name__,
                            args[x].output,
                        )
                    )
            except AttributeError:
                pass

    def pipe_reader(self, input_pipe):
        for x in reversed(self.args):
            input_pipe = x.pipe_reader(input_pipe)
        return input_pipe

    def pipe_writer(self, output_pipe):
        for x in reversed(self.args):
            output_pipe = x.pipe_writer(output_pipe)
        return output_pipe


class NopPipeline(IOPipeline):
    def pipe_reader(self, input_pipe):
        return input_pipe

    def pipe_writer(self, output_pipe):
        return output_pipe


class WrappedFormat(IOPipeline):
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def pipe_reader(self, input_pipe):
        return self.wrapper_cls(input_pipe, *self.args, **self.kwargs)

    def pipe_writer(self, output_pipe):
        return self.wrapper_cls(output_pipe, *self.args, **self.kwargs)
