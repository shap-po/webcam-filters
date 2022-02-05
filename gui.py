from PyQt6.QtWidgets import QMainWindow, QPushButton, QWidget, QGridLayout, QLabel, QSlider
from PyQt6.QtGui import QImage, QPixmap, QPainter, QPainterPath
from PyQt6.QtCore import QSize, Qt, pyqtSignal
import keyboard  # I preffer using keyboard module instead of Qt shortcuts, because it can handle more buttons
import cv2

from configs import load_config
import filters


def clear_layout(layout):
    if layout is not None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
            else:
                clear_layout(item.layout())


class FramePositionError(Exception):
    '''This exception is thrown when the position of frame is not valid'''


class FilterButton(QPushButton):
    def __init__(self, parent: "CamGUI", target: dict):
        super().__init__('', parent)

        filter_name = target.get('filter')
        button_name = target.get('name') or filter_name

        self.setText(button_name)
        self.clicked.connect(self.on_click)
        self.setCheckable(True)

        self.parent = parent
        self.target = target

        self.filter = None
        self.filter_class = getattr(filters, filter_name)
        self.filter_args = target.get('args', [])
        if isinstance(self.filter_args, dict):
            self.filter_kwargs = self.filter_args
            self.filter_args = []
        else:
            self.filter_kwargs = {}

        hotkey = target.get('hotkey')
        if hotkey:
            self.add_hotkey(hotkey, button_name)

    def add_hotkey(self, hotkey, button_name):
        # if there a list of hotkeys - create a bind for them all
        if isinstance(hotkey, list):
            for key in hotkey:
                keyboard.add_hotkey(key, lambda: self.click())
            hotkeys = ' | '.join(hotkey)
            self.setText(f'{button_name}\n({hotkeys})')
        # if hotkeys are fixed values - bind them
        elif isinstance(hotkey, dict):
            for key, value in hotkey.items():
                if value is True:
                    keyboard.add_hotkey(key, lambda: self.switch_on())
                elif value is False:
                    keyboard.add_hotkey(key, lambda: self.switch_off())
                else:
                    keyboard.add_hotkey(key, lambda: self.click())
            hotkeys = ' | '.join(hotkey.keys())
            self.setText(f'{button_name}\n({hotkeys})')
        # and if there is just a single hotkey - bind it too
        else:
            keyboard.add_hotkey(hotkey, lambda: self.click())
            self.setText(f'{button_name}\n({hotkey})')

    # main function for bindings
    def switch_to(self, state: bool):
        if self.isChecked() != state:
            self.click()

    # function for bindings
    def switch_on(self):
        self.switch_to(True)

    # function for bindings
    def switch_off(self):
        self.switch_to(False)

    def on_click(self):
        if self.parent.camera:
            if self.isChecked():
                self.filter = self.filter_class(
                    *self.filter_args, **self.filter_kwargs)
                self.parent.camera.add_filter(self.filter)
            else:
                self.parent.camera.remove_filter(self.filter)

    def update_filter(self):
        if self.filter:
            self.filter.__init__(*self.filter_args, **self.filter_kwargs)

    def reset(self):
        if bool(self.target.get('enabled')) != self.isChecked():
            self.click()


class Slider(QSlider):
    def __init__(self, parent, properties: filters.SliderProperties, button: FilterButton, label: QLabel):
        super().__init__(parent)

        self.setOrientation(Qt.Orientation.Horizontal)

        # filter properties can be callable, so create a instance of filter to calculate properties
        temp_filter = button.filter_class(
            *button.filter_args, **button.filter_kwargs)
        if callable(properties.min):
            properties.min = properties.min(temp_filter)
        if callable(properties.max):
            properties.max = properties.max(temp_filter)
        if callable(properties.step):
            properties.step = properties.step(temp_filter)
        if callable(properties.default):
            properties.default = properties.default(temp_filter)

        self.setMinimum(properties.min)
        self.setMaximum(properties.max)
        self.setSingleStep(properties.step)
        self.setTickInterval(properties.step)
        self.valueChanged.connect(self.on_change)

        self.variable = properties.variable
        self.label_name = properties.label_name

        self.button = button
        self.label = label
        self.default = properties.default
        self.fixed = False

        # set value to maximum to get maximum width
        self.setValue(properties.max)

    def fix_size(self):
        self.label.setFixedWidth(self.label.width())
        self.setValue(self.default)

    def on_change(self):
        self.button.filter_kwargs[self.variable] = self.value()
        self.button.update_filter()
        self.label.setText(self.label_name(self.value()))

    def showEvent(self, event):
        if not self.fixed:
            self.fix_size()
            self.fixed = True


class RoundedPreviewLabel(QLabel):
    inited = False

    # rounded frame borders are separate class because of Qt
    class RoundedFrameBorders(QLabel):
        def set_size(self, size: QSize):
            self.setFixedSize(QSize(size.width()+2, size.height()+2))

    def __init__(self, parent):
        super().__init__(parent)
        self.frame = self.RoundedFrameBorders(parent)

    # create a borders and a painter when we know the size of the image
    def init(self, size: QSize):
        self.Antialiasing = True
        self.radius = 25

        self.target = QPixmap(size)
        self.target.fill(Qt.GlobalColor.transparent)

        self.painter = QPainter(self.target)
        if self.Antialiasing:
            self.painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            self.painter.setRenderHint(
                QPainter.RenderHint.SmoothPixmapTransform, True)

        path = QPainterPath()
        path.addRoundedRect(
            0, 0, size.width(), size.height(), self.radius, self.radius)
        self.painter.setClipPath(path)

        self.frame.set_size(size)
        self.setFixedSize(size)

        self.inited = True

    def update(self, image: QImage):
        if not self.inited:
            self.init(image.size())

        self.painter.drawPixmap(0, 0, QPixmap.fromImage(image))
        self.setPixmap(self.target)

    def __del__(self):
        # Stop the painter, so it doesn't raise an error when the window is closed or reloaded
        self.painter.end()


