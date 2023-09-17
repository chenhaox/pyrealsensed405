"""
Interface for Realsense D405. Datasheet: https://dev.intelrealsense.com/docs/intel-realsense-d400-series-product-family-datasheet
Author: Chen Hao (chen960216@gmail.com), 20220719, osaka
Requirement libs: (required) 'pyrealsense2', 'numpy'
                  (optional) 'opencv-python', 'opencv-contrib-python==4.6.0.66'
Note: This program needs to connect to USB3 to work
Update Notes: '0.0.1'/20220719: Implement the functions to capture the point clouds and depth camera
              '0.0.2'/20221110: 1. Implement the functions to stream multiple cameras, 2. remove multiprocessing
"""
import time
from typing import Literal, Tuple, Dict
import multiprocessing as mp

import numpy as np
import pyrealsense2 as rs

try:
    import cv2

    aruco = cv2.aruco
except:
    print("Cv2 aruco does not exist, Accessing the function 'recognize_ar_marker' will raise an error")

__version__ = '0.0.2'

PROCESS_SLEEP_TIME = .1
# Read chapter 4 of datasheet for details
DEPTH_RESOLUTION_MID = (848, 480)
COLOR_RESOLUTION_MID = (848, 480)
DEPTH_RESOLUTION_HIGH = (1280, 720)
COLOR_RESOLUTION_HIGH = (1280, 720)
DEPTH_FPS = 30
COLOR_FPS = 30


def find_devices() -> Tuple[list, rs.context]:
    '''
    Find all connected Intel RealSense Devices
    :return: 1. List of serial numbers of connected devices, and 2. the context
    '''
    ctx = rs.context()  # Create librealsense context for managing devices
    serials = []
    if (len(ctx.devices) > 0):
        for dev in ctx.devices:
            print('Found device: ', dev.get_info(rs.camera_info.name), ' ', dev.get_info(rs.camera_info.serial_number))
            serials.append(dev.get_info(rs.camera_info.serial_number))
    else:
        print("No Intel Device connected")

    return serials, ctx


def stream_data(pipe: rs.pipeline, pc: rs.pointcloud) -> Tuple[np.array, np.array, np.array, np.array]:
    """
    Stream data for RealSense D504
    :param pipe: rs.pipeline
    :param pc: rs.pointcloud
    :return: 1) point cloud, 2) point cloud color, 3) depth image and 4) color image
    """
    # Acquire a frame
    frames = pipe.wait_for_frames()
    depth_frame = frames.get_depth_frame()
    color_frame = frames.get_color_frame()
    # get depth and color image
    depth_image = np.asanyarray(depth_frame.get_data())
    color_image = np.asanyarray(color_frame.get_data())
    # Calculate point clouds and color textures for the point clouds
    points = pc.calculate(depth_frame)
    pc.map_to(color_frame)
    v, t = points.get_vertices(), points.get_texture_coordinates()
    verts = np.asanyarray(v).view(np.float32).reshape(-1, 3)  # xyz
    texcoords = np.asanyarray(t).view(np.float32).reshape(-1, 2)  # uv
    # Calculate normalized colors (rgb nx3) for the point cloud
    cw, ch = color_image.shape[:2][::-1]
    v, u = (texcoords * (cw, ch) + 0.5).astype(np.uint32).T
    np.clip(u, 0, ch - 1, out=u)
    np.clip(v, 0, cw - 1, out=v)
    pc_color = color_image[u, v] / 255
    pc_color[:, [0, 2]] = pc_color[:, [2, 0]]
    return (verts, pc_color, depth_image, color_image)


