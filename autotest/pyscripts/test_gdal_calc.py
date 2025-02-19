#!/usr/bin/env pytest
# -*- coding: utf-8 -*-
###############################################################################
# $Id: test_gdal_calc.py 25549 2013-01-26 11:17:10Z rouault $
#
# Project:  GDAL/OGR Test Suite
# Purpose:  gdal_calc.py testing
# Author:   Etienne Tourigny <etourigny dot dev @ gmail dot com>
#
###############################################################################
# Copyright (c) 2013, Even Rouault <even dot rouault @ spatialys.com>
# Copyright (c) 2014, Etienne Tourigny <etourigny dot dev @ gmail dot com>
# Copyright (c) 2020, Idan Miara <idan@miara.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
###############################################################################

import os
import shutil
from collections import defaultdict
from copy import copy

import pytest
import test_py_scripts

from osgeo import gdal

# test that numpy is available, if not skip all tests
np = pytest.importorskip("numpy")
gdal_calc = pytest.importorskip("osgeo_utils.gdal_calc")
gdal_array = pytest.importorskip("osgeo.gdal_array")
try:
    GDALTypeCodeToNumericTypeCode = gdal_array.GDALTypeCodeToNumericTypeCode
except AttributeError:
    pytestmark = pytest.mark.skip(
        "osgeo.gdal_array.GDALTypeCodeToNumericTypeCode is unavailable"
    )

pytestmark = pytest.mark.skipif(
    test_py_scripts.get_py_script("gdal_calc") is None,
    reason="gdal_calc not available",
)


@pytest.fixture()
def script_path():
    return test_py_scripts.get_py_script("gdal_calc")


###############################################################################
#


def test_gdal_calc_help(script_path):

    assert "ERROR" not in test_py_scripts.run_py_script(
        script_path, "gdal_calc", "--help"
    )


###############################################################################
#


def test_gdal_calc_version(script_path):

    assert "ERROR" not in test_py_scripts.run_py_script(
        script_path, "gdal_calc", "--version"
    )


# Usage: gdal_calc.py [-A <filename>] [--A_band] [-B...-Z filename] [other_options]


def check_file(filename_or_ds, checksum, i=None, bnd_idx=1):
    if gdal_calc.is_path_like(filename_or_ds):
        ds = gdal.Open(os.fspath(filename_or_ds))
    else:
        ds = filename_or_ds
    assert ds is not None, f'ds{i if i is not None else ""} not found'
    ds_checksum = ds.GetRasterBand(bnd_idx).Checksum()
    if checksum is None:
        print(f"ds{i} bnd{bnd_idx} checksum is {ds_checksum}")
    else:
        assert (
            ds_checksum == checksum
        ), f"ds{i} bnd{bnd_idx} wrong checksum, expected {checksum}, got {ds_checksum}"
    return ds


temp_counter_dict = defaultdict(int)
opts_counter_counter = 0
input_checksum = (12603, 58561, 36064, 10807)


def get_input_file():
    infile = make_temp_filename(0)
    if not os.path.isfile(infile):
        shutil.copy(
            test_py_scripts.get_data_path("gcore") + "stefan_full_rgba.tif", infile
        )
    return infile


def format_temp_filename(test_id, idx, is_opt=False):
    if not is_opt:
        out_template = "tmp/test_gdal_calc_py{}.tif"
        return out_template.format(
            "" if test_id == 0 else "_{}_{}".format(test_id, idx)
        )
    else:
        opts_template = "tmp/opt{}"
        return opts_template.format(idx)


def make_temp_filename(test_id, is_opt=False):
    if not is_opt:
        global temp_counter_dict
        temp_counter_dict[test_id] = 1 + (temp_counter_dict[test_id] if test_id else 0)
        idx = temp_counter_dict[test_id]
    else:
        global opts_counter_counter
        opts_counter_counter = opts_counter_counter + 1
        idx = opts_counter_counter
    return format_temp_filename(test_id, idx, is_opt)


def make_temp_filename_list(test_id, test_count, is_opt=False):
    return list(make_temp_filename(test_id, is_opt) for _ in range(test_count))


