import open3d as o3d
import numpy as np
from typing import List, Optional, Dict
import rospkg
import glob
from time import time
from pathlib import Path
from utilities.urdf_handler import URDFHandler

class PointCloudHandler():
    def __init__(self, point_clouds : List[o3d.geometry.PointCloud] = None, transforms : List[np.ndarray] = None):
        self._pc = point_clouds if point_clouds is not None else []
        self._transforms = transforms if transforms is not None else []
    
    # OBS: When calling functions with this decorator with non-default index, remember to do explicit assignment of index (i.e. index = n), otherwise it won't be listed in kwargs    
    def _check_multiple_run(func):
        """
        Decorator to run a function on all point clouds if no index is given.
        """
        def wrapper(self, *args, **kwargs):
            combined = kwargs.get('combined', False)
            if not combined and kwargs.get('index') is None:
                tmp_kwargs = kwargs.copy()
                for index in range(self.count):
                    tmp_kwargs['index'] = index
                    func(self, *args, **tmp_kwargs)
            else:
                func(self, *args, **kwargs)
        
        return wrapper
    
    
    @_check_multiple_run
    def visualize(self, combined : bool = False, index : Optional[int] = None):
        """
        Visualize its own point cloud.
        :param point_cloud: Open3D PointCloud object
        :param index: The index of the point cloud
        """
        if self.count == 0:
            raise ValueError("The point cloud is not set.")
        
        pc = self._pc[index] if not combined else self.get_combined()
        
        # Create a mesh representing the global coordinate frame axes
        axis_mesh = o3d.geometry.TriangleMesh.create_coordinate_frame(size=0.02)
        
        vis = o3d.visualization.Visualizer()
        vis.create_window()
        vis.add_geometry(pc)
        vis.add_geometry(axis_mesh)
        vis.run()
        vis.destroy_window()
    
    @_check_multiple_run
    def remove_plane(self, index : Optional[int] = None):
        """
        It will remove the plane from the point cloud.
        :param index: The index of the point cloud
        """
        # Isolate the plane in the point cloud
        (plane_coeffs, plane_indices) = self._pc[index].segment_plane(distance_threshold=2, ransac_n=3, num_iterations=1000)
        
        # Remove the plane from the point cloud
        self._pc[index] = self._pc[index].select_by_index(plane_indices, invert=True)
    
    @_check_multiple_run
    def update_cardinality(self, num_points : int, voxel_size : float = 0.005, index : Optional[int] = None):
        """
        It will update the cardinality of the point cloud.
        :param num_points: The number of points in output pc
        :param voxel_size: The voxel size used during sampling 
        :param index: The index of the point cloud
        """
        self._pc[index] = self._pc[index].voxel_down_sample(voxel_size)
        self._pc[index] = self._pc[index].random_down_sample(num_points/len(self._pc[index].points))
    
    @_check_multiple_run
    def add(self, point_cloud : o3d.geometry.PointCloud, index : int = None):
        """
        It will add the point cloud with the current point cloud.
        :param point_cloud: The point cloud to add
        :param index: The index of the point cloud
        """
        self._pc[index] += point_cloud
    
    @_check_multiple_run
    def clear(self, index : Optional[int] = None):
        """
        It will clear the point cloud.
        :param index: The index of the point cloud
        """
        self._pc[index].clear()
    
    def get_combined(self, index_list : Optional[List[int]] = None):
        """
        It will combine all the point clouds.
        :param index_list: The list of indices to combine
        :return: The combined point cloud
        """
        pc = o3d.geometry.PointCloud()
        for index in (index_list if index_list is not None else range(self.count)):
            pc += self._pc[index]
        
        return pc
    
    @staticmethod
    def sample_from_mesh(mesh_file : str, sample_points : int = 1000, transformation : np.ndarray = None):
        """
        It will sample the mesh file (either .stl or .obj).
        :param stl_file: The path to the stl file
        :param sample_points: The number of points to sample
        :return: The point cloud
        """
        # Read the stl file
        mesh = o3d.io.read_triangle_mesh(mesh_file)
        
        # Sample the stl file
        pc =  mesh.sample_points_uniformly(number_of_points=sample_points)
        
        # Apply transformation if it is provided
        if transformation is not None:
            pc.transform(transformation)
        
        return pc

    @staticmethod
    def scale(pc : o3d.geometry.PointCloud, scale_factors : np.array):
        """
        It will scale the point cloud by the scale factors.
        :param scale_factor: The scale factors in each direction
        :param transform: The coordinate frame to scale the point cloud about
        :return: The scaled point cloud
        """
        scaled_pc = o3d.geometry.PointCloud(pc)
        
        scaling_matrix = np.diag(np.append(scale_factors, 1))
        scaled_pc.transform(scaling_matrix)
        
        return scaled_pc
        
    @staticmethod
    def transform(pc : o3d.geometry.PointCloud, transform : np.ndarray):
        """
        It will transform the point cloud.
        :param pc: The point cloud
        :return: The transformed point cloud
        """
        transformed_pc = o3d.geometry.PointCloud(pc)
        
        transformed_pc.transform(transform)
        
        return transformed_pc
        
        
    @property
    def pc(self):
        return self._pc
    
    @property
    def transforms(self):
        return self._transforms
    
    @property
    def points(self):
        return np.asarray(self.pc.points)

    @property
    def count(self):
        return len(self._pc)


