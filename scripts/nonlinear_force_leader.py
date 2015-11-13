#!/usr/bin/env python

import leader
import rospy
import math
from nav_msgs.msg import Odometry

from utils import heading_to_quaternion, quaternion_to_heading
from utils import calc_errors, dist, scale, minimize_angle
from utils import unit as to_unit_tuple

def unit(function):
    def modded_function(*args, **varargs):
        val = function(*args, **varargs)
        return to_unit_tuple(val)
    return modded_function

# pylint: disable=no-self-use
# the class functions are used. I'm not sure why it's missing this.

class ForceLeader(leader.Leader):
    # methods to override:
    # generate_initial_path, generate_next_path

    def generate_initial_path(self):
        """
        Path creation for node
        """
        self.generate_next_path(rvs=False)

    def generate_next_path(self, rvs=False):
        """
        generate a new path, either forwards or backwards (rvs == True)
        """
        if not rvs:
            end = self.path_next().goal
            start = self.path_start().goal
        else:
            # move back one segment
            start = self.path_back().goal
            end = start.path_goal().goal

        self.targets = []
        self.targets.append(start)

        # pylint: disable=invalid-name
        # dt, v, w, are accurately describing what I want in this case

        dt = .1

        start.header.frame_id = 'odom'

        current = StateModel(start)
        force_vector = self.get_force_vector(start, end, start)
        force_heading = math.atan2(force_vector[1], force_vector[0])
        heading_err = current.theta - force_heading
        w = heading_err/dt
        v = 0.75 # TODO(buckbaskin): calculate something smart based on vel
        # profile from start to end
        # possibly do vel profile based on distance, slow down proportional to
        #  heading error relative to force field

        rospy.loginfo('gnxt: '+str(force_heading)+' ... '+str(current.theta))

        next_ = current.sample_motion_model(v, w, dt)
        self.targets.append(next_)

        errors = calc_errors(next_, end)
        along = errors[0]

        count = 1

        while along < 0:
            if count > 0:
                break
            current = StateModel(next_)
            force_vector = self.get_force_vector(start, end, next_)
            force_heading = math.atan2(force_vector[1], force_vector[0])
            heading_err = minimize_angle(current.theta - force_heading)

            # pylint: disable=invalid-name
            # v, w, are accurately describing what I want in this case
            w = heading_err/dt
            v = 0.75

            count += 1
            next_ = current.sample_motion_model(v, w, dt)
            self.targets.append(next_)

            

            errors = calc_errors(next_, end)
            along = errors[0]

        self.index = 0



    @unit # forces a unit vector to be returned, scaled by weight
    def get_force_vector(self, start, end, current):
        """
        Aggregate the sum of the force vectors for 3 different actors: departing
        the original location, arriving at the destination and traversing
        between the two points.

        There may be more added, and the end output is
        only relevant for its direction, so the weighting is arbitrary and
        relative, where I've fixed the traverse weight to always be 1.

        This is a superposition of 3? differential equations representing a sum
        of forces.
        """
        wdep = self.weighted_depart(start, end, current)
        warr = self.weighted_arrive(start, end, current)
        wtrv = self.weighted_traverse(start, end, current)
        # wobs = self.weighted_obstacle(start, end, current)

        force = (wdep[0]+warr[0]+wtrv[0], wdep[1]+warr[1]+wtrv[1], 0,)

        return force

    def weighted_depart(self, start, end, current):
        depart_vector = self.depart_vector(start, end, current)
        rospy.loginfo('wdp: '+str(depart_vector[0])+' , '+str(depart_vector[1]))
        w = self.depart_weight(start, end, current)
        return scale(depart_vector, w)

    # pylint: disable=unused-argument
    # it is being left in to maintain method signature consistency
    @unit # forces a unit vector to be returned, scaled by weight
    def depart_vector(self, start, unused_end, current):
        # axis direction
        axis_direction = quaternion_to_heading(start.pose.pose.orientation)

        # correction to move away from axis
        errors = calc_errors(current, start)
        off_axis = errors[1]
        heading_correction = math.atan(2.0*off_axis)

        final_direction = axis_direction+heading_correction

        return (math.cos(final_direction), math.sin(final_direction), 0,)

    # pylint: disable=unused-argument
    # it is being left in to maintain method signature consistency
    def depart_weight(self, start, unused_end, current):
        d = dist(start, current)
        if d < .3:
            return 1/.3
        return 1.0/d

    def weighted_arrive(self, start, end, current):
        arrive_vector = self.arrive_vector(start, end, current)
        rospy.loginfo('war: '+str(arrive_vector[0])+' , '+str(arrive_vector[1]))
        w = self.arrive_weight(start, end, current)
        return scale(arrive_vector, w)

    # pylint: disable=unused-argument
    # it is being left in to maintain method signature consistency
    @unit # forces a unit vector to be returned, scaled by weight
    def arrive_vector(self, unused_start, end, current):
        # axis direction
        axis_direction = quaternion_to_heading(end.pose.pose.orientation)

        # correction to move away from axis
        errors = calc_errors(current, end)
        off_axis = errors[1]
        heading_correction = math.atan(-2.0*off_axis)

        final_direction = axis_direction+heading_correction

        rospy.loginfo('avr: '+str(axis_direction)+' '+str(heading_correction))

        return (math.cos(final_direction), math.sin(final_direction), 0,)

    # pylint: disable=unused-argument
    # it is being left in to maintain method signature consistency
    def arrive_weight(self, unused_start, end, current):
        d = dist(current, end)
        if d < .3:
            return 1/.3
        return 1.0/d

    def weighted_traverse(self, start, end, current):
        traverse_vector = self.traverse_vector(start, end, current)
        rospy.loginfo('wtr: '+str(traverse_vector[0])+' , '+str(traverse_vector[1]))
        w = self.traverse_weight(start, end, current)
        return scale(traverse_vector, w)

    # pylint: disable=unused-argument
    # it is being left in to maintain method signature consistency
    @unit # forces a unit vector to be returned, scaled by weight
    def traverse_vector(self, start, end, unused_current):
        dx = end.pose.pose.position.x - start.pose.pose.position.x
        dy = end.pose.pose.position.y - start.pose.pose.position.y
        return (dx, dy, 0,)

    # pylint: disable=unused-argument
    # it is being left in to maintain method signature consistency
    def traverse_weight(self, unused_start, unused_end, unused_current):
        # This is the standard unit. All other forces can use a weight of 1 to
        #  be of equal weight to the traverse weight. More indicates a greater
        #  requested priority.
        return 1.0

