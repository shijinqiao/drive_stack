#!/usr/bin/env python

'''
run the following test with:
python driver_mathTest.py
'''

import unittest
import math

import rospy
from geometry_msgs.msg import Quaternion
from nav_msgs.msg import Odometry

from driver_pseudolinear import PseudoLinearDriver as Driver
from utils import heading_to_quaternion, quaternion_to_heading, easy_Odom, is_close

class TestDriverCalculations(unittest.TestCase):

    # sign conventions (revised):
    # axis: x axis is parallel to goal, y axis is to- the left when facing
    #  the goal direction, z-axis is oriented up
    # positive heading error - rotated counter clockwise from goal
    # positve offset error - positive y-axis, 

    def setUp(self):
        self.driver_obj = Driver()

    def test_zero(self):
        heading = 0
        offset = 0
        adjusted_heading = self.driver_obj.adjust_heading(heading, offset)
        self.assertTrue(is_close(adjusted_heading, 0.0))

    def test_pos_heading(self):
        heading = 1.0
        offset = 0
        adjusted_heading = self.driver_obj.adjust_heading(heading, offset)
        self.assertTrue(is_close(adjusted_heading, heading))

    def test_neg_heading(self):
        heading = -1.0
        offset = 0
        adjusted_heading = self.driver_obj.adjust_heading(heading, offset)
        self.assertTrue(is_close(adjusted_heading, heading))

    def test_pure_offset1(self):
        heading = 0
        offset = .5
        adjusted_heading = self.driver_obj.adjust_heading(heading, offset)
        self.assertTrue(adjusted_heading < 0.0)
        self.assertTrue(is_close(adjusted_heading, -.75*math.pi/2, 4))

    def test_pure_offset2(self):
        heading = 0
        offset = -.5
        adjusted_heading = self.driver_obj.adjust_heading(heading, offset)
        self.assertTrue(adjusted_heading > 0.0)
        self.assertTrue(is_close(adjusted_heading, .75*math.pi/2, 4))

if __name__ == '__main__':
    unittest.main()