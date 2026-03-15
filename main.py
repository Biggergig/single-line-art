import sys
import math
import argparse
import urllib.request
import urllib.error
import tempfile
import os
from urllib.parse import urlparse
from PyQt6.QtWidgets import QApplication, QMainWindow, QGraphicsView, QGraphicsScene
from PyQt6.QtSvgWidgets import QGraphicsSvgItem
from PyQt6.QtGui import QPixmap, QPainter, QImage, QPen, QColor
from PyQt6.QtCore import Qt

class ImageViewer(QMainWindow):
    def __init__(self, file_path, num_lines=0, spacing=0.0, line_width=3, line_color="red"):
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
            image = QImage(file_path)
            if not image.isNull():
                # Convert the photo to grayscale
                grayscale_image = image.convertToFormat(QImage.Format.Format_Grayscale8)
                pixmap = QPixmap.fromImage(grayscale_image)
                self.scene.addPixmap(pixmap)
            else:
                print(f"Failed to load image: {file_path}")
                
        # Draw diagonal lines from bottom-left to top-right across the picture
        rect = self.scene.itemsBoundingRect()
        if rect.width() > 0 and rect.height() > 0:
            W = rect.width()
            H = rect.height()
            
            # Determine line drawing parameters based on user input
            if spacing > 0:
                delta_C = spacing * math.hypot(W, H) / (W * H)
                if num_lines <= 0:
                    num_lines = int(2.0 / delta_C)
            else:
                if num_lines <= 0:
                    num_lines = 50
                delta_C = 2.0 / num_lines

            if num_lines > 0:
                pen = QPen(QColor(line_color))
                pen.setWidth(line_width) # make the lines clearly visible
                
                start_i = -(num_lines - 1) / 2.0
                for i in range(num_lines):
                    if spacing > 0 and num_lines > 0:
                        # Center the lines around C=1.0 if both parameters are explicitly provided
                        C = 1.0 + (start_i + i) * delta_C
                    else:
                        # Evenly distribute the lines between C=0 and C=2 across the image
                        C = (i + 0.5) * delta_C
                        
                    if C <= 0 or C >= 2:
                        continue
                        
                    # find intersections with the image bounding rect [0, W] x [0, H]
                    pts = []
                    x_top = C * W
                    if 0 <= x_top <= W: pts.append((x_top, 0))
                    
                    x_bot = (C - 1) * W
                    if 0 <= x_bot <= W: pts.append((x_bot, H))
                    
                    y_left = C * H
                    if 0 <= y_left <= H: pts.append((0, y_left))
                    
                    y_right = (C - 1) * H
                    if 0 <= y_right <= H: pts.append((W, y_right))
                    
                    # Deduplicate points that land exactly on corners
                    unique_pts = []
                    for p in pts:
                        if not any(abs(p[0]-up[0]) < 1e-5 and abs(p[1]-up[1]) < 1e-5 for up in unique_pts):
                            unique_pts.append(p)
                            
                    # Draw clipping to bounding rect constraint
                    if len(unique_pts) == 2:
                        self.scene.addLine(unique_pts[0][0], unique_pts[0][1], unique_pts[1][0], unique_pts[1][1], pen)
        
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
    parser.add_argument("--url", 
                        default="https://krita-artists.org/uploads/default/original/3X/3/e/3eb0b1438164155899e2af27d6ff10157f2cab78.jpeg", 
                        help="URL of the image or SVG to download")
    parser.add_argument("--num-lines", type=int, default=0, help="Number of diagonal lines to draw (0 for auto)")
    parser.add_argument("--spacing", type=float, default=0.0, help="Spacing between lines in pixels (0 for auto)")
    parser.add_argument("--line-width", type=int, default=3, help="Width of the diagonal lines in pixels")
    parser.add_argument("--line-color", type=str, default="red", help="Color of the diagonal lines (e.g. 'red', '#ff0000')")
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
        viewer = ImageViewer(temp_path, args.num_lines, args.spacing, args.line_width, args.line_color)
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