class StateModel(object):
    def __init__(self, odom):
        self.x = odom.pose.pose.position.x
        self.y = odom.pose.pose.position.y
        self.theta = quaternion_to_heading(odom.pose.pose.orientation)
        self.v = odom.twist.twist.linear.x
        self.w = odom.twist.twist.angular.z
        self.a = 0
        self.alpha = 0
        self.frame_id = odom.header.frame_id

    def sample_motion_model(self, v, w, dt):
        '''
        Return an odometry message sampled from the distribution defined by the
        probabilistic motion model based on this statemodel
        Does not yet take full advantage of state stored in above
        And does not check acceleration bounds for example
        '''
        # TODO(buckbaskin): use the v,w data stored above to add accel limits
        # TODO(buckbaskin): use the v,w data to create more accurate v_hat

        noise = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0) # no noise for now, ideal motion
        v_hat = v + self.sample_normal(noise[0]*v+noise[1]*w)
        w_hat = w + self.sample_normal(noise[2]*v+noise[3]*w)
        y_hat = self.sample_normal(noise[4]*v+noise[5]*w)

        if w_hat < .001:
            pass

        rospy.loginfo('smm: '+str(v)+' , '+str(w)+' , '+str(dt))
        x_new = (self.x - v_hat/w_hat*math.sin(self.theta)
            + v_hat/w_hat*math.sin(self.theta+w_hat*dt))
        rospy.loginfo('smm: dx '+str(x_new-self.x))
        y_new = (self.y - v_hat/w_hat*math.cos(self.theta)
            - v_hat/w_hat*math.cos(self.theta+w_hat*dt))
        rospy.loginfo('smm: dy '+str(y_new-self.y))

        theta_new = self.theta + w_hat*dt + y_hat*dt

        new_odom = Odometry()
        new_odom.pose.pose.position.x = x_new
        new_odom.pose.pose.position.y = y_new
        new_odom.pose.pose.orientation = heading_to_quaternion(theta_new)
        new_odom.twist.twist.linear.x = v_hat
        new_odom.twist.twist.angular.z = w_hat
        new_odom.header.frame_id = self.frame_id

        return new_odom

    # pylint: disable=unused-argument
    # it will be used when implmenented properly
    def sample_normal(self, unused_b):
        # TODO(buckbaskin): change to sample normal distribution
        # norm(mean=0, stdev = b)
        return 0



if __name__ == '__main__':
    # pylint: disable=invalid-name
    # leader is a fine name, it's not a constant
    leader = ForceLeader()
    leader.run_server()