class PreviewLabel(QLabel):
    fixed = False

    def update(self, image: QImage):
        self.setPixmap(QPixmap.fromImage(image))
        # fix the size, so the window will not crash on resize
        if not self.fixed:
            self.setFixedSize(image.size())
            self.fixed = True


class CamGUI(QMainWindow):
    camera = None
    opened = True
    reloaded = pyqtSignal()

    def __init__(self):
        super().__init__()
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.layout: QGridLayout = QGridLayout(central_widget)
        self.reloaded.connect(self.reload_gui)
        self.preview_frame = None
        self.reload_gui()

    # This function is used to place elements to the GUI
    def reload_gui(self):
        self.gui_config = load_config('gui')
        self.setWindowTitle(self.gui_config['title'])
        self.buttons = []

        self.row_offset = 0
        self.column_offset = 0
        # if the gui is enabled in the config
        if self.gui_config['preview']['enabled']:
            self.preview_frame = RoundedPreviewLabel(
                self) if self.gui_config['preview']['round'] else PreviewLabel(self)  # pick the class for the preview frame
            # calculate the offset for buttons
            position = self.gui_config['preview']['position'].lower()
            if position in ['up', 'top', 'u', 't']:
                self.row_offset = 1
            elif position in ['left', 'l']:
                self.column_offset = 1

        clear_layout(self.layout)

        self.place_buttons()
        if self.gui_config['preview']['enabled']:
            self.place_frame()
        self.camera_inited = False  # run filters on the first frame

    def place_frame(self):
        # I don't like this part of code, but it is used to calculate the position of the preview frame
        position = self.gui_config['preview']['position'].lower()
        if position in ['up', 'top', 'u', 't']:
            row = 0
            column = 0
            row_end = 1
            column_end = self.layout.columnCount()
        elif position in ['down', 'bottom', 'd', 'b']:
            row = self.layout.rowCount()
            column = 0
            row_end = self.layout.rowCount()+1
            column_end = self.layout.columnCount()
        elif position in ['right', 'r']:
            row = 0
            column = self.layout.columnCount()
            row_end = self.layout.rowCount()
            column_end = self.layout.columnCount()+1
        elif position in ['left', 'l']:
            row = 0
            column = 0
            row_end = self.layout.rowCount()
            column_end = 1
        else:
            raise FramePositionError('Unknown position')
        # When we know the position, place the frame
        self.layout.addWidget(self.preview_frame, row, column, row_end, column_end,
                              alignment=Qt.AlignmentFlag.AlignCenter)
        if self.gui_config['preview']['round']:
            self.layout.addWidget(self.preview_frame.frame, row, column, row_end, column_end,
                                  alignment=Qt.AlignmentFlag.AlignCenter)

    # This function is used to place buttons in the GUI
    def place_buttons(self):
        for row in range(len(self.gui_config['buttons'])):
            skip = 0
            for column in range(len(self.gui_config['buttons'][row])):
                button_config = self.gui_config['buttons'][row][column]
                if isinstance(button_config, dict):
                    filter_name = button_config.get('filter')
                    # skip the button if it's name starts with '_' or not valid
                    if not filter_name or filter_name.startswith('_'):
                        skip += 1
                        continue
                    self.place_button(button_config, row, column-skip)
                elif isinstance(button_config, str):
                    # TODO Create a label
                    pass

    # This function is used to place the button in the GUI
    def place_button(self, button_config: dict, row: int, column: int):
        row += self.row_offset
        column += self.column_offset

        filter_name = button_config.get('filter')
        filter_class: filters.Filter = getattr(filters, filter_name)
        button = FilterButton(self, button_config)
        if not filter_class.sliders:
            self.layout.addWidget(button, row, column)
        else:
            layout = QGridLayout()
            layout.addWidget(button, 0, 0, 1, 2)
            for index, slider_properties in enumerate(filter_class.sliders):
                slider_label = QLabel(slider_properties.name, self)
                slider = Slider(
                    self, slider_properties, button, slider_label)
                layout.addWidget(slider_label, index+1, 0)
                layout.addWidget(slider, index+1, 1)
            self.layout.addLayout(layout, row, column)
        self.buttons.append(button)

    def update_preview(self, image):
        if not self.gui_config['preview']['enabled']:
            return
        if not self.camera_inited and self.camera:
            for button in self.buttons:
                button.reset()
            self.camera_inited = True
        if self.gui_config['preview']['mirrored']:
            image = cv2.flip(image, 1)
        self.image = QImage(
            image.data, image.shape[1], image.shape[0], QImage.Format.Format_BGR888)
        self.preview_frame.update(self.image)

    def clear_filters(self):
        self.camera.clear_filters()

    def closeEvent(self, event):
        self.opened = False