def test_gdal_calc_py_1(script_path):
    """test basic copy"""

    infile = get_input_file()
    test_id, test_count = 1, 3
    out = make_temp_filename_list(test_id, test_count)

    test_py_scripts.run_py_script(
        script_path, "gdal_calc", f"-A {infile} --calc=A --overwrite --outfile {out[0]}"
    )
    test_py_scripts.run_py_script(
        script_path,
        "gdal_calc",
        f"-A {infile} --A_band=2 --calc=A --overwrite --outfile {out[1]}",
    )
    test_py_scripts.run_py_script(
        script_path,
        "gdal_calc",
        f"-Z {infile} --Z_band=2 --calc=Z --overwrite --format GTiff --outfile {out[2]}",
    )

    for i, checksum in zip(
        range(test_count), (input_checksum[0], input_checksum[1], input_checksum[1])
    ):
        check_file(out[i], checksum, i + 1)

    # Test update
    ds = gdal.Open(out[2], gdal.GA_Update)
    ds.GetRasterBand(1).Fill(0)
    ds = None
    test_py_scripts.run_py_script(
        script_path, "gdal_calc", f"-Z {infile} --Z_band=2 --calc=Z --outfile {out[2]}"
    )
    check_file(out[2], input_checksum[1])

    # Test un-intended updated
    ds = gdal.Open(out[2], gdal.GA_Update)
    ds.GetRasterBand(1).Fill(0)
    zero_cs = ds.GetRasterBand(1).Checksum()
    ds = None
    test_py_scripts.run_py_script(
        script_path,
        "gdal_calc",
        f"-Z {infile} --Z_band=2 --calc=Z --format GTiff --outfile {out[2]}",
    )
    check_file(out[2], zero_cs)


def test_gdal_calc_py_2(script_path):
    """test simple formulas"""

    infile = get_input_file()
    test_id, test_count = 2, 3
    out = make_temp_filename_list(test_id, test_count)

    test_py_scripts.run_py_script(
        script_path,
        "gdal_calc",
        f"-A {infile} --A_band 1 -B {infile} --B_band 2 --calc=A+B "
        f"--overwrite --outfile {out[0]}",
    )
    test_py_scripts.run_py_script(
        script_path,
        "gdal_calc",
        f"-A {infile} --A_band 1 -B {infile} --B_band 2 --calc=A*B "
        f"--overwrite --outfile {out[1]}",
    )
    test_py_scripts.run_py_script(
        script_path,
        "gdal_calc",
        f'-A {infile} --A_band 1 --calc="sqrt(A)" --type=Float32 '
        f"--overwrite --outfile {out[2]}",
    )

    for i, checksum in zip(range(test_count), (12368, 62785, 47132)):
        check_file(out[i], checksum, i + 1)


def test_gdal_calc_py_3(script_path):
    """test --allBands option (simple copy)"""

    infile = get_input_file()
    test_id, test_count = 3, 1
    out = make_temp_filename_list(test_id, test_count)

    test_py_scripts.run_py_script(
        script_path,
        "gdal_calc",
        f"-A {infile} --allBands A --calc=A --overwrite --outfile {out[0]}",
    )

    bnd_count = 4
    for i, checksum in zip(range(bnd_count), input_checksum[0:bnd_count]):
        check_file(out[0], checksum, 1, bnd_idx=i + 1)