class _DataPipeline(mp.Process):
    """
    Deprecated. The process to stream data through Realsense API. This process is not used in the current version.
    """

    # TODO
    # Two process cannot share the same rs.context.
    # See https://github.com/IntelRealSense/librealsense/issues/7365 to solve this problem
    def __init__(self, req_q: mp.Queue,
                 res_q: mp.Queue,
                 resolution: Literal['MID', 'HIGH'] = 'HIGH',
                 device: str = None):
        mp.Process.__init__(self)
        # Require queue and receive queue to exchange data
        self._req_q = req_q
        self._res_q = res_q
        self._device = device
        self._color_intr = None
        self._intr_mat = None
        self._intr_distcoeffs = None

    def run(self):
        # RealSense pipeline, encapsulating the actual device and sensors
        print("Multithreading feature will be deprecated in future! The speed of using mutliprocess is musch slower")
        pipeline = rs.pipeline()
        config = rs.config()
        # Setup config
        config.enable_stream(rs.stream.depth, DEPTH_RESOLUTION_HIGH[0], COLOR_RESOLUTION_HIGH[1], rs.format.z16,
                             DEPTH_FPS)
        config.enable_stream(rs.stream.color, COLOR_RESOLUTION_HIGH[0], COLOR_RESOLUTION_HIGH[1], rs.format.bgr8,
                             COLOR_FPS)
        if self._device is not None:
            config.enable_device(self._device)
        # Start streaming with chosen configuration
        pipeline.start(config)

        # Declare pointcloud object, for calculating pointclouds and texture mappings
        pc = rs.pointcloud()

        # Streaming
        while True:
            req_packet = self._req_q.get()
            if req_packet == "stop":
                break
            if req_packet == "intrinsic":
                # get intrinsic matrix of the color image
                color_frame = pipeline.wait_for_frames().get_color_frame()
                _color_intr = color_frame.profile.as_video_stream_profile().intrinsics
                _intr_mat = np.array([[_color_intr.fx, 0, _color_intr.ppx],
                                      [0, _color_intr.fy, _color_intr.ppy],
                                      [0, 0, 1]])
                _intr_distcoeffs = np.asarray(_color_intr.coeffs)
                self._res_q.put([_intr_mat, _intr_distcoeffs])
                continue
            self._res_q.put(stream_data(pipe=pipeline, pc=pc))
            time.sleep(self.PROCESS_SLEEP_TIME)
        pipeline.stop()


