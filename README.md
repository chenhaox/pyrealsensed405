# pyrealsensed405
- A high level python wrapper for Intel RealSense D405 camera. It provides a simple interface to get color image, depth image, color point cloud and depth point cloud.

- It supports RealSense d400 series camera, but only tested on D405.

**Note: D405 camera should be connected to USB3.0 port**

## Requirements 
- **Required**: Install python library `pyrealsense2` and `numpy`.
- **Optional**: Install `opencv-python` and `opencv-contrib-python` for ArUco marker detection.



## Quick Start
1. Get depth image and color image

```python
import cv2
rs_pipe = RealSenseD405()
pcd, pcd_color, depth_img, color_img = rs_pipe.get_all_data()
depth_map = cv2.normalize(depth_img, 0, 65535, cv2.NORM_MINMAX).astype(np.uint8)
depth_map = cv2.applyColorMap(dist, cv2.COLORMAP_HSV)
cv2.imshow("depth image", dist)
cv2.imshow("color image", color_img)
cv2.waitKey(0)
```

![depth and color image](./depth_color.jpg)

2. Get color point cloud
![depth and color image](./point_cloud.jpg)

## Reference
RealSense API: https://dev.intelrealsense.com/docs/python2
