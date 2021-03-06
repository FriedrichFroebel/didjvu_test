# encoding=UTF-8

# Copyright © 2015 Jakub Wilk <jwilk@jwilk.net>
#
# This file is part of didjvu.
#
# didjvu is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# didjvu is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
# for more details.

import io
import os
import shutil
from unittest import mock, TestCase

from .tools import (
    assert_equal,
    assert_greater,
    assert_image_sizes_equal,
    assert_images_equal,
    assert_raises,
)

from PIL import Image as pil

from lib import djvu_support as djvu
from lib import ipc
from lib import temporary

datadir = os.path.join(os.path.dirname(__file__), 'data')

def setup_module():
    djvu.require_cli()

def ddjvu(djvu_file, fmt='ppm'):
    cmdline = ['ddjvu', '-1', '-format=' + fmt]
    stdio = dict(
        stdout=ipc.PIPE,
        stderr=ipc.PIPE
    )
    if isinstance(djvu_file, str):
        djvu_path = djvu_file
        cmdline += [djvu_path]
    else:
        stdio.update(stdin=djvu_file)
    child = ipc.Subprocess(cmdline, **stdio)
    stdout, stderr = child.communicate()
    stderr = stderr.decode()
    if child.returncode != 0:
        raise RuntimeError('ddjvu failed')
    if stderr != '':
        raise RuntimeError('ddjvu stderr: ' + stderr)
    out_file = io.BytesIO(stdout)
    return pil.open(out_file)

def test_bitonal_to_djvu():
    path = os.path.join(datadir, 'onebit.bmp')
    in_image = pil.open(path)
    djvu_file = djvu.bitonal_to_djvu(in_image)
    out_image = ddjvu(djvu_file, fmt='pbm')
    assert_images_equal(in_image, out_image)

def test_photo_to_djvu():
    path = os.path.join(datadir, 'ycbcr-jpeg.tiff')
    in_image = pil.open(path)
    in_image = in_image.convert('RGB')
    mask_image = in_image.convert('1')
    djvu_file = djvu.photo_to_djvu(in_image, mask_image=mask_image)
    out_image = ddjvu(djvu_file, fmt='ppm')
    assert_image_sizes_equal(in_image, out_image)

def test_djvu_iw44():
    path = os.path.join(datadir, 'ycbcr.djvu')
    in_djvu = open(path, 'rb')
    out_djvu = djvu.djvu_to_iw44(in_djvu)
    in_image = ddjvu(in_djvu, fmt='ppm')
    out_image = ddjvu(out_djvu, fmt='ppm')
    assert_image_sizes_equal(in_image, out_image)
    in_djvu.seek(0)
    in_data = in_djvu.read()
    out_djvu.seek(0)
    out_data = out_djvu.read()
    assert_greater(len(in_data), len(out_data))

class test_multichunk():

    def test_sjbz(self):
        path = os.path.join(datadir, 'onebit.bmp')
        in_image = pil.open(path)
        [width, height] = in_image.size
        sjbz_path = os.path.join(datadir, 'onebit.djvu')
        multichunk = djvu.Multichunk(width, height, 100, sjbz=sjbz_path)
        djvu_file = multichunk.save()
        out_image = ddjvu(djvu_file, fmt='pbm')
        assert_images_equal(in_image, out_image)

    def test_incl(self):
        path = os.path.join(datadir, 'onebit.bmp')
        in_image = pil.open(path)
        [width, height] = in_image.size
        sjbz_path = os.path.join(datadir, 'onebit.djvu')
        incl_path = os.path.join(datadir, 'shared_anno.iff')
        multichunk = djvu.Multichunk(width, height, 100, sjbz=sjbz_path, incl=incl_path)
        djvu_file = multichunk.save()
        with temporary.directory() as tmpdir:
            tmp_djvu_path = os.path.join(tmpdir, 'index.djvu')
            tmp_incl_path = os.path.join(tmpdir, 'shared_anno.iff')
            os.link(djvu_file.name, tmp_djvu_path)
            shutil.copyfile(incl_path, tmp_incl_path)
            out_image = ddjvu(tmp_djvu_path, fmt='pbm')
            assert_images_equal(in_image, out_image)

class test_validate_page_id():

    def test_empty(self):
        with assert_raises(ValueError) as ecm:
            djvu.validate_page_id('')
        assert_equal(str(ecm.exception), 'page identifier must end with the .djvu extension')

    def test_bad_char(self):
        with assert_raises(ValueError) as ecm:
            djvu.validate_page_id('eggs/ham.djvu')
        assert_equal(str(ecm.exception), 'page identifier must consist only of lowercase ASCII letters, digits, _, +, - and dot')

    def test_leading_bad_char(self):
        with assert_raises(ValueError) as ecm:
            djvu.validate_page_id('.eggs.djvu')
        assert_equal(str(ecm.exception), 'page identifier cannot start with +, - or a dot')

    def test_dot_dot(self):
        with assert_raises(ValueError) as ecm:
            djvu.validate_page_id('eggs..djvu')
        assert_equal(str(ecm.exception), 'page identifier cannot contain two consecutive dots')

    def test_bad_extension(self):
        with assert_raises(ValueError) as ecm:
            djvu.validate_page_id('eggs.png')
        assert_equal(str(ecm.exception), 'page identifier must end with the .djvu extension')

    def test_ok(self):
        n = 'eggs.djvu'
        assert_equal(djvu.validate_page_id(n), n)


class BundleDjvuViaIndirectTestCase(TestCase):
    def test_string_versus_bytes_issue(self):
        # Simplify the test by mocking away the subprocess communication which does
        # not directly influence the error.
        with mock.patch.object(djvu.ipc.Subprocess, 'wait'):
            djvu_path = djvu.bundle_djvu_via_indirect(
                *[os.path.join(datadir, 'onebit.png')]
            )
            self.assertTrue(os.path.exists(djvu_path.name))


# vim:ts=4 sts=4 sw=4 et
