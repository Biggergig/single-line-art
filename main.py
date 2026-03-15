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
    def __init__(self, file_path, num_lines=0, spacing=0.0, line_width=3, min_line_width=1.0, variation_intensity=1.0, line_color="red"):
        super().__init__()
        self.setWindowTitle("SVG/Image Viewer - Ready for drawing")
        self.setGeometry(100, 100, 800, 600)
        
        # A QGraphicsScene holds the items (like your background image and future line art)
        self.scene = QGraphicsScene()
        
        # The view displays the scene
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        self.setCentralWidget(self.view)
        
        self.bg_image = None
        bg_width, bg_height = 800, 600
        
        # Load the image or SVG
        _, ext = os.path.splitext(file_path.lower())
        if ext == '.svg':
            self.item = QGraphicsSvgItem(file_path)
            self.scene.addItem(self.item)
            rect = self.item.boundingRect()
            bg_width = rect.width()
            bg_height = rect.height()
        else:
            image = QImage(file_path)
            if not image.isNull():
                # Store the background image for pixel brightness sampling
                self.bg_image = image.convertToFormat(QImage.Format.Format_Grayscale8)
                bg_width = self.bg_image.width()
                bg_height = self.bg_image.height()
                self.scene.setSceneRect(0, 0, bg_width, bg_height)
                # We intentionally DO NOT add the pixmap to the scene, 
                # so the varied line widths create the illusion of the image!
            else:
                print(f"Failed to load image: {file_path}")
                
        # Draw diagonal lines from bottom-left to top-right across the picture
        if bg_width > 0 and bg_height > 0:
            W = bg_width
            H = bg_height
            
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
                pen.setWidthF(line_width) # make the lines clearly visible
                
                start_i = -(num_lines - 1) / 2.0
                for i in range(num_lines):
                    # Evenly distribute lines across the diagonal
                    # We map a set of parallel lines with equation: x/W + y/H = C
                    # where C ranges from 0.0 (top-left) to 2.0 (bottom-right)
                    if spacing > 0 and num_lines > 0:
                        # Center the lines around C=1.0 if both parameters are explicitly provided
                        C = 1.0 + (start_i + i) * delta_C
                    else:
                        # Evenly distribute the lines between C=0 and C=2 across the image
                        C = (i + 0.5) * delta_C
                        
                    if C <= 0 or C >= 2:
                        continue
                        
                    # find intersections of the line x/W + y/H = C with the image bounding rect [0, W] x [0, H]
                    pts = []
                    
                    # Intersect with top edge (y = 0) => x/W = C => x = C * W
                    x_top = C * W
                    if 0 <= x_top <= W: pts.append((x_top, 0))
                    
                    # Intersect with bottom edge (y = H) => x/W + 1 = C => x = (C - 1) * W
                    x_bot = (C - 1) * W
                    if 0 <= x_bot <= W: pts.append((x_bot, H))
                    
                    # Intersect with left edge (x = 0) => y/H = C => y = C * H
                    y_left = C * H
                    if 0 <= y_left <= H: pts.append((0, y_left))
                    
                    # Intersect with right edge (x = W) => 1 + y/H = C => y = (C - 1) * H
                    y_right = (C - 1) * H
                    if 0 <= y_right <= H: pts.append((W, y_right))
                    
                    # Deduplicate points that land exactly on corners
                    unique_pts = []
                    for p in pts:
                        if not any(abs(p[0]-up[0]) < 1e-5 and abs(p[1]-up[1]) < 1e-5 for up in unique_pts):
                            unique_pts.append(p)
                            
                    # Draw clipping to bounding rect constraint
                    if len(unique_pts) == 2:
                        pt1 = unique_pts[0]
                        pt2 = unique_pts[1]
                        
                        dx = pt2[0] - pt1[0]
                        dy = pt2[1] - pt1[1]
                        length = math.hypot(dx, dy)
                        
                        segment_length = 3.0 # Draw in 3-pixel segments to capture detail
                        num_segments = max(1, int(length / segment_length))
                        
                        for step in range(num_segments):
                            t1 = step / num_segments
                            t2 = (step + 1) / num_segments
                            x1 = pt1[0] + dx * t1
                            y1 = pt1[1] + dy * t1
                            x2 = pt1[0] + dx * t2
                            y2 = pt1[1] + dy * t2
                            
                            mx = int((x1 + x2) / 2)
                            my = int((y1 + y2) / 2)
                            
                            brightness = 255
                            if self.bg_image is not None:
                                if 0 <= mx < self.bg_image.width() and 0 <= my < self.bg_image.height():
                                    brightness = self.bg_image.pixelColor(mx, my).red()
                                    
                            # Darker pixels -> thicker lines, Brighter pixels -> thinner lines
                            factor = (255 - brightness) / 255.0
                            
                            # Enhance contrast using an exponent so details pop
                            # variation_intensity controls how severely the line width scales.
                            # When intensity is 0, factor becomes 1.0 (no variation)
                            factor = factor ** 1.3
                            factor = 1.0 + (factor - 1.0) * variation_intensity
                            
                            current_width = line_width * factor
                            current_width = max(min_line_width, current_width) # Min width to keep paths continuous
                            
                            seg_pen = QPen(QColor(line_color))
                            seg_pen.setWidthF(current_width)
                            seg_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
                            
                            self.scene.addLine(x1, y1, x2, y2, seg_pen)
        
        # Make the image fit to the window without distorting its aspect ratio
        if self.scene.sceneRect().width() > 0:
            self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event):
        # Keeps the image fitted when the user resizes the window
        super().resizeEvent(event)
        if hasattr(self, 'scene') and self.scene.sceneRect().width() > 0:
            self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)


def main():
    parser = argparse.ArgumentParser(description="Download and display an image/SVG.")
    parser.add_argument("--url", 
                        default="https://krita-artists.org/uploads/default/original/3X/3/e/3eb0b1438164155899e2af27d6ff10157f2cab78.jpeg", 
                        help="URL of the image or SVG to download")
    parser.add_argument("--num-lines", type=int, default=50, help="Number of diagonal lines to draw (0 for auto)")
    parser.add_argument("--spacing", type=float, default=0.0, help="Spacing between lines in pixels (0 for auto)")
    parser.add_argument("--line-width", type=float, default=5.0, help="Maximum width of the diagonal lines in pixels")
    parser.add_argument("--min-line-width", type=float, default=1.0, help="Minimum width of the diagonal lines in pixels")
    parser.add_argument("--variation-intensity", type=float, default=1, help="How strongly brightness changes the line width (0.0 for uniform lines, 1.0 for full variation)")
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
        viewer = ImageViewer(temp_path, args.num_lines, args.spacing, args.line_width, args.min_line_width, args.variation_intensity, args.line_color)
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