class RealSenseD405(object):
    def __init__(self, resolution: Literal['mid', 'high'] = 'high', device: str = None):
        """
        :param resolution: 'mid' or 'high'. 'mid' is 848x480, 'high' is 1280x720. The 'mid' resolution has a better accuracy.
        :param device: The serial number of the device. If None, the first device will be used.
        """
        assert resolution in ['mid', 'high']
        self._pipeline = rs.pipeline()
        self._config = rs.config()
        if device is not None:
            self._config.enable_device(device)
        # Setup config
        if resolution == 'high':
            depth_resolution = DEPTH_RESOLUTION_HIGH
            color_resolution = COLOR_RESOLUTION_HIGH
        else:
            depth_resolution = DEPTH_RESOLUTION_MID
            color_resolution = COLOR_RESOLUTION_MID

        self._config.enable_stream(rs.stream.depth, depth_resolution[0], depth_resolution[1], rs.format.z16,
                                   DEPTH_FPS)
        self._config.enable_stream(rs.stream.color, color_resolution[0], color_resolution[1], rs.format.bgr8,
                                   COLOR_FPS)
        # Start streaming with chosen configuration
        self._profile = self._pipeline.start(self._config)
        # Declare pointcloud object, for calculating pointclouds and texture mappings
        self._pc = rs.pointcloud()
        # get intrinsic matrix of the color image
        color_frame = self._pipeline.wait_for_frames().get_color_frame()
        self._color_intr = color_frame.profile.as_video_stream_profile().intrinsics
        self.intr_mat = np.array([[self._color_intr.fx, 0, self._color_intr.ppx],
                                  [0, self._color_intr.fy, self._color_intr.ppy],
                                  [0, 0, 1]])
        self.intr_distcoeffs = np.asarray(self._color_intr.coeffs)

    @property
    def intrinsics(self) -> Tuple[np.array, np.array]:
        """
        Get the intrinsic matrix and distortion coefficients of the color image
        """
        return self.intr_mat, self.intr_distcoeffs

    def get_all_data(self) -> Tuple[np.array, np.array, np.array, np.array]:
        """
        Require 1) point cloud, 2) point cloud color, 3) depth image and 4) color image
        :return: Tuple[np.array, np.array, np.array, np.array]
        """
        return stream_data(pipe=self._pipeline, pc=self._pc)

    def get_pcd(self, return_color=False) -> Tuple[np.ndarray, np.array] or np.array:
        """
        Get point cloud data. If return_color is True, additionally return pcd color
        :return: nx3 np.array
        """
        pcd, pcd_color, depth_img, color_img = self.get_all_data()
        if return_color:
            return pcd, pcd_color
        return pcd

    def get_color_img(self) -> np.array:
        """
        Get color image
        :return:
        """
        pcd, pcd_color, depth_img, color_img = self.get_all_data()
        return color_img

    def get_depth_img(self) -> np.array:
        """
        Get depth image
        :return:
        """
        pcd, pcd_color, depth_img, color_img = self.get_all_data()
        return depth_img

    def recognize_ar_marker(self, aruco_dict=None, aruco_marker_size: float = .02, toggle_show: bool = False) -> Dict[
        int, np.ndarray]:
        '''
        Functions to recognize the AR marker.
        :param aruco_dict: The dictionary of the aruco marker
        :param aruco_marker_size: The size of the aruco marker. The unit is meter
        :param toggle_show: If True, show the image with the marker
        :return: A dictionary with the key as the marker id and the value as the homomat of the marker
        '''
        if aruco_dict is None:
            aruco_dict = aruco.DICT_4X4_50
        color_img = self.get_color_img()
        parameters = aruco.DetectorParameters_create()
        aruco_dict = aruco.Dictionary_get(aruco_dict)
        corners, ids, rejectedImgPoints = aruco.detectMarkers(color_img, aruco_dict, parameters=parameters,
                                                              cameraMatrix=self.intr_mat,
                                                              distCoeff=self.intr_distcoeffs)
        poselist = []
        detected_r = {}
        if ids is not None:
            if toggle_show:
                aruco.drawDetectedMarkers(color_img, corners, borderColor=[255, 255, 0])
            rvecs, tvecs, _objPoints = aruco.estimatePoseSingleMarkers(corners, aruco_marker_size, self.intr_mat,
                                                                       self.intr_distcoeffs)
            for i in range(ids.size):
                rot = cv2.Rodrigues(rvecs[i])[0]
                pos = tvecs[i][0].ravel()
                homomat = np.eye(4)
                homomat[:3, :3] = rot
                homomat[:3, 3] = pos
                poselist.append(homomat)
                # if toggle_show:
                #     aruco.drawAxis()
        if ids is None:
            idslist = []
        else:
            idslist = ids.ravel().tolist()
        if len(idslist) > 0:
            for ind, key in enumerate(idslist):
                detected_r[key] = poselist[ind]
        return detected_r

    def stop(self):
        '''
        Stops subprocess for ethernet communication. Allows program to exit gracefully.
        '''
        self._pipeline.stop()

    def reset(self):
        """
        Reset the device
        """
        device = self._profile.get_device()
        device.hardware_reset()
        del self

    def __del__(self):
        self.stop()


if __name__ == "__main__":
    import cv2

    serials, ctx = find_devices()
    print(serials)
    rs_pipelines = []
    for ser in serials:
        rs_pipelines.append(RealSenseD405(device=ser, resolution='mid'))

    while True:
        for ind, pipeline in enumerate(rs_pipelines):
            pcd, pcd_color, depth_img, color_img = pipeline.get_all_data()
            cv2.imshow(f"color image {ind}", color_img)

        k = cv2.waitKey(1)
        if k == 27:
            break
    cv2.destroyAllWindows()

    for pipeline in rs_pipelines:
        pipeline.stop()
