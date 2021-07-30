from time import time
import disktools
import os
import bit
import math

# This file contains helper functions
# Author: Kinan Cheung

NUM_BLOCKS = 16
META_DATA_LENGTH = 38
DATA = 63
ALL_DATA = 64

def write_meta_data(block_location, mode, path, n_links, data_location):
    block = disktools.read_block(block_location)
    current_time = int(time())
    # Byte 0 of a block holds the LOCATION of the data
    block[0:1] = disktools.int_to_bytes(data_location, 1)

    # Bytes 1-2 of a block holds the metadata for MODE
    block[1:3] = disktools.int_to_bytes(mode, 2)

    # Bytes 3-4 of a block holds the metadata for UID
    block[3:5] = disktools.int_to_bytes(os.getuid(), 2)

    # Bytes 5-6 of a block holds the metadata for GID
    block[5:7] = disktools.int_to_bytes(os.getgid(), 2)

    # Byte 7 of a block holds the metadata for NLINKS
    block[7:8] = disktools.int_to_bytes(n_links, 1)

    # Bytes 8-9 of a block holds the SIZE of the file in bytes
    block[8:10] = disktools.int_to_bytes(0, 2)

    # Bytes 10-13 if a block holds the metadata for CTIME
    block[10:14] = disktools.int_to_bytes(current_time, 4)

    # Bytes 14-17 of a block holds the metadata for MTIME
    block[14:18] = disktools.int_to_bytes(current_time, 4)

    # Bytes 18-21 of a block holds the metadata for ATIME
    block[18:22] = disktools.int_to_bytes(current_time, 4)

    # Bytes 22-37 of a block holds the NAME of the file
    block[22:38] = path.encode()

    # Bytes 42-43 of a block holds the LENGTH of the NAME
    block[42:44] = disktools.int_to_bytes(len(path), 2)

    disktools.write_block(block_location, block)

# Formatted meta data for getattr to return
def read_meta_data(block_num):
    block = disktools.read_block(block_num)
    dictionary = dict(
        st_mode=disktools.bytes_to_int(block[1:3]),
        st_nlink=disktools.bytes_to_int(block[7:8]),
        st_size=disktools.bytes_to_int(block[8:10]),
        st_ctime=disktools.bytes_to_int(block[10:14]),
        st_mtime=disktools.bytes_to_int(block[14:18]),
        st_atime=disktools.bytes_to_int(block[18:22]),
        
    )
    return dictionary

# Write data to a file
def write_data(new_data, block_int):
    block = disktools.read_block(block_int)
    length = len(new_data)
    block_pointer = disktools.bytes_to_int(block[0:1])
    # Check if data is smaller than 1 block
    if length < ALL_DATA:
        block[1:length+1] = new_data[0:length]
        block[0:1] = bytearray([0])
        disktools.write_block(block_int, block)
        # Release any blocks pointed to if any
        if block_pointer != 0:
            release_blocks(block_pointer)
    # Else write a full block of data
    else:
        counter = 1
        block[1:ALL_DATA] = new_data[0:DATA]
        if block_pointer == 0:
            block_pointer = free_block()
            block[0:1] = disktools.int_to_bytes(block_pointer, 1)
        disktools.write_block(block_int, block)
        length = length - DATA
        # While not all data has been written, check if there is a pre-allocated block to write to
        # and write data to blocks
        while length > 0:
            block = disktools.read_block(block_pointer)
            if length > DATA:
                block[1:ALL_DATA] = new_data[ALL_DATA*counter-counter:ALL_DATA*(counter+1)-counter-1]
                prev_point = block_pointer
                block_pointer = disktools.bytes_to_int(block[0:1])
                counter+=1
                if block_pointer == 0:
                    block_pointer = free_block()
                    block[0:1] = disktools.int_to_bytes(block_pointer, 1)
                disktools.write_block(prev_point, block)
                length = length - DATA
            else:
                block[1:length+1] = new_data[ALL_DATA*counter-counter:ALL_DATA*counter+length-1]
                block[length+1:64] = bytearray([0]*(64-length+1))
                # Release any extra blocks pointed to if any
                if disktools.bytes_to_int(block[0:1]) != 0:
                    block_pointer = disktools.bytes_to_int(block[0:1])
                    release_blocks(block_pointer)
                disktools.write_block(block_pointer, block)
                break
    


# Reads the data from a file if there exists any
def read_data(data_block_int, meta_block_int):
    block = disktools.read_block(data_block_int)
    length = get_size(meta_block_int)
    # Check if data is smaller than one block
    if length < ALL_DATA:
        data = block[1:length+1]
        return data
    # Else keep reading blocks till no more data left
    else:
        data = block[1:length+1]
        length = length - DATA
        while length > 0:
            block_int = disktools.bytes_to_int(block[0:1])
            block = disktools.read_block(block_int)
            if length > DATA:
                data = data + block[1:ALL_DATA]
                length = length - DATA
            else:
                data = data + block[1:length+1]
                break
    return data

