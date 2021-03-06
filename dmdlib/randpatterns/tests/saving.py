"""
Classes for saving patterns to various formats.
"""

import unittest
import numpy as np
from dmdlib.randpatterns.saving import HfiveSaver, SparseSaver
import os
import tables as tb
import shutil
from scipy import sparse
import json
import csv


class TestHfiveCreation(unittest.TestCase):
    pth = 'saver_tst{}.h5'
    root_attrs = {'a1': 88., 'a2': 'hello'}

    @classmethod
    def setUpClass(self):
        self.h5saver = HfiveSaver(self.pth, overwrite=True, attributes=self.root_attrs)

    def test_no_overwrite(self):
        with self.assertRaises(FileExistsError) as ctx:
            with HfiveSaver(self.pth, overwrite=False) as f:
                pass

    def test_creation(self):
        self.assertTrue(os.path.exists(self.pth))
        with tb.open_file(self.pth) as f:
            self.assertTrue('/patterns' in f)

    def test_attributes(self):
        uuid = self.h5saver.uuid
        with tb.open_file(self.pth, 'r') as f:
            title = f.get_node_attr('/', 'TITLE')  #type: str
            _, uuid_read = title.split(':')
            self.assertEqual(uuid, uuid_read)
            for k, v in self.root_attrs.items():
                a = f.get_node_attr('/', k)
                self.assertEqual(a, v)

    def test_iter(self):
        self.assertEqual(self.h5saver.current_group_id, 'aaa')
        grpname = self.h5saver.iter_pattern_group()
        self.assertEqual(grpname, 'aab')
        self.assertEqual(self.h5saver.current_group_id, grpname)
        # grpname = self.h5saver.iter_pattern_group()
        # self.assertEqual(grpname, 'aac')

    def test_data_add(self):
        data = np.random.randint(0, 2, (100,100,100), dtype=bool)
        attrs = {'test1':32423, 'test2': 'asdfklkn'}
        self.h5saver.store_sequence_array(data, attrs)
        self.h5saver._check_futures(True)
        nodename = '/patterns/{}/000000'.format(self.h5saver.current_group_id)
        with tb.open_file(self.pth, 'r') as f:
            self.assertTrue(nodename in f)
            retrieved = f.get_node(nodename).read()
            for k, v in attrs.items():
                a = f.get_node_attr(nodename, k)
                self.assertEqual(a, v)
        self.assertTrue(np.all(retrieved == data))

    @classmethod
    def tearDownClass(self):
        self.h5saver._check_futures(wait=True)
        os.remove(self.pth)


class TestH5_write_completes(unittest.TestCase):
    pth = 'test2.h5'
    def test_write_complete(self):
        data = [np.random.randint(0,2,(500,500,50), dtype=bool) for _ in range(5)]
        with HfiveSaver(self.pth, overwrite=True) as f:
            for d in data:
                f.store_sequence_array(d)
            self.assertEqual(len(f._futures), len(data))
            current_group = f.current_group_id
            current_leaf = f.current_leaf_id
        self.assertEqual(current_leaf, len(data))
        with tb.open_file(self.pth, 'r') as f2:
            for i, d in enumerate(data):
                ndname = '/patterns/{}/{:06d}'.format(current_group, i)
                self.assertTrue(ndname in f2)
                a = f2.get_node(ndname).read()
                self.assertTrue(np.all(a == d))

    def tearDown(self):
        os.remove(self.pth)


class TestSparseSaver(unittest.TestCase):
    workingdir = 'tst'
    prefix = 'testsparse'
    root_attrs =  {'a1': 'hello, I am here', 'a2': 'goodbye again'}

    @classmethod
    def setUpClass(self):
        os.mkdir(self.workingdir)
        self.saver = SparseSaver(self.workingdir, self.prefix, overwrite=True, attributes=self.root_attrs)

    def test_creation(self):
        """tests that files are created."""
        self.assertTrue(os.path.exists(os.path.join(self.workingdir, self.prefix+'.json')))
        with open(self.saver.store_path, 'r') as f:
            j_dict = json.load(f)
        for k, v in self.root_attrs.items():
            self.assertEqual(j_dict[k], v)
        self.assertEqual(j_dict['uuid'], self.saver.uuid)

    def test_store(self):
        """
        Tests that data are stored correctly as a sparse matrix. Tests that attribute data csv file is generated as
        expected and that attributes of the data are saved as specified.
        """
        n, h, w = (50,500, 50)
        data = np.random.randint(0,2, (n, h,w), dtype=bool)
        attrs = {'hello': 'goodbye', 'another': 'value'}
        self.saver.store_sequence_array(data.astype(bool), attrs)

        fn = self.saver._path_start + "_{}:{:06d}.sparse.npz".format(
            self.saver.current_group_id, self.saver.current_leaf_id-1)
        ar = sparse.load_npz(fn)  #type: sparse.csr_matrix
        d = np.asarray(ar.todense(), )
        d.shape = n, h, w
        self.assertTrue(np.all(data == d))

        self.assertTrue(os.path.exists(self.saver.framedata_path))
        self.saver._framedata_file.flush()
        with open(self.saver.framedata_path) as f:
            mycsv = csv.DictReader(f)
            l1 = next(mycsv)
        for k, v in attrs.items():
            t = type(v)
            self.assertEqual(v, t(l1[k]))

    @classmethod
    def tearDownClass(self):
        shutil.rmtree(self.workingdir)


if __name__ == '__main__':
    unittest.main(verbosity=4)