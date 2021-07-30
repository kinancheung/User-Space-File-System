#!/usr/bin/env python
from __future__ import print_function, absolute_import, division

import logging

from collections import defaultdict
from errno import ENOENT
from stat import S_IFDIR, S_IFLNK, S_IFREG
from time import time
import helper
import disktools
import bit

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn

# This file contains methods that are required to work a file system
# Author: Kinan Cheung

if not hasattr(__builtins__, 'bytes'):
    bytes = str


class Memory(LoggingMixIn, Operations):

    def __init__(self):
        self.fd = 0

    # This writes meta data to a block which selects a block to write file data to 
    def create(self, path, mode):
        free_meta_int = helper.free_block()
        free_data_int = helper.free_block()
        helper.update_meta_bit_map(free_meta_int)
        helper.write_meta_data(free_meta_int, (S_IFREG | mode), path, 1, free_data_int)
        self.fd += 1
        return self.fd

    # This returns meta data in specified format
    def getattr(self, path, fh=None):
        meta_block_int = helper.find_block(path)
        if meta_block_int == None:
            # ERROR IF CANT FIND FILE
            raise FuseOSError(ENOENT)
        return helper.read_meta_data(meta_block_int)

    # This returns attributes(meta data) in specified format
    def getxattr(self, path, name, position=0):
        meta_block_int = helper.find_block(path)
        attrs = helper.read_meta_data(meta_block_int)
        try:
            return attrs[name]
        except KeyError:
            return FuseOSError(1)       # Should return ENOATTR

    # Opens file required
    def open(self, path, flags):
        self.fd += 1
        return self.fd

    # Call read data from a block and keep going if more blocks
    # return byte, not string or byte array
    def read(self, path, size, offset, fh):
        meta_block_int = helper.find_block(path)
        data_block_int = helper.get_data_location(meta_block_int)
        block_data = helper.read_data(data_block_int, meta_block_int)
        return bytes(block_data)

    # Read all paths that aren't empty, read meta data names basically without /
    def readdir(self, path, fh):
        meta_file_int = helper.get_meta_bit_map()
        return ['.', '..'] + [helper.get_name(i) for i in range(0,15) if bit.checkBit(meta_file_int, i) != 0]


    # Truncates data (deletes everything for rewrite)
    def truncate(self, path, length, fh=None):
        meta_block_int = helper.find_block(path)
        helper.release_blocks(helper.get_data_location(meta_block_int))
        helper.update_size(meta_block_int, 0)

    # Constants
    def statfs(self, path):
        return dict(f_bsize=512, f_blocks=4096, f_bavail=2048)

    # Delete metadata and data blocks
    def unlink(self, path):
        meta_block_int = helper.find_block(path)
        helper.release_blocks(meta_block_int)

    # Updates a_time and m_time
    def utimens(self, path, times=None):
        now = time()
        atime, mtime = times if times else (now, now)
        helper.update_utimens(path, atime, mtime)

    # Write function to blocks
    def write(self, path, data, offset, fh):
        # Get meta_data and data block locations
        meta_block_int = helper.find_block(path)
        data_block_int = helper.get_data_location(meta_block_int)

        # Read old data from file and add with new data and offset
        old_data = helper.read_data(data_block_int, meta_block_int)
        offset = len(old_data)

        new_data = (old_data[:offset].ljust(offset, '\x00'.encode('ascii'))
        # make sure the data gets inserted at the right offset
        + data
        # and only overwrites the bytes that the data is replacing
        + old_data[offset + len(data):])

        # Write data to blocks
        helper.write_data(new_data, data_block_int)

        # This is supposed to update the size of the data in the meta data block
        helper.update_size(meta_block_int, len(new_data))
        return len(data)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('mount')
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)
    fuse = FUSE(Memory(), args.mount, foreground=True)