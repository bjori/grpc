# Copyright 2015, Google Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     * Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above
# copyright notice, this list of conditions and the following disclaimer
# in the documentation and/or other materials provided with the
# distribution.
#     * Neither the name of Google Inc. nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""Helpers to run docker instances as jobs."""

import jobset
import tempfile
import time
import uuid
import os
import subprocess

_DEVNULL = open(os.devnull, 'w')

def wait_for_file(filepath, timeout_seconds=15):
  """Wait until given file exists and returns its content."""
  started = time.time()
  while time.time() - started < timeout_seconds:
    if os.path.isfile(filepath):
      with open(filepath, 'r') as f:
        content = f.read()
        # make sure we don't return empty content
        if content:
          return content
    time.sleep(1)
  raise Exception('Failed to read file %s.' % filepath)


def docker_mapped_port(cid, port):
  """Get port mapped to internal given internal port for given container."""
  output = subprocess.check_output('docker port %s %s' % (cid, port), shell=True)
  return int(output.split(':', 2)[1])


def finish_jobs(jobs):
  """Kills given docker containers and waits for corresponding jobs to finish"""
  for job in jobs:
    job.kill(suppress_failure=True)

  while any(job.is_running() for job in jobs):
    time.sleep(1)


def image_exists(image):
  """Returns True if given docker image exists."""
  return subprocess.call(['docker','inspect', image],
                         stdout=_DEVNULL,
                         stderr=_DEVNULL) == 0


def remove_image(image, skip_nonexistent=False, max_retries=10):
  """Attempts to remove docker image with retries."""
  if skip_nonexistent and not image_exists(image):
    return True
  for attempt in range(0, max_retries):
    if subprocess.call(['docker','rmi', '-f', image]) == 0:
      return True
    time.sleep(2)
  print 'Failed to remove docker image %s' % image
  return False


class DockerJob:
  """Encapsulates a job"""

  def __init__(self, spec):
    self._spec = spec
    self._job = jobset.Job(spec, bin_hash=None, newline_on_success=True, travis=True, add_env={}, xml_report=None)
    self._cidfile = spec.cidfile
    self._cid = None

  def cid(self):
    """Gets cid of this container"""
    if not self._cid:
      self._cid = wait_for_file(self._cidfile)
    return self._cid

  def mapped_port(self, port):
    return docker_mapped_port(self.cid(), port)

  def kill(self, suppress_failure=False):
    """Sends kill signal to the container."""
    if suppress_failure:
      self._job.suppress_failure_message()
    return subprocess.call(['docker','kill', self.cid()]) == 0

  def is_running(self):
    """Polls a job and returns True if given job is still running."""
    return self._job.state(jobset.NoCache()) == jobset._RUNNING
