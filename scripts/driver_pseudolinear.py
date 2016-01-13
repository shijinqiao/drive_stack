#!/usr/bin/env python
"""
Pseudo Linear Driver
Example implementation of the driver

process_position is the key method here
"""

import driver
import rospy

import math
import sys
# from driver import heading_to_quaternion, quaternion_to_heading
# from driver import dot_product, cross_product, scale, unit
# import rospy
from geometry_msgs.msg import Twist

class PseudoLinearDriver(driver.Driver):
    """
    See module docstring
    """

    # pylint: disable=no-self-use
    # incorrectly identifies helpers as no-self-use

    def __init__(self):
        super(PseudoLinearDriver, self).__init__()
        self.last_odom = None

    def process_position(self, odom):
        """
        Uses a somewhat linear correction based on the error from the desired
        position
        """
        # rospy.loginfo('process_position')
        # rospy.loginfo('odom'+str(odom))
        ## TODO check:
        odom.header.frame_id = 'map'
        self.last_pose_data.publish(odom)

        if self.last_odom is None:
            self.last_odom = odom

        next_goal = self.lead_goal().goal

        # rospy.loginfo('goal'+str(next_goal))

        while self.advance_next_goal(odom, next_goal):
            # if you are .04 m or less from the goal, move forward
            # NOTE: this might change.
            # for example, you may want to look at the next_goal two points
            #  ahead and see if you want to skip the current one, or if you are
            #  ahead of the current one in the direction that you want to go
            next_goal = self.lead_next().goal

        # errors along axis "x", off axis "y", heading "theta"
        along, off, heading = self.calc_errors(odom, next_goal)
        # rospy.loginfo('aoh'+ str( (along, off, heading)) )
        
        # 63.6567 is an arbitrary value to make the heading correction 99% of
        #  90 degrees at 1 meter of offset
        heading_from_off = math.atan(63.6567*off)

        adjusted_heading = heading + heading_from_off
        while adjusted_heading > math.pi*2:
            adjusted_heading = adjusted_heading - math.pi*2
        while adjusted_heading < math.pi*-2:
            adjusted_heading = adjusted_heading + math.pi*2
        if adjusted_heading > math.pi:
            adjusted_heading = math.pi*-2 + adjusted_heading
        if adjusted_heading < -math.pi:
            adjusted_heading = math.pi*2 + adjusted_heading

        # rospy.loginfo('adjusted_heading: '+str(adjusted_heading))

        if abs(adjusted_heading) > .5: # approx 30 degrees
            twist_out = Twist()
            twist_out.linear.x = 0
            if adjusted_heading < 0:
                rospy.loginfo('extreme negative heading err')
                twist_out.angular.z = -0.25
            else:
                rospy.loginfo('extreme positive heading err')
                twist_out.angular.z = 0.25
            self.cmd_vel.publish(twist_out)
            return None

        # 2.7468 is an arbitrary value so that the atan value results in a 
        #  .5 at heading = +-.5
        angular_vel = math.atan(10*adjusted_heading)/2.7468

        # 2.7468 is an arbitrary value so that the atan value results in a 
        #  .5 at along error of = +-.5
        net_distance = math.sqrt(along*along+off*off)+next_goal.twist.twist.linear.x
        linear_vel = math.atan(10*net_distance)/2.7468

        # the closer that angular vel gets to .25, the slower the robot moves
        #  forward or backwards. Based on the way that the angular velocity is
        #  calculated, the further away the robot is, the more it will correct
        #  toward where it is supposed to be instead of moving forwards.
        linear_vel = linear_vel*((0.5-abs(angular_vel))/0.5)

        # linear and angular velocity are now within dx/dt, d2x/dt2 limits
        twist_out = Twist()
        twist_out.linear.x = linear_vel
        twist_out.angular.z = angular_vel
        # rospy.loginfo('lin: '+str(linear_vel)+' ang: '+str(angular_vel))

        if math.isnan(linear_vel) or math.isnan(angular_vel):
            linear_vel = 0
            angular_vel = 0
            twist_out.linear.x = linear_vel
            twist_out.angular.z = angular_vel
            self.cmd_vel.publish(twist_out)
            rospy.loginfo('Error in driver calculation')
            sys.exit(0)

        rospy.loginfo('normal state. '+str(adjusted_heading>0)+' '+str(angular_vel>0))
        rospy.loginfo('head: %4f off: %4f adj: %4f' % (heading, off, adjusted_heading,))

        self.cmd_vel.publish(twist_out)


    def check_linear_limits(self, odom, linear_vel):
        """
        Make sure the given linear velocity fits within accel/speed limits
        """
        # limit maximum acceleration
        if odom.twist.twist.linear.x + self.max_accel < linear_vel:
            linear_vel = odom.twist.twist.linear.x + self.max_accel
        elif linear_vel < odom.twist.twist.linear.x - self.max_accel:
            linear_vel = odom.twist.twist.linear.x - self.max_accel

        # limit maximum speed
        if linear_vel > self.max_v:
            linear_vel = self.max_v
        elif linear_vel < -1.0*self.max_v:
            linear_vel = -1.0*self.max_v

        return linear_vel

    def check_angular_limits(self, odom, angular_vel):
        """
        Make sure the given angular velocity fits within accel/speed limits
        """
        # limit maximum angular acceleration
        if odom.twist.twist.angular.z + self.max_alpha < angular_vel:
            angular_vel = odom.twist.twist.angular.z + self.max_alpha
        elif angular_vel < odom.twist.twist.angular.z - self.max_alpha:
            angular_vel = odom.twist.twist.angular.z - self.max_alpha

        # limit maximum angular speed
        if angular_vel > self.max_omega:
            angular_vel = self.max_omega
        elif angular_vel < -1.0*self.max_omega:
            angular_vel = -1.0*self.max_omega

        return angular_vel

    def advance_next_goal(self, odom, current):
        along, off, heading = self.calc_errors(odom, current)
        return along <= 0.0

if __name__ == '__main__':
    # pylint: disable=invalid-name
    # ignoring the trivial naming of the PseudoLinearDriver class for startup and run
    d = PseudoLinearDriver()
    d.run_node()