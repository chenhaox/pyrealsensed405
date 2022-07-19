# pyrealsensed405
A example to get data from Realsense D405

## Requirements 
Install python library `pyrealsense2` and `numpy`

## Example
1. Get depth image and color image

```python
import cv2
rs_pipe = RealSenseD405()
pcd, pcd_color, depth_img, color_img = rs_pipe.get_pcd_color_depth()
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