class ImaginedPointCloudHandler(PointCloudHandler):
    def __init__(self):
        super().__init__()
        self._pc.append(o3d.geometry.PointCloud()) # The point cloud for the entire hand untransformed
        self._transforms.append(np.eye(4)) # The transform for the entire hand untransformed
        self._initial_transforms = self._transforms.copy()

    def visualize(self, index : int = 0):
        if index == 0:
            self.update_hand()
        return super().visualize(index=index)

    def sample_from_meshes(self, mesh_dict : dict, total_sample_points : int = 1000):
        """
        It will sample the mesh files (either .stl or .obj) given by the dict.
        :param mesh_dict: Dictionary containing the mesh files, scale factors, origins, and group indices
        :param total_sample_points: The total number of points to sample
        """
        sample_points = total_sample_points // len(mesh_dict)
        
        # Initialise the point clouds
        initial_count = self.count
        num_pc = max(mesh_dict.values(), key=lambda x: x["group_index"])["group_index"] + 1
        self._pc.extend([o3d.geometry.PointCloud() for _ in range(num_pc)])
        self._transforms.extend([None for _ in range(num_pc)])
        
        # Go through each mesh file in the dictionary
        for mesh_values in mesh_dict.values():
            point_cloud = self.sample_from_mesh(mesh_values["path"], sample_points)
            
            # Apply the scale factors and origin
            if mesh_values["scale_factors"] is not None:
                point_cloud = self.scale(point_cloud, mesh_values["scale_factors"])
            if mesh_values["visual_origin"] is not None:
                point_cloud = self.transform(point_cloud, mesh_values["visual_origin"])
            
            # Set the new point cloud
            index = initial_count + mesh_values["group_index"]
            self.add(point_cloud, index=index)
            
            # Set the transform of the group
            if self._transforms[index] is None:
                self._transforms[index] = mesh_values["link_origin"] if mesh_values["link_origin"] is not None else np.eye(4)
                self._initial_transforms[index] = self._transforms[index].copy()
    
    def update_hand(self, num_points : Optional[int] = None):
        """
        It will update the base point cloud of the entire hand.
        """
        self._pc[0].clear()
        for index in range(1, self.count):
            pc = self.transform(self._pc[index], self._transforms[index])
            self.add(pc, index=0)

        self._pc[0] = self.transform(self._pc[0], self._transforms[0])
        
        if num_points is not None:        
            self.update_cardinality(num_points, index=0)
    
    @property
    def initial_transforms(self):
        return self._initial_transforms.copy()


