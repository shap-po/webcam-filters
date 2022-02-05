import sys
import threading
from PyQt6.QtWidgets import QApplication
from camera import VirtualCam
from gui import CamGUI
from configs import camera_config


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(open('configurations/style.css').read())
    gui = CamGUI()
    camera = VirtualCam(camera_config['camera_id'])
    # link camera and gui
    camera.gui = gui
    gui.camera = camera
    gui.show()

    thread = threading.Thread(target=camera.run)
    thread.start()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