def test_gdal_calc_py_4(script_path):
    """test --allBands option (simple calc)"""

    infile = get_input_file()
    test_id, test_count = 4, 3
    out = make_temp_filename_list(test_id, test_count)

    # some values are clipped to 255, but this doesn't matter... small values were visually checked
    test_py_scripts.run_py_script(
        script_path, "gdal_calc", f"-A {infile} --calc=1 --overwrite --outfile {out[0]}"
    )
    test_py_scripts.run_py_script(
        script_path,
        "gdal_calc",
        f"-A {infile} -B {out[0]} --B_band 1 --allBands A --calc=A+B --NoDataValue=999 "
        f"--overwrite --outfile {out[1]}",
    )

    bnd_count = 3
    for i, checksum in zip(range(bnd_count), (29935, 13128, 59092)):
        check_file(out[1], checksum, 2, bnd_idx=i + 1)
        # also check NoDataValue
        ds = gdal.Open(out[1])
        assert ds.GetRasterBand(i + 1).GetNoDataValue() == 999

    # these values were not tested
    test_py_scripts.run_py_script(
        script_path,
        "gdal_calc",
        f"-A {infile} -B {infile} --B_band 1 --allBands A --calc=A*B --NoDataValue=999 "
        f"--overwrite --outfile {out[2]}",
    )

    bnd_count = 3
    for i, checksum in zip(range(bnd_count), (10025, 62785, 10621)):
        check_file(out[2], checksum, 3, bnd_idx=i + 1)
        # also check NoDataValue
        ds = gdal.Open(out[2])
        assert ds.GetRasterBand(i + 1).GetNoDataValue() == 999


def test_gdal_calc_py_5(script_path):
    """test python interface, basic copy"""

    infile = get_input_file()
    test_id, test_count = 5, 4
    out = make_temp_filename_list(test_id, test_count)

    gdal_calc.Calc("A", A=infile, overwrite=True, quiet=True, outfile=out[0])
    gdal_calc.Calc("A", A=infile, A_band=2, overwrite=True, quiet=True, outfile=out[1])
    gdal_calc.Calc("Z", Z=infile, Z_band=2, overwrite=True, quiet=True, outfile=out[2])
    gdal_calc.Calc(
        ["A", "Z"],
        A=infile,
        Z=infile,
        Z_band=2,
        overwrite=True,
        quiet=True,
        outfile=out[3],
    )

    for i, checksum in zip(
        range(test_count), (input_checksum[0], input_checksum[1], input_checksum[1])
    ):
        check_file(out[i], checksum, i + 1)

    bnd_count = 2
    for i, checksum in zip(range(bnd_count), (input_checksum[0], input_checksum[1])):
        check_file(out[3], checksum, 4, bnd_idx=i + 1)


def test_gdal_calc_py_6(script_path):
    """test nodata"""

    test_id, test_count = 6, 2
    out = make_temp_filename_list(test_id, test_count)

    gdal.Translate(
        out[0],
        test_py_scripts.get_data_path("gcore") + "byte.tif",
        options="-a_nodata 74",
    )
    gdal_calc.Calc(
        "A", A=out[0], overwrite=True, quiet=True, outfile=out[1], NoDataValue=1
    )

    for i, checksum in zip(range(test_count), (4672, 4673)):
        ds = check_file(out[i], checksum, i + 1)
        if i == 1:
            result = ds.GetRasterBand(1).ComputeRasterMinMax()
            assert result == (90, 255), "Error! min/max not correct!"
        ds = None


def test_gdal_calc_py_7(script_path):
    """test --optfile"""

    infile = get_input_file()
    test_id, test_count = 7, 4
    out = make_temp_filename_list(test_id, test_count)
    opt_files = make_temp_filename_list(test_id, test_count, is_opt=True)

    with open(opt_files[0], "w") as f:
        f.write(f"-A {infile} --calc=A --overwrite --outfile {out[0]}")

    # Lines in optfiles beginning with '#' should be ignored
    with open(opt_files[1], "w") as f:
        f.write(f"-A {infile} --A_band=2 --calc=A --overwrite --outfile {out[1]}")
        f.write("\n# -A_band=1")

    # options on separate lines should work, too
    opts = (
        f"-Z {infile}",
        "--Z_band=2",
        "--calc=Z",
        "--overwrite",
        f"--outfile  {out[2]}",
    )
    with open(opt_files[2], "w") as f:
        for i in opts:
            f.write(i + "\n")

    # double-quoted options should be read as single arguments. Mixed numbers of arguments per line should work.
    opts = (
        f"-Z {infile} --Z_band=2",
        '--calc "Z + 0"',
        f"--overwrite --outfile {out[3]}",
    )
    with open(opt_files[3], "w") as f:
        for i in opts:
            f.write(i + "\n")
    for opt_prefix in ["--optfile ", "@"]:
        for i, checksum in zip(
            range(test_count),
            (
                input_checksum[0],
                input_checksum[1],
                input_checksum[1],
                input_checksum[1],
            ),
        ):
            test_py_scripts.run_py_script(
                script_path, "gdal_calc", f"{opt_prefix}{opt_files[i]}"
            )
            check_file(out[i], checksum, i + 1)