if __name__ == "__main__":
    # Create the point cloud handler
    point_cloud_handler = ImaginedPointCloudHandler()
    urdf_handler = URDFHandler()
    
    # Get an instance of RosPack with the default search paths
    rospack = rospkg.RosPack()

    # Get the stl files from the mia description package
    ignore_files = ["1.001.stl", "UR_flange.stl"]
    stl_folder = rospack.get_path('mia_hand_description') + "/meshes/stl"
    stl_files = [file for file in glob.glob(stl_folder + "/*") if (Path(file).name not in ignore_files)]
    
    # Extract stl files for left and right hand respectively
    stl_files_left, stl_files_right = [], []
    for x in stl_files:
        (stl_files_right, stl_files_left)["mirrored" in x].append(x)
    
    # Define the groups
    free_joints = urdf_handler.get_free_joints()
    groups = {free_joint : urdf_handler.get_free_joint_group(free_joint) for free_joint in free_joints}
    groups["j_palm"] = urdf_handler.get_link_group("palm")
    
    # Create a dictionary for the stl files
    mesh_dict = {}  # Initialize an empty dictionary
    for stl_file in stl_files_right:
        # Get the visual origin and scale
        visual_origin, scale = urdf_handler.get_visual_origin_and_scale(Path(stl_file).stem)
        
        # Get the link name and origin
        link_name = urdf_handler.get_link_name(Path(stl_file).stem)
        link_origin = urdf_handler.get_link_transform("palm", link_name)
        
        # Get the group index of the link
        group_index = None
        for group_name, links in groups.items():
            if not any(link in link_name for link in links):
                continue
            group_index = list(groups.keys()).index(group_name)
            group = groups[group_name]
            break
        
        # Fix the transformation to have origin at the group parent link
        group_parent = group[0]
        while link_name != group_parent:
            index = group.index(link_name)
            
            visual_origin = urdf_handler.get_link_transform(group[index - 1], link_name) @ visual_origin
            link_origin = link_origin @ np.linalg.inv(urdf_handler.get_link_transform(group[index - 1], link_name))
            
            link_name = group[index - 1]
        
        # Create a dictionary for each mesh file
        mesh_dict[Path(stl_file).stem] = {
            'path': stl_file,  # Construct the path for the file
            'scale_factors': scale,  # Assign scale factors
            'visual_origin': visual_origin,  # Assign origin
            'link_origin' : link_origin,
            'group_index' : group_index
        }

    start_time = time()
    # Load the stl file
    point_cloud_handler.sample_from_meshes(mesh_dict, 10000)
    #pc_plane = PointCloudHandler.sample_from_mesh("./plane.stl", 1000)
    #point_cloud_handler.add(pc_plane)
    
    duration = time() - start_time
    print(f"Duration: {duration:.5f} seconds")
    
    transform = np.array([[0.707, -0.707, 0, 0],
                        [0.707, 0.707, 0, 0],
                        [0, 0, 1, 0],
                        [0, 0, 0, 1]])
    point_cloud_handler._transforms[3] = point_cloud_handler._transforms[3] @ transform
    #point_cloud_handler._pc[2] = point_cloud_handler._pc[2].transform(transform)
    start_time = time()
    #point_cloud_handler.update_cardinality(250)
    duration = time() - start_time
    print(f"Duration: {duration:.5f} seconds")
    
    # Visualize the point cloud
    point_cloud_handler.visualize(index=0)

    #point_cloud_handler.transform(point_cloud_handler.pc[2], transform)
    #for i in range(point_cloud_handler.count):
    #    point_cloud_handler.transform(point_cloud_handler.pc[i], transform)
    #point_cloud_handler.visualize()
    
    #point_cloud_handler.remove_plane()
    #point_cloud_handler.visualize()