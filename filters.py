import cv2
from enum import IntEnum
from numpy import ndarray
import numpy as np
import random
import typing

# Base classes


class SliderProperties:
    def __init__(self, name: str,
                 variable: str = None,
                 min: typing.Union[int, float] = 0,
                 max: typing.Union[int, float] = 0,
                 step: typing.Union[int, float] = 1,
                 default: typing.Union[int, float] = None,
                 fstring: str = '{name}: {spacing}{value}'):
        self.name = name
        self.variable = variable or name
        self.min = min
        self.max = max
        self.step = step
        self.default = default if default is not None else lambda filter: filter.__dict__[
            variable]
        self.fstring = fstring

    def label_name(self, value):
        spacing = (len(str(self.max))-len(str(value)))*'  '
        return self.fstring.format(name=self.name, spacing=spacing, value=value)


class ChanceSlider(SliderProperties):
    def __init__(self, name: str = 'Chance',
                 variable: str = 'chance',
                 min: typing.Union[int, float] = 0,
                 max: typing.Union[int, float] = 100,
                 step: typing.Union[int, float] = 1,
                 default: typing.Union[int, float] = 100,
                 fstring: str = '{name}: {spacing}{value}%'):
        super().__init__(name=name, variable=variable,
                         min=min, max=max, step=step, default=default, fstring=fstring)


class FPS_Slider(SliderProperties):
    def __init__(self, name: str = 'FPS',
                 variable: str = 'global_fps',
                 min: typing.Union[int, float] = 1,
                 max: typing.Union[int, float] = 60,
                 step: typing.Union[int, float] = 1,
                 default: typing.Union[int, float] = 35,
                 fstring: str = '{name}: {spacing}{value}'):
        super().__init__(name=name, variable=variable,
                         min=min, max=max, step=step, default=default, fstring=fstring)


class Filter:
    '''
    Base class for camera filters

    Args:
        priority (int): a number from -2 to 1, where
            -2: apply filter and ignore others
            -1: apply filter as fast as you can
            0: I don't care when you will apply filter
            1: apply filter in the very end
            2: apply filter in the very end, even if there is filter with priority -2

        sliders (list[`SliderProperties`])

        chance (int): a number form 0 to 100, represents chance of filter to apply

        global_fps (int | None): fps of camera output

    Functions:
        _apply: main function, that will be executed by the camera script. It must not be modified
        apply: the function, that applies the filter to the frame
        modify_gui: the function, that applies the filter to gui

    '''
    priority: int = 0
    sliders: typing.List[SliderProperties] = []
    chance: int = 100
    global_fps: typing.Union[int, None] = None
    toggleable: bool = True  # TODO: toggleable

    def _apply(self, frame: ndarray, gui) -> typing.Optional[ndarray]:
        if self.chance >= 100 or self.chance >= random.random() * 100:
            self.modify_gui(gui)
            return self.apply(frame)

    def apply(self, frame: ndarray) -> typing.Optional[ndarray]:
        return None

    def modify_gui(self, gui) -> None:
        return None

    def on_disable(self, gui) -> None:
        # TODO: disable
        return None

# Filters


class Pause(Filter):
    priority = 2

    def __init__(self):
        self.saved_frame = None

    def apply(self, frame: ndarray) -> ndarray:
        if self.saved_frame is None:
            self.saved_frame = np.copy(frame)
        return np.copy(self.saved_frame)


class MirrorX(Filter):
    priority = 0

    def apply(self, frame: ndarray) -> ndarray:
        return cv2.flip(frame, 1)


class MirrorY(Filter):
    priority = 0

    def apply(self, frame: ndarray) -> ndarray:
        return cv2.flip(frame, 0)


class Negative(Filter):
    priority = 0

    def apply(self, frame: ndarray) -> ndarray:
        return 1 - frame


class Grayscale(Filter):
    priority = 0

    def apply(self, frame: ndarray) -> ndarray:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        return frame


class FPS(Filter):
    priority = 0
    sliders = [FPS_Slider(default=3)]

    def __init__(self, global_fps: int = None):
        self.global_fps = global_fps

    def apply(self, frame: ndarray) -> ndarray:
        return frame


def trim_image(img: ndarray, width: int, height: int) -> ndarray:
    image_height, image_width, _ = img.shape
    if image_width > image_height:
        img = cv2.resize(
            img, (int(round(height * image_width / image_height)), height))
    else:
        img = cv2.resize(
            img, (width, int(round(width * image_height / image_width))))
    image_height, image_width, _ = img.shape
    return img[round(image_height/2)-round(height/2):round(image_height/2)+round(height/2), round(image_width/2)-round(width/2):round(image_width/2)+round(width/2)]


class Image(Filter):
    priority = -1

    def __init__(self, image_path: str, resize: bool = False):
        self.image_path = image_path
        self.resize = resize

        self.image = None

    def apply(self, frame: ndarray) -> ndarray:
        if self.image is None:
            height, width, _ = frame.shape
            img = cv2.imread(self.image_path, cv2.IMREAD_COLOR)
            if self.resize:
                self.image = cv2.resize(img, (width, height))
            else:
                self.image = trim_image(img, width, height)
        return np.copy(self.image)


class ImageList(Image):
    sliders = [SliderProperties('Image', 'index', min=0,
                                max=lambda filter: len(filter.images)-1)]

    def __init__(self, images: typing.List[typing.List[str]], index: int = 0):
        self.images = images
        self.index = index

        self.image = None
        self.image_path = images[index][0]
        self.resize = images[index][1] if len(images[index]) > 1 else False