def test_gdal_calc_py_8(script_path):
    """test multiple calcs"""

    infile = get_input_file()
    test_id, test_count = 8, 1
    out = make_temp_filename_list(test_id, test_count)

    test_py_scripts.run_py_script(
        script_path,
        "gdal_calc",
        f"-A {infile} --A_band=1 -B {infile} --B_band=2 -Z {infile} --Z_band=2 --calc=A --calc=B --calc=Z "
        f"--overwrite --outfile {out[0]}",
    )

    bnd_count = 3
    for i, checksum in zip(
        range(bnd_count), (input_checksum[0], input_checksum[1], input_checksum[1])
    ):
        check_file(out[0], checksum, 1, bnd_idx=i + 1)


def my_sum(a, gdal_dt=None):
    """sum using numpy"""
    np_dt = GDALTypeCodeToNumericTypeCode(gdal_dt)
    concatenate = np.stack(a)
    ret = concatenate.sum(axis=0, dtype=np_dt)
    return ret


def my_max(a):
    """max using numpy"""
    concatenate = np.stack(a)
    ret = concatenate.max(axis=0)
    return ret


def test_gdal_calc_py_9(script_path):
    """
    test calculating sum in different ways. testing the following features:
    * noDataValue
    * user_namespace
    * using output ds
    * mem driver (no output file)
    * single alpha for multiple datasets
    * extent = 'fail'
    """
    infile = get_input_file()
    test_id, test_count = 9, 9
    out = make_temp_filename_list(test_id, test_count)

    common_kwargs = {
        "hideNoData": True,
        "overwrite": True,
        "extent": "fail",
    }
    inputs0 = dict()
    inputs0["a"] = infile

    total_bands = 3
    checksums = [input_checksum[0], input_checksum[1], input_checksum[2]]
    inputs = []
    keep_ds = [True, False, False]
    for i in range(total_bands):
        bnd_idx = i + 1
        inputs0["a_band"] = bnd_idx
        outfile = out[i]
        return_ds = keep_ds[i]
        kwargs = copy(common_kwargs)
        kwargs.update(inputs0)
        ds = gdal_calc.Calc(calc="a", outfile=outfile, **kwargs)
        assert ds.GetRasterBand(1).GetNoDataValue() is None
        if return_ds:
            input_file = ds
        else:
            # the dataset must be closed if we are to read it again
            del ds
            input_file = outfile
        inputs.append(input_file)

        check_file(input_file, checksums[i], i + 1)

    inputs1 = dict()
    inputs1["a"] = inputs[0]
    inputs1["b"] = inputs[1]
    inputs1["c"] = inputs[2]

    inputs2 = {"a": inputs}

    write_output = True
    outfile = [out[i] if write_output else None for i in range(test_count)]

    i = total_bands

    checksum = 13256
    kwargs = copy(common_kwargs)
    kwargs.update(inputs1)
    check_file(
        gdal_calc.Calc(calc="numpy.max((a,b,c),axis=0)", outfile=outfile[i], **kwargs),
        checksum,
        i,
    )
    i += 1
    kwargs = copy(common_kwargs)
    kwargs.update(inputs2)
    check_file(
        gdal_calc.Calc(calc="numpy.max(a,axis=0)", outfile=outfile[i], **kwargs),
        checksum,
        i,
    )
    i += 1
    kwargs = copy(common_kwargs)
    kwargs.update(inputs2)
    check_file(
        gdal_calc.Calc(
            calc="my_neat_max(a)",
            outfile=outfile[i],
            user_namespace={"my_neat_max": my_max},
            **kwargs,
        ),
        checksum,
        i,
    )
    i += 1

    # for summing 3 bytes we'll use GDT_UInt16
    gdal_dt = gdal.GDT_UInt16
    np_dt = GDALTypeCodeToNumericTypeCode(gdal_dt)

    # sum with overflow
    checksum = 12261
    kwargs = copy(common_kwargs)
    kwargs.update(inputs1)
    check_file(
        gdal_calc.Calc(calc="a+b+c", type=gdal_dt, outfile=outfile[i], **kwargs),
        checksum,
        i,
    )
    i += 1

    # sum with numpy function, no overflow
    checksum = 12789
    kwargs = copy(common_kwargs)
    kwargs.update(inputs2)
    check_file(
        gdal_calc.Calc(
            calc="numpy.sum(a,axis=0,dtype=np_dt)",
            type=gdal_dt,
            outfile=outfile[i],
            user_namespace={"np_dt": np_dt},
            **kwargs,
        ),
        checksum,
        i,
    )
    i += 1
    # sum with my custom numpy function
    kwargs = copy(common_kwargs)
    kwargs.update(inputs2)
    check_file(
        gdal_calc.Calc(
            calc="my_neat_sum(a, out_dt)",
            type=gdal_dt,
            outfile=outfile[i],
            user_namespace={"my_neat_sum": my_sum, "out_dt": gdal_dt},
            **kwargs,
        ),
        checksum,
        i,
    )
    i += 1


