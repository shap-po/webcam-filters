import time
import pyvirtualcam
from pyvirtualcam import PixelFormat
import cv2
import numpy as np
from collections import OrderedDict

from filters import Filter
import typing


class CameraError(Exception):
    '''Base exception for camera class'''


class VirtualCam:
    gui = None

    def __init__(self, camera_id: str):
        self.vc = cv2.VideoCapture(camera_id)
        if not self.vc.isOpened():
            raise CameraError('Could not open video source')
        status, frame = self.vc.read()
        if not status:
            raise CameraError('Could not open video source')
        self.height, self.width, _ = frame.shape
        self.fps = self.vc.get(cv2.CAP_PROP_FPS)
        self.global_fps = None

        self.clear_filters()

    def __del__(self):
        self.vc.release()

    def run(self):
        try:
            with pyvirtualcam.Camera(self.width, self.height, self.fps, fmt=PixelFormat.BGR) as cam:
                print(
                    f'Virtual cam started ({self.width}x{self.height} @ {self.fps}fps)')
                while self.gui and self.gui.opened:
                    status, in_frame = self.vc.read()
                    if not status:
                        raise CameraError('Error fetching frame')

                    output_frame = self.apply_filters(
                        in_frame, self.filter_list)
                    cam.send(output_frame)
                    self.gui.update_preview(output_frame.astype(np.uint8))

                    if self.global_fps is None:
                        cam.sleep_until_next_frame()
                    else:
                        time.sleep(1/self.global_fps)
        except RuntimeError:
            raise CameraError(
                'Virtual camera is in use, you need to close any apps that can write into it and restart the program.')
        finally:
            self.vc.release()

    def apply_filters(self, frame: np.ndarray, filters_list: typing.Dict[str, list[Filter]]) -> np.ndarray:
        self.global_fps = None
        ignore = len(filters_list[-2])
        for priority, filters in filters_list.items():
            if priority not in [-2, 2] and ignore:
                continue
            for filter in filters:
                new_frame = filter._apply(frame, self.gui)
                if new_frame is not None:
                    frame = new_frame
                    if filter.global_fps:
                        self.global_fps = filter.global_fps
                elif priority == -2:
                    ignore -= 1
        return frame

    # functions, used by gui.py
    def add_filter(self, filter: Filter):
        self.filter_list[filter.priority].append(filter)

    def remove_filter(self, filter: Filter):
        if filter in self.filter_list[filter.priority]:
            self.filter_list[filter.priority].remove(filter)

    def clear_filters(self):
        self.filter_list = OrderedDict({i: [] for i in range(-2, 3)})