class Video(Filter):
    priority = -1
    sliders = [FPS_Slider()]

    height, width = None, None
    video = None

    def __init__(self, video_path: str, resize: bool = False, global_fps: int = None):
        self.video_path = video_path
        self.resize = resize
        self.global_fps = global_fps

    def __del__(self):
        if self.video:
            self.video.release()

    def apply(self, frame: ndarray) -> ndarray:
        if self.height is None:
            self.height, self.width, _ = frame.shape
        if self.video is None:
            self.video = cv2.VideoCapture(self.video_path)
        if self.video.isOpened():
            ret, frame = self.video.read()
            if ret is True:
                if self.resize:
                    return cv2.resize(frame, (self.width, self.height))
                else:
                    return trim_image(frame, self.width, self.height).astype(np.uint8)
        self.video = None
        return self.apply(None)


class Interpolation(IntEnum):
    nearest = cv2.INTER_NEAREST   # 0
    lenear = cv2.INTER_LINEAR     # 1
    cubic = cv2.INTER_CUBIC       # 2
    area = cv2.INTER_AREA         # 3
    lanczos = cv2.INTER_LANCZOS4  # 4

    smooth = cv2.INTER_LINEAR
    pixelized = cv2.INTER_AREA


class Pixelized(Filter):
    priority = 0
    sliders = [SliderProperties('Pixelisation', 'pixelisation_k', min=1, max=20, step=1),
               SliderProperties('Interpolation', 'interpolation', min=0, max=4)]

    def __init__(self, pixelisation_k: float = 3, interpolation: Interpolation = 3):
        self.pixelisation_k = pixelisation_k
        self.interpolation = interpolation

    def apply(self, frame: ndarray) -> ndarray:
        height, width, _ = frame.shape

        if self.pixelisation_k > 0:
            frame = cv2.resize(frame, (width//self.pixelisation_k, height // self.pixelisation_k),
                               interpolation=self.interpolation)
            frame = cv2.resize(frame, (width, height),
                               interpolation=self.interpolation)
        return frame


class SkipFrames(Filter):
    priority = 0
    sliders = [SliderProperties('Frames loss', 'frames_loss', min=1,
                                max=40), ChanceSlider()]

    saved_frame = None

    def __init__(self, frames_loss: int = 1, chance: float = 1):
        '''frames_loss - frames lost per displayed frame'''
        self.frames_loss = frames_loss
        self.frames_lost = 0
        self.chance = chance

    def apply(self, frame: ndarray) -> typing.Optional[ndarray]:
        if self.frames_lost == 0:
            self.saved_frame = np.copy(frame)
        if self.frames_lost < self.frames_loss:
            self.frames_lost += 1
            return self.saved_frame
        self.frames_lost = 0


class Blur(Filter):
    priority = 0
    sliders = [SliderProperties('Blur', 'blur_k', min=1, max=100)]

    def __init__(self, blur_k: int = 1):
        self.blur_k = blur_k

    def apply(self, frame: ndarray) -> ndarray:
        return cv2.blur(frame, (self.blur_k, self.blur_k))


class Noise(Filter):
    priority = 0
    sliders = [SliderProperties('Density', 'density', min=1, max=255)]

    def __init__(self, density: int = 8):
        self.density = density

    def apply(self, frame: ndarray) -> ndarray:
        mask = (np.random.rand(*frame.shape)*self.density).astype(np.uint8)
        return frame+mask

# GUI filters


class ReloadGUI(Filter):
    priority = -2

    def modify_gui(self, gui):
        gui.clear_filters()
        gui.reloaded.emit()


class ResetButtons(Filter):
    priority = -2

    def modify_gui(self, gui):
        for button in gui.buttons:
            button.reset()


class DeactivateAll(Filter):
    priority = -2
    ignore = [Pause]

    def modify_gui(self, gui):
        for button in gui.buttons:
            if button.filter_class not in self.ignore:
                button.switch_off()


class ActivateAll(Filter):
    priority = -2
    ignore = [Pause, ReloadGUI, ResetButtons, DeactivateAll]

    def modify_gui(self, gui):
        for button in gui.buttons:
            if isinstance(self, button.filter_class):
                button.switch_off()
            elif button.filter_class not in self.ignore:
                button.switch_on()


class FilterPack(Filter):  # TODO add sliders
    # this filter has no priority attribute here, because it can be set in config file

    # filters must look like this: [{'filter': FilterClass, 'args': dict|list}]
    def __init__(self, filters: typing.List[dict], priority=0):
        self.priority = priority
        self.filters = []
        for filter in filters:
            args = filter.get('args', [])
            filter_class: Filter = globals()[filter['filter']]
            if isinstance(args, dict):
                filter_class = filter_class(**args)
            else:
                filter_class = filter_class(*args)
            self.filters.append(filter_class)
            if filter_class.global_fps is not None:
                self.global_fps = filter_class.global_fps

    def _apply(self, frame: ndarray, gui) -> typing.Optional[ndarray]:
        if self.chance >= 100 or self.chance >= random.random() * 100:
            self.modify_gui(gui)
            return self.apply(frame, gui)

    def apply(self, frame: ndarray, gui) -> ndarray:
        for filter in self.filters:
            new_frame = filter._apply(frame, gui)
            if new_frame is not None:
                frame = new_frame
        return frame
