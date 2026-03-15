import sys
import argparse
import urllib.request
import urllib.error
import tempfile
import os
from urllib.parse import urlparse
from PyQt6.QtWidgets import QApplication, QMainWindow, QGraphicsView, QGraphicsScene
from PyQt6.QtSvgWidgets import QGraphicsSvgItem
from PyQt6.QtGui import QPixmap, QPainter
from PyQt6.QtCore import Qt

class ImageViewer(QMainWindow):
    def __init__(self, file_path):
        super().__init__()
        self.setWindowTitle("SVG/Image Viewer - Ready for drawing")
        self.setGeometry(100, 100, 800, 600)
        
        # A QGraphicsScene holds the items (like your background image and future line art)
        self.scene = QGraphicsScene()
        
        # The view displays the scene
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        self.setCentralWidget(self.view)
        
        # Load the image or SVG
        _, ext = os.path.splitext(file_path.lower())
        if ext == '.svg':
            self.item = QGraphicsSvgItem(file_path)
            self.scene.addItem(self.item)
        else:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                self.scene.addPixmap(pixmap)
            else:
                print(f"Failed to load image: {file_path}")
                
        # To add things on top later, you might do things like:
        # self.scene.addLine(0, 0, 100, 100) # Draws a simple line on top of the image!
        
        # Make the image fit to the window without distorting its aspect ratio
        if self.scene.itemsBoundingRect().width() > 0:
            self.view.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event):
        # Keeps the image fitted when the user resizes the window
        super().resizeEvent(event)
        if hasattr(self, 'scene') and self.scene.itemsBoundingRect().width() > 0:
            self.view.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)


def main():
    parser = argparse.ArgumentParser(description="Download and display an image/SVG.")
    parser.add_argument("--url", required=True, help="URL of the image or SVG to download")
    args = parser.parse_args()

    url = args.url
    print(f"Downloading from: {url}...")

    # Extract a meaningful extension, default to .png if not found
    parsed_url = urlparse(url)
    _, ext = os.path.splitext(parsed_url.path)
    if not ext:
        ext = ".png"

    # Create a temporary file to save the image
    fd, temp_path = tempfile.mkstemp(suffix=ext)
    os.close(fd)
    
    exit_code = 0
    
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        
        with urllib.request.urlopen(req) as response, open(temp_path, 'wb') as f:
            f.write(response.read())
            
        print(f"Successfully downloaded to: {temp_path}")
        print("Opening in native PyQt6 application viewer...")
        
        # We must initialize the QApplication to load Qt GUIs
        app = QApplication(sys.argv)
        viewer = ImageViewer(temp_path)
        viewer.show()
        
        # Run the UI loop (it will block here until the user closes the window)
        exit_code = app.exec()
        
    except urllib.error.URLError as e:
        print(f"Error downloading image: {e}")
        exit_code = 1
    except Exception as e:
        print(f"An error occurred: {e}")
        exit_code = 1
    finally:
        # Clean up the temporary file automatically
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

    sys.exit(exit_code)

if __name__ == "__main__":
    main()