# Find a free block
def free_block():
    bit_map_int = get_bit_map()
    new_data_location = None
    for i in range(0, 15):
        if (bit.checkBit(bit_map_int, i)) == 0:
            new_data_location = i
            # Update bit map when a free block is found automatically
            update_bit_map(new_data_location)
            break
    if new_data_location == None:
        # Raise some sort of error here
        raise FuseOSError()
    return new_data_location

# Find meta data block using path
def find_block(path):
    bit_map_int = get_bit_map()
    for i in range(0, 15):
        if bit.checkBit(bit_map_int, i) != 0:
            block = disktools.read_block(i)
            name = get_path(block, path)
            if name == path:
                return i

# Release blocks from linked list
def release_blocks(block_int):
    if block_int != 0:
        block = disktools.read_block(block_int)
        block_point = disktools.bytes_to_int(block[0:1])
        block = bytearray([0] * ALL_DATA)
        disktools.write_block(block_int, block)
        regress_bit_map(block_int)
        while block_point != 0:
            block_int = block_point
            block = disktools.read_block(block_int)
            block_point = disktools.bytes_to_int(block[0:1])
            block = bytearray([0] * ALL_DATA)
            disktools.write_block(block_int, block)
            regress_bit_map(block_int)

# This method reads the current bitmap data and rewrites it when metadata and data
# are written into new blocks
def update_bit_map(block_location):
    bit_map_block = disktools.read_block(0)
    bit_map_int = get_bit_map()
    bit_map_int = bit.setBit(bit_map_int, block_location)
    bit_map_block[META_DATA_LENGTH:META_DATA_LENGTH+2] = disktools.int_to_bytes(bit_map_int, 2)
    disktools.write_block(0, bit_map_block)

# This method removes a block from the bitmap
def regress_bit_map(block_location):
    bit_map_block = disktools.read_block(0)
    bit_map_int = get_bit_map()
    meta_bit_map_int = get_meta_bit_map()
    bit_map_int = bit.clearBit(bit_map_int, block_location)
    meta_bit_map_int = bit.clearBit(meta_bit_map_int, block_location)
    bit_map_block[META_DATA_LENGTH:META_DATA_LENGTH+2] = disktools.int_to_bytes(bit_map_int, 2)
    bit_map_block[META_DATA_LENGTH+2:META_DATA_LENGTH+4] = disktools.int_to_bytes(meta_bit_map_int, 2)
    disktools.write_block(0, bit_map_block)

# Bit map for meta data blocks, used for listing files
def update_meta_bit_map(block_location):
    bit_map_block = disktools.read_block(0)
    bit_map_int = get_meta_bit_map()
    bit_map_int = bit.setBit(bit_map_int, block_location)
    bit_map_block[META_DATA_LENGTH+2:META_DATA_LENGTH+4] = disktools.int_to_bytes(bit_map_int, 2)
    disktools.write_block(0, bit_map_block)

# Update size of a file
def update_size(block_int, size):
    meta_block = disktools.read_block(block_int)
    meta_block[8:10] = disktools.int_to_bytes(size, 2)
    disktools.write_block(block_int, meta_block)

# Update a_time and m_time for utimens
def update_utimens(path, atime, mtime):
    meta_block_int = find_block(path)
    if meta_block_int != None:
        block = disktools.read_block(meta_block_int)
        block[18:22] = disktools.int_to_bytes(int(atime), 4)
        block[14:18] = disktools.int_to_bytes(int(mtime), 4)

# Gets size of file currently
def get_size(meta_int):
    meta_block = disktools.read_block(meta_int)
    return disktools.bytes_to_int(meta_block[8:10])

# Gets the location of the next block that carries on the data if it exists
def get_data_location(meta_block_int):
    meta_block = disktools.read_block(meta_block_int)
    return disktools.bytes_to_int(meta_block[0:1])

# Get bit map
def get_bit_map():
    bit_map_block = disktools.read_block(0)
    return disktools.bytes_to_int(bit_map_block[META_DATA_LENGTH:META_DATA_LENGTH+2])

# Get meta bit map
def get_meta_bit_map():
    bit_map_block = disktools.read_block(0)
    return disktools.bytes_to_int(bit_map_block[META_DATA_LENGTH+2:META_DATA_LENGTH+4])

# Get path of file
def get_path(block, path):
    name = block[22:22+len(path)]
    return name.decode()

# Get length of file name
def get_name_length(block_int):
    block = disktools.read_block(block_int)
    return disktools.bytes_to_int(block[42:44])

# Get name of file using int location
def get_name(block_int):
    meta_block = disktools.read_block(block_int)
    length = get_name_length(block_int)
    name = meta_block[22:22 + length]
    name = name.decode()
    name = name[1:]
    print('%s' % (name))
    return name