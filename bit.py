# This file contains bit manipulation helper functions
# Author: Kinan Cheung

# Checks whether bit is 0 or 1 (empty or full)
def checkBit(int_type, offset):
    mask = 1 << offset
    return (int_type & mask)

# Sets the selected bit to 1
def setBit(int_type, offset):
    mask = 1 << offset
    return (int_type | mask)

# Sets the selected bit to 0
def clearBit(int_type, offset):
    mask = ~(1 << offset)
    return (int_type & mask)

# Inverts the selected bit values from 1->0 or 0->1
def toggleBit(int_type, offset):
    mask = 1 << offset
    return (int_type ^ mask)