def test_gdal_calc_py_10(script_path):
    """test --NoDataValue=none"""

    infile = get_input_file()
    test_id, test_count = 10, 4
    out = make_temp_filename_list(test_id, test_count)

    test_py_scripts.run_py_script(
        script_path,
        "gdal_calc",
        f"-A {infile} --A_band=1 --NoDataValue=none --calc=A "
        f"--overwrite --outfile {out[0]}",
    )

    check_file(out[0], input_checksum[0])
    ds = gdal.Open(out[0])
    assert ds.GetRasterBand(1).GetNoDataValue() is None


def test_gdal_calc_py_multiple_inputs_same_alpha(script_path):
    """test multiple values for -A flag, including wildcards"""

    shutil.copy("../gcore/data/byte.tif", "tmp/input_wildcard_1.tif")
    shutil.copy("../gcore/data/byte.tif", "tmp/input_wildcard_2.tif")

    test_py_scripts.run_py_script(
        script_path,
        "gdal_calc",
        '-A ../gcore/data/byte.tif ../gcore/data/byte.tif tmp/input_wildcard_*.tif --calc="sum(A.astype(numpy.float32),axis=0)" --overwrite --outfile tmp/test_gdal_calc_py_multiple_inputs_same_alpha.tif --type Float32 --overwrite',
    )

    test_py_scripts.run_py_script(
        script_path,
        "gdal_calc",
        '-A ../gcore/data/byte.tif --calc="A.astype(numpy.float32)*4" --overwrite --outfile tmp/test_gdal_calc_py_multiple_inputs_same_alpha_ref.tif --type Float32 --overwrite',
    )

    ds = gdal.Open("tmp/test_gdal_calc_py_multiple_inputs_same_alpha.tif")
    cs = ds.GetRasterBand(1).Checksum()
    ds = None

    ds = gdal.Open("tmp/test_gdal_calc_py_multiple_inputs_same_alpha_ref.tif")
    cs_ref = ds.GetRasterBand(1).Checksum()
    ds = None

    gdal.Unlink("tmp/input_wildcard_1.tif")
    gdal.Unlink("tmp/input_wildcard_2.tif")
    gdal.Unlink("tmp/test_gdal_calc_py_multiple_inputs_same_alpha.tif")
    gdal.Unlink("tmp/test_gdal_calc_py_multiple_inputs_same_alpha_ref.tif")

    assert cs == cs_ref


def test_gdal_calc_py_cleanup():
    """cleanup all temporary files that were created in this pytest"""
    global temp_counter_dict
    global opts_counter_counter
    temp_files = []
    for test_id, count in temp_counter_dict.items():
        for i in range(count):
            name = format_temp_filename(test_id, i + 1)
            temp_files.append(name)

    for i in range(opts_counter_counter):
        name = format_temp_filename(test_id, i + 1, True)
        temp_files.append(name)

    for filename in temp_files:
        try:
            os.remove(filename)
        except OSError:
            pass
