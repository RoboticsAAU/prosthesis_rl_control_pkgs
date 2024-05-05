import rospy
import rospkg
import numpy as np
import yaml
import torch.nn as nn
from stable_baselines3.ppo import PPO
from stable_baselines3.common.torch_layers import PointNetImaginationExtractorGP
from stable_baselines3.common.vec_env.subproc_vec_env import SubprocVecEnv
from datetime import datetime

from rl_env.task_envs.mia_hand_task_env import MiaHandWorldEnv
from rl_env.setup.hand.mia_hand_setup import MiaHandSetup
from sim_world.world_interfaces.simulation_interface import SimulationInterface
from sim_world.rl_interface.rl_interface import RLInterface


# Load the configuration files
rospack = rospkg.RosPack()
package_path = rospack.get_path("rl_env")
with open(package_path + "/params/rl_params.yaml", 'r') as file:
    rl_config = yaml.safe_load(file)

with open(package_path + "/params/sim_params.yaml", 'r') as file:
    sim_config = yaml.safe_load(file)

with open(package_path + "/params/hand/mia_hand_params.yaml", 'r') as file:
    hand_config = yaml.safe_load(file)

with open(rospack.get_path("sim_world") + "/config/joint_limits.yaml", 'r') as file:
    joint_limits = yaml.safe_load(file)

# Current date as a string in the format "ddmmyyyy"
algorithm_name = "PPO"
env_name= "mia_hand_rl"
date_string = datetime.now().strftime("%d%m%Y")
log_name = f"{env_name}_{algorithm_name}_{date_string}" 


def get_3d_policy_kwargs(extractor_name):
    feature_extractor_class = PointNetImaginationExtractorGP
    feature_extractor_kwargs = {"pc_key": "camera-point_cloud",
                                "extractor_name": extractor_name,
                                "imagination_keys": "imagined",
                                "state_key": "state"}

    policy_kwargs = {
        "features_extractor_class": feature_extractor_class,
        "features_extractor_kwargs": feature_extractor_kwargs,
        "net_arch": [dict(pi=[64, 64], vf=[64, 64])],
        "activation_fn": nn.ReLU,
    }
    return policy_kwargs


def main():
    
    # Instantiate the RL interface to the simulation
    rl_interface = RLInterface(
        SimulationInterface(
            MiaHandSetup(hand_config, joint_limits),
        ),
        sim_config
    )
    
    # Instantiate RL env
    rl_env = MiaHandWorldEnv(rl_interface, rl_config)

    # Instantiate the PPO model
    model = PPO(
        policy = "MultiInputPolicy",
        env = SubprocVecEnv([rl_env]),
        verbose = 1,
        batch_size = 64,
        policy_kwargs = get_3d_policy_kwargs(extractor_name="smallpn"), # Can either be "smallpn", "mediumpn" or "largepn". See sb3.common.torch_layers.py 
        tensorboard_log = rospack.get_path("rl_env") + "/logs",
        device = 'cuda:0'
    )
    
    # Train the model
    model.learn(total_timesteps=100000, tb_log_name=log_name)
        

if __name__ == "__main__":
    rospy.init_node("rl_env", log_level=rospy.INFO)
    np.random.seed(sim_config["seed"])
    
    try:
        main()
    except rospy.ROSInterruptException:
        pass