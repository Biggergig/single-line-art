import sys
import math
import argparse
import urllib.request
import urllib.error
import tempfile
import os
from urllib.parse import urlparse
from PyQt6.QtWidgets import (QApplication, QMainWindow, QGraphicsView, QGraphicsScene, 
                               QWidget, QVBoxLayout, QHBoxLayout, QSlider, QLabel,
                               QSpinBox, QDoubleSpinBox, QPushButton, QFileDialog)
from PyQt6.QtSvgWidgets import QGraphicsSvgItem
from PyQt6.QtSvg import QSvgGenerator
from PyQt6.QtGui import QPixmap, QPainter, QImage, QPen, QColor
from PyQt6.QtCore import Qt, QLineF, QSize, QRectF

class ImageViewer(QMainWindow):
    def __init__(self, file_path, num_lines=50, spacing=0.0, line_width=5.0, min_line_width=1.0, variation_intensity=1.0, line_color="red"):
        super().__init__()
        self.setWindowTitle("SVG/Image Viewer - Ready for drawing")
        self.setGeometry(100, 100, 800, 600)
        
        
        # Central widget and layout for the sidebar and canvas
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        
        # --- Sidebar ---
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar.setFixedWidth(250)
        
        self.num_lines_slider = self.create_slider("Number of Lines", sidebar_layout, 10, 300, num_lines)
        self.max_width_slider = self.create_slider("Max Width", sidebar_layout, 1, 50, int(line_width))
        self.min_width_slider = self.create_slider("Min Width", sidebar_layout, 0, 20, int(min_line_width))
        self.variation_slider = self.create_slider("Variation Intensity", sidebar_layout, 0, 30, int(variation_intensity * 10), is_float=True)
        
        # --- Export Button ---
        self.export_button = QPushButton("Export to SVG")
        self.export_button.clicked.connect(self.export_svg)
        sidebar_layout.addWidget(self.export_button)
        
        sidebar_layout.addStretch() # Push everything to top
        main_layout.addWidget(sidebar)
        
        # --- Canvas ---
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        main_layout.addWidget(self.view)
        
        self.bg_image = None
        self.bg_width, self.bg_height = 800, 600
        self.line_color = line_color
        self.file_path = file_path # stash for resizing

        
        # Load the image or SVG
        _, ext = os.path.splitext(file_path.lower())
        if ext == '.svg':
            self.item = QGraphicsSvgItem(file_path)
            self.scene.addItem(self.item)
            rect = self.item.boundingRect()
            rect = self.item.boundingRect()
            self.bg_width = rect.width()
            self.bg_height = rect.height()
        else:
            image = QImage(file_path)
            if not image.isNull():
                # Store the background image for pixel brightness sampling
                self.bg_image = image.convertToFormat(QImage.Format.Format_Grayscale8)
                self.bg_width = self.bg_image.width()
                self.bg_height = self.bg_image.height()
                self.scene.setSceneRect(0, 0, self.bg_width, self.bg_height)
                # We intentionally DO NOT add the pixmap to the scene, 
                # so the varied line widths create the illusion of the image!
            else:
                print(f"Failed to load image: {file_path}")
                
        # Draw the initial lines
        self.draw_lines()
        self.fit_view()

    def create_slider(self, label_text, layout, min_val, max_val, default_val, is_float=False):
        row_layout = QHBoxLayout()
        label = QLabel(label_text + ":")
        row_layout.addWidget(label)
        
        if is_float:
            spin_box = QDoubleSpinBox()
            spin_box.setMinimum(min_val / 10.0)
            spin_box.setMaximum(max_val / 10.0)
            spin_box.setSingleStep(0.1)
            spin_box.setValue(default_val / 10.0)
        else:
            spin_box = QSpinBox()
            spin_box.setMinimum(min_val)
            spin_box.setMaximum(max_val)
            spin_box.setValue(default_val)
            
        row_layout.addWidget(spin_box)
        layout.addLayout(row_layout)
        
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(min_val)
        slider.setMaximum(max_val)
        slider.setValue(default_val)
        
        # Keep the text box and the slider synced up!
        slider.valueChanged.connect(lambda val: spin_box.setValue(val / 10.0 if is_float else val))
        if is_float:
            spin_box.valueChanged.connect(lambda val: slider.setValue(int(val * 10)))
        else:
            spin_box.valueChanged.connect(slider.setValue)
            
        # Draw new lines on slider changes
        slider.valueChanged.connect(self.draw_lines)
        layout.addWidget(slider)
        return slider

    def draw_lines(self):
        self.scene.clear()
        
        num_lines = self.num_lines_slider.value()
        line_width = self.max_width_slider.value()
        min_line_width = self.min_width_slider.value()
        variation_intensity = self.variation_slider.value() / 10.0
        
        if self.bg_width > 0 and self.bg_height > 0:
            W = self.bg_width
            H = self.bg_height
            
            # Massive graphics optimization: draw everything natively to a single QPixmap 
            # instead of adding hundreds of thousands of individual line segments to the QGraphicsScene
            pixmap = QPixmap(W, H)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Refactored to reuse logic
            self.paint_lines(painter, W, H)
                            
            painter.end()
            self.scene.addPixmap(pixmap)

    def paint_lines(self, painter, W, H):
        """Helper method that shares the same exact drawing logic for both screen and SVG export."""
        num_lines = self.num_lines_slider.value()
        line_width = self.max_width_slider.value()
        min_line_width = self.min_width_slider.value()
        variation_intensity = self.variation_slider.value() / 10.0
        
        if num_lines <= 0:
            num_lines = 50
        delta_C = 2.0 / num_lines

        if num_lines > 0:
            start_i = -(num_lines - 1) / 2.0
            for i in range(num_lines):
                C = (i + 0.5) * delta_C
                    
                if C <= 0 or C >= 2:
                    continue
                    
                pts = []
                
                x_top = C * W
                if 0 <= x_top <= W: pts.append((x_top, 0))
                
                x_bot = (C - 1) * W
                if 0 <= x_bot <= W: pts.append((x_bot, H))
                
                y_left = C * H
                if 0 <= y_left <= H: pts.append((0, y_left))
                
                y_right = (C - 1) * H
                if 0 <= y_right <= H: pts.append((W, y_right))
                
                unique_pts = []
                for p in pts:
                    if not any(abs(p[0]-up[0]) < 1e-5 and abs(p[1]-up[1]) < 1e-5 for up in unique_pts):
                        unique_pts.append(p)
                        
                if len(unique_pts) == 2:
                    pt1 = unique_pts[0]
                    pt2 = unique_pts[1]
                    
                    dx = pt2[0] - pt1[0]
                    dy = pt2[1] - pt1[1]
                    length = math.hypot(dx, dy)
                    
                    segment_length = 3.0 
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
                                
                        factor = (255 - brightness) / 255.0
                        factor = factor ** 1.3
                        factor = 1.0 + (factor - 1.0) * variation_intensity
                        
                        current_width = line_width * factor
                        current_width = max(min_line_width, current_width)
                        
                        seg_pen = QPen(QColor(self.line_color))
                        seg_pen.setWidthF(current_width)
                        seg_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
                        
                        painter.setPen(seg_pen)
                        painter.drawLine(QLineF(x1, y1, x2, y2))

    def export_svg(self):
        if self.bg_width <= 0 or self.bg_height <= 0:
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save SVG", "line_art.svg", "SVG Files (*.svg)"
        )
        
        if file_path:
            generator = QSvgGenerator()
            generator.setFileName(file_path)
            generator.setSize(QSize(self.bg_width, self.bg_height))
            generator.setViewBox(QRectF(0, 0, self.bg_width, self.bg_height))
            generator.setTitle("Single Line Art Generate")
            
            painter = QPainter(generator)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            self.paint_lines(painter, self.bg_width, self.bg_height)
            painter.end()
            
            print(f"Successfully exported to: {file_path}")

    def fit_view(self):
        # Make the image fit to the window without distorting its aspect ratio
        if self.scene.sceneRect().width() > 0:
            self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event):
        # Keeps the image fitted when the user resizes the window
        super().resizeEvent(event)
        self.fit_view()


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
