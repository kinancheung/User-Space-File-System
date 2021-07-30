from __future__ import print_function, division
import io
import os
import disktools
import helper
from stat import S_IFDIR

# This file sets up my-disk to be used as a file-system.
# Author: Kinan Cheung

# Creates the metadata for root and set bitmap to take up block 0
def high_level_format():
    helper.write_meta_data(0, (S_IFDIR | 0o755), '/', 2, 1)
    helper.update_bit_map(0)

if __name__ =='__main__':
    high_level_format()
