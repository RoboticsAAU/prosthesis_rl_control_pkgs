from hand_prosthesis_rl_env import robot_gazebo_env
import numpy
import rospy
from std_msgs.msg import Float64
from sensor_msgs.msg import JointState
from sensor_msgs.msg import PointCloud2
from mia_hand_msgs.msg import FingersData
from mia_hand_msgs.msg import FingersStrainGauges

class MiaHandEnv(robot_gazebo_env.RobotGazeboEnv):
    """Superclass for all Robot environments.
    """

    def __init__(self):
        """Initializes a new Robot environment.
        """
        # Variables that we give through the constructor.
        rospy.loginfo("Start MiaHanEnv INIT...")
        
        # Internal Vars
        self.controllers_list = []

        self.robot_name_space = ""
        
        # We launch the init function of the Parent Class robot_gazebo_env.RobotGazeboEnv
        
        super(MiaHandEnv, self).__init__(controllers_list=self.controllers_list,
                                                robot_name_space=self.robot_name_space,
                                                reset_controls=False,
                                                start_init_physics_parameters=False,
                                                reset_world_or_sim="WORLD")

        self.gazebo.unpauseSim()
    
        self._check_all_sensors_ready()
        
        # We Start all the ROS related Subscribers and publishers
        rospy.Subscriber("/mia_hand_sim/joint_states", JointState, self._joints_callback)
        rospy.Subscriber("/camera/depth/points", PointCloud2, self._camera_depth_points_callback)
        
        self._thumb_vel_pub = rospy.Publisher('/mia_hand_sim/j_index_fle_velocity_controller/command', Float64, queue_size=1)
        self._mrl_vel_pub = rospy.Publisher('/mia_hand_sim/j_mrl_fle_velocity_controller/command', Float64, queue_size=1)
        self._index_vel_pub = rospy.Publisher('/mia_hand_sim/j_thumb_fle_velocity_controller/command', Float64, queue_size=1)
        
        self._check_publishers_connection()

        self.gazebo.pauseSim()
        
        rospy.loginfo("Finished MiaHanEnv INIT...")


    # Methods needed by the RobotGazeboEnv
    # ----------------------------    

    def _check_all_systems_ready(self):
        """
        Checks that all the sensors, publishers and other simulation systems are
        operational.
        """
        self._check_all_sensors_ready()
        return True
    
    def _check_all_sensors_ready(self):
        rospy.logdebug("START ALL SENSORS READY")
        
        self.hand_joints_data = None
        while self.hand_joints_data is None and not rospy.is_shutdown():
            try:
                self.disk_joints_data = rospy.wait_for_message("/mia_hand_sim/joint_states", JointState, timeout=1.0)
                rospy.loginfo("Current mia_hand_sim/joint_states READY=>" + str(self.hand_joints_data))

            except:
                rospy.logerr("Current mia_hand_sim/joint_states not ready yet, retrying for getting joint_states")
        
        self.camera_pc_data = None
        while self.camera_pc_data is None and not rospy.is_shutdown():
            try:
                self.camera_pc_data = rospy.wait_for_message("/camera/depth/points", PointCloud2, timeout=1.0)
                rospy.loginfo("Current camera/depth/points READY=>" + str(self.camera_pc_data))

            except:
                rospy.logerr("Current camera/depth/points not ready yet, retrying for getting joint_states")

        rospy.loginfo("ALL SENSORS READY")
    
    def _check_publishers_connection(self):
        """
        Checks that all the publishers are working
        :return:
        """
        rate = rospy.Rate(10)  # 10hz
        while self._thumb_vel_pub.get_num_connections() == 0 and not rospy.is_shutdown():
            rospy.logdebug("No susbribers to _thumb_vel_pub yet so we wait and try again")
            try:
                rate.sleep()
            except rospy.ROSInterruptException:
                # This is to avoid error when world is rested, time when backwards.
                pass
        rospy.logdebug("_thumb_vel_pub Publisher Connected")
        while self._mrl_vel_pub.get_num_connections() == 0 and not rospy.is_shutdown():
            rospy.logdebug("No susbribers to _mrl_vel_pub yet so we wait and try again")
            try:
                rate.sleep()
            except rospy.ROSInterruptException:
                # This is to avoid error when world is rested, time when backwards.
                pass
        rospy.logdebug("_mrl_vel_pub Publisher Connected")
        while self._index_vel_pub.get_num_connections() == 0 and not rospy.is_shutdown():
            rospy.logdebug("No susbribers to _index_vel_pub yet so we wait and try again")
            try:
                rate.sleep()
            except rospy.ROSInterruptException:
                # This is to avoid error when world is rested, time when backwards.
                pass
        rospy.logdebug("_index_vel_pub Publisher Connected")

        rospy.logdebug("All Publishers READY")
    
    def _joints_callback(self, data):
        self.joints = data
        
    def _camera_depth_points_callback(self, data):
        self.camera_depth_points = data
    
    # Methods that the TrainingEnvironment will need to define here as virtual
    # because they will be used in RobotGazeboEnv GrandParentClass and defined in the
    # TrainingEnvironment.
    # ----------------------------
    def _set_init_pose(self):
        """Sets the Robot in its init pose
        """
        raise NotImplementedError()
    
    
    def _init_env_variables(self):
        """Inits variables needed to be initialised each time we reset at the start
        of an episode.
        """
        raise NotImplementedError()

    def _compute_reward(self, observations, done):
        """Calculates the reward to give based on the observations given.
        """
        raise NotImplementedError()

    def _set_action(self, action):
        """Applies the given action to the simulation.
        """
        raise NotImplementedError()

    def _get_obs(self):
        raise NotImplementedError()

    def _is_done(self, observations):
        """Checks if episode done based on observations given.
        """
        raise NotImplementedError()
        
    # Methods that the TrainingEnvironment will need.
    # ----------------------------
    
    