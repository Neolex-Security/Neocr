import tempfile
import os
import sys
import subprocess
import json
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from ollama_ocr import OCRProcessor
import mss
import pyperclip

try:
    import requests
except ImportError:
    requests = None

# Require PySide6 - exit if not available
try:
    from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                                   QLabel, QComboBox, QLineEdit, QPushButton, QFrame)
    from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QRect
    from PySide6.QtGui import QColor, QPainter, QPainterPath, QFont
    HAS_PYSIDE6 = True
except ImportError:
    print("Error: PySide6 is required but not installed.")
    print("Please install it with: pip install PySide6")
    sys.exit(1)

# Require pynput - exit if not available
try:
    from pynput import keyboard
    HAS_PYNPUT = True
except ImportError:
    print("Error: pynput is required but not installed.")
    print("Please install it with: pip install pynput")
    sys.exit(1)

# Config file path for saving last used model
CONFIG_DIR = os.path.expanduser('~/.config/neocr')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')


def get_last_model():
    """Get the last used model from config file"""
    default_model = 'qwen3-vl:8b'
    
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return config.get('last_model', default_model)
    except Exception:
        pass
    
    return default_model


def save_last_model(model_name):
    """Save the last used model to config file"""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        config = {'last_model': model_name}
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)
    except Exception:
        pass


def get_default_vision_models():
    """Get default vision models without API call"""
    return [
        'qwen3-vl:8b',
        'qwen2-vl:7b',
        'qwen2-vl:2b',
        'llava:latest',
        'llava:13b',
        'llava:7b',
        'gemma3:4b',
        'gemma3:12b'
    ]


def get_vision_models(ollama_url='http://localhost:11434'):
    """Fetch available models from Ollama API and filter vision-capable models"""
    if requests is None:
        # Fallback to default models if requests is not available
        return get_default_vision_models()
    
    vision_models = []
    
    try:
        # Get list of all models
        response = requests.get(f'{ollama_url}/api/tags', timeout=5)
        if response.status_code != 200:
            raise Exception(f"API returned status {response.status_code}")
        
        data = response.json()
        models = data.get('models', [])
        
        # Keywords that indicate vision capabilities
        vision_keywords = ['vl', 'vision', 'llava', 'multimodal', 'image', 'clip', 'visual']
        # Exclude common non-vision model names
        exclude_keywords = [ 'mistral', 'phi', 'codellama', 'deepseek-coder', 
                           'starcoder', 'wizardcoder', 'neural-chat', 'orca']
        
        # Check each model for vision capabilities
        for model_info in models:
            model_name = model_info.get('name', '')
            model_lower = model_name.lower()
            
            # Skip if it's clearly a non-vision model
            if any(exclude in model_lower for exclude in exclude_keywords):
                # Only include if it explicitly has vision keywords
                if not any(keyword in model_lower for keyword in vision_keywords):
                    continue
            
            # Check if model name contains vision keywords
            if any(keyword in model_lower for keyword in vision_keywords):
                vision_models.append(model_name)
                continue
            
            # Check model details for vision support
            try:
                detail_response = requests.post(
                    f'{ollama_url}/api/show',
                    json={'name': model_name},
                    timeout=5
                )
                if detail_response.status_code == 200:
                    detail_data = detail_response.json()
                    # Check for vision-related fields in model details
                    modelfile = detail_data.get('modelfile', '').lower()
                    details_str = json.dumps(detail_data).lower()
                    
                    # Check parameters for vision capabilities
                    parameters = detail_data.get('parameters', '')
                    if isinstance(parameters, str):
                        parameters = parameters.lower()
                    else:
                        parameters = str(parameters).lower()
                    
                    # Check for vision support indicators
                    has_vision = any(keyword in modelfile or keyword in details_str or keyword in parameters
                                   for keyword in vision_keywords)
                    
                    # Also check for specific vision model families
                    if 'llava' in model_lower or 'qwen' in model_lower and 'vl' in model_lower:
                        has_vision = True
                    
                    if has_vision:
                        vision_models.append(model_name)
            except Exception:
                # If we can't check details, skip this model
                continue
        
        # Remove duplicates and sort
        vision_models = sorted(list(set(vision_models)))
        
    except Exception as e:
        print(f"Warning: Could not fetch models from Ollama API: {e}")
        # Fallback to default models
        vision_models = get_default_vision_models()
    
    return vision_models if vision_models else get_default_vision_models()


class GlassyWidget(QWidget):
    """Widget with glassy effect - frameless, translucent, rounded corners"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.radius = 20
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Create rounded rectangle path
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 
                           self.radius, self.radius)
        
        # Fill with semi-transparent background
        painter.fillPath(path, QColor(43, 43, 43, 240))  # Dark with transparency
        
        # Draw border
        painter.setPen(QColor(85, 85, 85, 180))
        painter.drawPath(path)


class GlassyButton(QPushButton):
    """Button with glassy grey transparent effect"""
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.radius = 15
        self.setCursor(Qt.PointingHandCursor)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Create rounded rectangle path
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 
                           self.radius, self.radius)
        
        # Grey glassy color with less opacity (more transparent)
        if self.isDown():
            color = QColor(100, 100, 100, 120)  # Darker grey when pressed, more transparent
        elif self.underMouse():
            color = QColor(120, 120, 120, 100)  # Lighter grey on hover, more transparent
        else:
            color = QColor(110, 110, 110, 80)  # Normal grey with less opacity
        
        painter.fillPath(path, color)
        
        # Draw subtle border for glass effect (more transparent)
        border_color = QColor(150, 150, 150, 80)  # Light grey border with less opacity
        painter.setPen(border_color)
        painter.drawPath(path)
        
        # Draw text with slight shadow for better visibility
        text_rect = self.rect()
        # Shadow
        painter.setPen(QColor(0, 0, 0, 100))
        painter.setFont(QFont("Helvetica", 10, QFont.Bold))
        painter.drawText(text_rect.adjusted(1, 1, 1, 1), Qt.AlignCenter, self.text())
        # Main text
        painter.setPen(QColor(255, 255, 255, 240))
        painter.drawText(text_rect, Qt.AlignCenter, self.text())


def select_model():
    """Display a toolbar window to select the Ollama model"""
    # Use default models initially (don't fetch from API)
    vision_models = get_default_vision_models()
    
    if not vision_models:
        print("Warning: No vision models found. Using default.")
        vision_models = ['qwen3-vl:8b']
    
    return select_model_pyside6(vision_models)  # PySide6 is required


def select_model_pyside6(vision_models):
    """PySide6 version with glassy effect"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    selected_model = {'value': None}
    dialog_closed = {'value': False}
    
    # Create glassy window
    window = GlassyWidget()
    window.setFixedSize(520, 320)
    
    # Center window
    screen = app.primaryScreen().geometry()
    window.move((screen.width() - window.width()) // 2,
                (screen.height() - window.height()) // 2)
    
    # Main layout
    layout = QVBoxLayout(window)
    layout.setContentsMargins(30, 24, 30, 24)
    layout.setSpacing(20)
    
    # Title
    title = QLabel("Select Ollama Model")
    title.setStyleSheet("""
        color: white;
        font-size: 16pt;
        font-weight: bold;
        padding-bottom: 4px;
    """)
    layout.addWidget(title)
    
    # Model selection with refresh button
    model_label_layout = QHBoxLayout()
    model_label_layout.setSpacing(8)
    model_label = QLabel("Vision Model:")
    model_label.setStyleSheet("""
        color: rgba(200, 200, 200, 255);
        font-size: 10pt;
        font-weight: 500;
    """)
    model_label_layout.addWidget(model_label)
    model_label_layout.addStretch()
    
    # Refresh button
    refresh_btn = QPushButton("↻")
    refresh_btn.setFixedSize(36, 36)
    refresh_btn.setStyleSheet("""
        QPushButton {
            background-color: rgba(70, 70, 70, 255);
            color: white;
            border: 1px solid rgba(90, 90, 90, 255);
            border-radius: 8px;
            font-size: 16pt;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: rgba(85, 85, 85, 255);
            border-color: rgba(74, 158, 255, 255);
        }
        QPushButton:pressed {
            background-color: rgba(60, 60, 60, 255);
        }
    """)
    refresh_btn.setCursor(Qt.PointingHandCursor)
    model_label_layout.addWidget(refresh_btn)
    layout.addLayout(model_label_layout)
    
    model_combo = QComboBox()
    model_combo.addItems(vision_models)
    # Try to set current model to last used model
    last_model = get_last_model()
    index = model_combo.findText(last_model)
    if index >= 0:
        model_combo.setCurrentIndex(index)
    else:
        model_combo.setCurrentIndex(0)
    model_combo.setFixedHeight(48)  # Fixed height
    model_combo.setStyleSheet("""
        QComboBox {
            background-color: rgba(50, 50, 50, 255);
            color: white;
            border: 1px solid rgba(70, 70, 70, 255);
            border-radius: 10px;
            padding: 12px 16px;
            font-size: 11pt;
        }
        QComboBox:hover {
            border-color: rgba(74, 158, 255, 255);
            background-color: rgba(55, 55, 55, 255);
        }
        QComboBox::drop-down {
            border: none;
            width: 30px;
        }
        QComboBox::down-arrow {
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid rgba(200, 200, 200, 255);
            width: 0;
            height: 0;
        }
        QComboBox QAbstractItemView {
            background-color: rgba(45, 45, 45, 255);
            color: white;
            selection-background-color: rgba(74, 158, 255, 255);
            selection-color: white;
            border: 1px solid rgba(70, 70, 70, 255);
            border-radius: 10px;
            padding: 6px;
        }
        QComboBox QAbstractItemView::item {
            min-height: 36px;
            padding: 10px 12px;
            border-radius: 6px;
        }
        QComboBox QAbstractItemView::item:hover {
            background-color: rgba(65, 65, 65, 255);
        }
        QComboBox QAbstractItemView::item:selected {
            background-color: rgba(74, 158, 255, 255);
            color: white;
        }
    """)
    layout.addWidget(model_combo)
    
    # Refresh button handler
    def on_refresh():
        """Fetch new models from API and update combo box"""
        refresh_btn.setEnabled(False)
        refresh_btn.setText("...")
        app.processEvents()  # Update UI
        
        try:
            new_models = get_vision_models()
            if new_models:
                current_text = model_combo.currentText()
                model_combo.clear()
                model_combo.addItems(new_models)
                # Try to restore previous selection
                index = model_combo.findText(current_text)
                if index >= 0:
                    model_combo.setCurrentIndex(index)
                else:
                    model_combo.setCurrentIndex(0)
        except Exception as e:
            print(f"Error refreshing models: {e}")
        finally:
            refresh_btn.setText("↻")
            refresh_btn.setEnabled(True)
    
    refresh_btn.clicked.connect(on_refresh)
    
    # Add spacing before custom model section
    layout.addSpacing(8)
    
    # Custom model entry
    custom_label = QLabel("Or enter custom model:")
    custom_label.setStyleSheet("""
        color: rgba(200, 200, 200, 255);
        font-size: 10pt;
        font-weight: 500;
    """)
    layout.addWidget(custom_label)
    
    custom_entry = QLineEdit()
    custom_entry.setFixedHeight(48)  # Same height as combo box
    custom_entry.setStyleSheet("""
        QLineEdit {
            background-color: rgba(50, 50, 50, 255);
            color: white;
            border: 1px solid rgba(70, 70, 70, 255);
            border-radius: 10px;
            padding: 12px 16px;
            font-size: 11pt;
        }
        QLineEdit:hover {
            border-color: rgba(90, 90, 90, 255);
            background-color: rgba(55, 55, 55, 255);
        }
        QLineEdit:focus {
            border-color: rgba(74, 158, 255, 255);
            background-color: rgba(55, 55, 55, 255);
        }
    """)
    layout.addWidget(custom_entry)
    
    # Add spacing before buttons
    layout.addSpacing(12)
    
    # Buttons
    button_layout = QHBoxLayout()
    button_layout.setSpacing(12)
    button_layout.addStretch()
    
    cancel_btn = GlassyButton("Cancel")
    cancel_btn.setFixedSize(110, 42)
    
    continue_btn = GlassyButton("Continue")
    continue_btn.setFixedSize(110, 42)
    
    def on_ok():
        custom_model = custom_entry.text().strip()
        if custom_model:
            selected_model['value'] = custom_model
        else:
            selected_model['value'] = model_combo.currentText()
        dialog_closed['value'] = True
        window.close()
    
    def on_cancel():
        dialog_closed['value'] = False
        window.close()
    
    continue_btn.clicked.connect(on_ok)
    cancel_btn.clicked.connect(on_cancel)
    
    button_layout.addWidget(cancel_btn)
    button_layout.addWidget(continue_btn)
    layout.addLayout(button_layout)
    
    # Show window
    window.show()
    custom_entry.setFocus()
    app.exec()
    
    if not dialog_closed['value']:
        return None
    
    return selected_model['value']


def select_model_tkinter(vision_models):
    """Fallback tkinter version"""
    selected_model = {'value': vision_models[0]}
    dialog_closed = {'value': False}
    
    root = tk.Tk()
    root.title("Neocr - Select Model")
    root.resizable(False, False)
    
    # Modern color scheme
    bg_color = '#2b2b2b'  # Dark gray background
    fg_color = '#ffffff'  # White text
    accent_color = '#4a9eff'  # Blue accent
    entry_bg = '#3c3c3c'  # Darker gray for entries
    button_bg = '#4a9eff'  # Blue buttons
    button_hover = '#5aaeff'  # Lighter blue on hover
    border_color = '#555555'  # Border color
    
    root.configure(bg=bg_color)
    
    # Center the window
    root.update_idletasks()
    width = 480
    height = 260  # Increased height to ensure buttons are visible
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'{width}x{height}+{x}+{y}')
    
    # Detect best font for the system
    try:
        # Try modern fonts in order of preference
        test_font = tk.Font(family='Segoe UI', size=10)
        font_family = 'Segoe UI'
    except:
        try:
            test_font = tk.Font(family='Ubuntu', size=10)
            font_family = 'Ubuntu'
        except:
            try:
                test_font = tk.Font(family='Roboto', size=10)
                font_family = 'Roboto'
            except:
                font_family = 'Helvetica'  # Fallback
    
    # Configure modern styles
    style = ttk.Style()
    style.theme_use('clam')
    
    # Configure styles
    style.configure('Title.TLabel', 
                   background=bg_color, 
                   foreground=fg_color,
                   font=(font_family, 14, 'bold'),
                   padding=(0, 0, 0, 10))
    
    style.configure('Modern.TLabel',
                   background=bg_color,
                   foreground=fg_color,
                   font=(font_family, 10))
    
    style.configure('Modern.TCombobox',
                   fieldbackground=entry_bg,
                   background=entry_bg,
                   foreground=fg_color,
                   borderwidth=1,
                   relief='solid',
                   padding=(8, 12))  # Increased vertical padding for more height
    
    style.map('Modern.TCombobox',
             fieldbackground=[('readonly', entry_bg)],
             selectbackground=[('readonly', accent_color)])
    
    style.configure('Modern.TEntry',
                   fieldbackground=entry_bg,
                   foreground=fg_color,
                   borderwidth=1,
                   relief='solid',
                   padding=8,
                   insertcolor=fg_color)
    
    style.configure('Modern.TButton',
                   background=button_bg,
                   foreground='white',
                   borderwidth=0,
                   padding=(20, 10),
                   font=(font_family, 10, 'bold'))
    
    style.map('Modern.TButton',
             background=[('active', button_hover), ('pressed', '#3a8eef')])
    
    style.configure('Cancel.TButton',
                   background='#555555',
                   foreground='white',
                   borderwidth=0,
                   padding=(20, 10),
                   font=(font_family, 10))
    
    style.map('Cancel.TButton',
             background=[('active', '#666666'), ('pressed', '#444444')])
    
    # Main frame with padding
    main_frame = tk.Frame(root, bg=bg_color, padx=24, pady=20)
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Title
    title_label = ttk.Label(main_frame, text="Select Ollama Model", style='Title.TLabel')
    title_label.pack(anchor=tk.W, pady=(0, 20))
    
    # Model selection section with refresh button
    model_label_frame = tk.Frame(main_frame, bg=bg_color)
    model_label_frame.pack(fill=tk.X, pady=(0, 8))
    
    model_label = ttk.Label(model_label_frame, text="Vision Model:", style='Modern.TLabel')
    model_label.pack(side=tk.LEFT)
    
    # Refresh button
    refresh_btn = tk.Button(model_label_frame, text="↻", 
                           bg='#555555', fg='white', font=(font_family, 12, 'bold'),
                           borderwidth=0, padx=8, pady=4, width=3,
                           activebackground='#666666', activeforeground='white',
                           cursor='hand2', relief='flat')
    refresh_btn.pack(side=tk.RIGHT)
    
    # Model selection combobox
    model_var = tk.StringVar()
    # Try to set to last used model
    last_model = get_last_model()
    if last_model in vision_models:
        model_var.set(last_model)
    elif vision_models:
        model_var.set(vision_models[0])
    model_combo = ttk.Combobox(main_frame, textvariable=model_var, values=vision_models, 
                               width=45, state='readonly', style='Modern.TCombobox',
                               font=(font_family, 10))
    model_combo.pack(fill=tk.X, pady=(0, 16), ipady=6)  # Added internal padding for more height
    
    # Refresh button handler
    def on_refresh():
        """Fetch new models from API and update combo box"""
        refresh_btn.config(state='disabled', text='...')
        root.update()
        
        try:
            new_models = get_vision_models()
            if new_models:
                current_text = model_var.get()
                model_var.set('')
                model_combo.config(values=new_models)
                # Try to restore previous selection
                if current_text in new_models:
                    model_var.set(current_text)
                elif new_models:
                    model_var.set(new_models[0])
        except Exception as e:
            print(f"Error refreshing models: {e}")
        finally:
            refresh_btn.config(state='normal', text='↻')
    
    refresh_btn.config(command=on_refresh)
    
    # Custom model entry section
    custom_label = ttk.Label(main_frame, text="Or enter custom model:", style='Modern.TLabel')
    custom_label.pack(anchor=tk.W, pady=(0, 8))
    
    custom_var = tk.StringVar()
    custom_entry = ttk.Entry(main_frame, textvariable=custom_var, width=45,
                            style='Modern.TEntry', font=(font_family, 10))
    custom_entry.pack(fill=tk.X, pady=(0, 20))
    
    # Buttons frame
    button_frame = tk.Frame(main_frame, bg=bg_color)
    button_frame.pack(fill=tk.X)
    
    def on_ok():
        # Use custom model if provided, otherwise use selected model
        custom_model = custom_var.get().strip()
        if custom_model:
            selected_model['value'] = custom_model
        else:
            selected_model['value'] = model_var.get()
        dialog_closed['value'] = True
        root.quit()
        root.destroy()
    
    def on_cancel():
        print("Escape pressed!")  # Debug message
        dialog_closed['value'] = False
        root.quit()
        root.destroy()
    
    # Buttons with spacing - using tk.Button for better visibility
    cancel_btn = tk.Button(button_frame, text="Cancel", command=on_cancel,
                          bg='#555555', fg='white', font=(font_family, 10),
                          borderwidth=0, padx=20, pady=10,
                          activebackground='#666666', activeforeground='white',
                          cursor='hand2')
    cancel_btn.pack(side=tk.RIGHT, padx=(10, 0))
    
    ok_btn = tk.Button(button_frame, text="Continue", command=on_ok,
                       bg=button_bg, fg='white', font=(font_family, 10, 'bold'),
                       borderwidth=0, padx=20, pady=10,
                       activebackground=button_hover, activeforeground='white',
                       cursor='hand2')
    ok_btn.pack(side=tk.RIGHT)
    
    # Bind Enter key to OK button
    root.bind('<Return>', lambda e: on_ok())
    root.bind('<Escape>', lambda e: on_cancel())
    
    # Focus on the window
    root.focus_force()
    custom_entry.focus()
    
    root.mainloop()
    
    if not dialog_closed['value']:
        return None
    
    return selected_model['value']


def select_region(model_name, on_model_change_callback=None):
    """Create a full-screen overlay for region selection"""
    # First, take a screenshot of the entire screen
    print("Capturing screen...")
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # Primary monitor
        screenshot = sct.grab(monitor)
        
        # Get screen dimensions from the screenshot
        screen_width = screenshot.width
        screen_height = screenshot.height
        
        # Save screenshot temporarily
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            screenshot_path = tmp_file.name
            mss.tools.to_png(screenshot.rgb, screenshot.size, output=screenshot_path)
    
    # Create the selection window
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes('-topmost', True)
    root.configure(bg='black')
    
    # Explicitly set window geometry to full screen
    # Try without fullscreen first to see if keyboard events work better
    root.geometry(f'{screen_width}x{screen_height}+0+0')
    # On Linux, try 'zoomed' first, fallback to fullscreen if needed
    try:
        root.state('zoomed')  # Maximized instead of fullscreen for better keyboard capture
    except:
        # If zoomed doesn't work, use fullscreen
        root.attributes('-fullscreen', True)
    
    # Force update to ensure window is properly sized
    root.update_idletasks()
    
    # Load and display the screenshot
    img = Image.open(screenshot_path)
    photo = ImageTk.PhotoImage(img)
    
    canvas = tk.Canvas(root, highlightthickness=0, bg='black', cursor='crosshair', 
                       width=screen_width, height=screen_height)
    canvas.pack(fill=tk.BOTH, expand=True)
    canvas.create_image(0, 0, anchor=tk.NW, image=photo)
    
    # Add a semi-transparent overlay
    overlay = canvas.create_rectangle(0, 0, screen_width, screen_height, 
                                      fill='black', stipple='gray25', outline='')
    canvas.tag_lower(overlay)  # Put overlay behind the image
    
    start_x = start_y = 0
    rect_id = None
    selected_region = {'x': 0, 'y': 0, 'width': 0, 'height': 0}
    selection_complete = False
    escape_pressed = False
    
    def on_button_press(event):
        nonlocal start_x, start_y, rect_id
        start_x = event.x
        start_y = event.y
        if rect_id:
            canvas.delete(rect_id)
        rect_id = canvas.create_rectangle(
            start_x, start_y, start_x, start_y,
            outline='#2dd4bf', width=3, fill='', tags='selection'
        )
        canvas.tag_raise(rect_id)  # Make sure selection rectangle is on top
    
    def on_move_press(event):
        nonlocal rect_id
        if rect_id:
            canvas.coords(rect_id, start_x, start_y, event.x, event.y)
    
    def on_button_release(event):
        nonlocal selected_region, selection_complete
        end_x = event.x
        end_y = event.y
        
        # Calculate region coordinates (normalize to ensure positive width/height)
        x1 = min(start_x, end_x)
        y1 = min(start_y, end_y)
        x2 = max(start_x, end_x)
        y2 = max(start_y, end_y)
        
        # Only accept selection if it has minimum size
        if abs(x2 - x1) > 10 and abs(y2 - y1) > 10:
            selected_region = {
                'x': x1,
                'y': y1,
                'width': x2 - x1,
                'height': y2 - y1
            }
            selection_complete = True
            root.quit()
            root.destroy()
    
    def on_escape(event=None):
        nonlocal selection_complete, screenshot_path, escape_pressed
        if escape_pressed:  # Already handled
            return "break"
        print("Escape pressed!")  # Debug message
        escape_pressed = True
        selection_complete = False
        # Stop keyboard listener if it exists
        if hasattr(root, '_keyboard_listener') and root._keyboard_listener:
            try:
                root._keyboard_listener.stop()
            except:
                pass
        # Clean up Qt widget if it exists
        if hasattr(root, '_buttons_widget') and root._buttons_widget:
            root._buttons_widget.close()
            root._buttons_widget = None
        # Clean up screenshot file
        try:
            if os.path.exists(screenshot_path):
                os.unlink(screenshot_path)
        except Exception:
            pass
        root.quit()
        root.destroy()
        return "break"  # Prevent event propagation
    
    # Add "Change Model" and "Cancel" buttons in center bottom with 10% margin
    button_text = f"Change Model (current: {model_name})"
    cancel_text = "Cancel"
    # Calculate button widths
    change_model_width = max(250, len(button_text) * 7)
    cancel_width = 120
    button_spacing = 10
    button_height = 40
    total_width = change_model_width + cancel_width + button_spacing
    margin_bottom = int(screen_height * 0.10)  # 10% margin from bottom
    x_position = (screen_width - total_width) // 2  # Center horizontally
    y_position = screen_height - margin_bottom - button_height  # 10% from bottom
    
    # Use PySide6 glassy button - create as floating widget
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # Create a simple widget container with transparent background for both buttons
    buttons_widget = QWidget()
    buttons_widget.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.X11BypassWindowManagerHint)
    buttons_widget.setAttribute(Qt.WA_TranslucentBackground, True)
    buttons_widget.setStyleSheet("background-color: transparent;")
    buttons_widget.setFixedSize(total_width, button_height)
    buttons_widget.move(x_position, y_position)
    
    # Layout for the buttons
    btn_layout = QHBoxLayout(buttons_widget)
    btn_layout.setContentsMargins(0, 0, 0, 0)
    btn_layout.setSpacing(button_spacing)
    
    if on_model_change_callback:
        change_model_btn = GlassyButton(button_text, buttons_widget)
        change_model_btn.setFixedSize(change_model_width, button_height)
        change_model_btn.clicked.connect(lambda: on_model_change_callback(root))
        btn_layout.addWidget(change_model_btn)
    
    # Cancel button
    cancel_btn = GlassyButton(cancel_text, buttons_widget)
    cancel_btn.setFixedSize(cancel_width, button_height)
    cancel_btn.clicked.connect(lambda: on_escape(None))
    btn_layout.addWidget(cancel_btn)
    
    buttons_widget.show()
    buttons_widget.raise_()  # Ensure it's on top
    buttons_widget.activateWindow()  # Activate the window
    app.processEvents()  # Process events immediately to show the widget
    
    # Keep reference to prevent garbage collection
    root._buttons_widget = buttons_widget
    root._qt_app = app
    
    # Process Qt events periodically while tkinter is running
    def process_qt_events():
        if hasattr(root, '_buttons_widget') and root._buttons_widget:
            app.processEvents()
        root.after(10, process_qt_events)  # Process every 10ms
    
    process_qt_events()  # Start processing Qt events
    
    def check_escape_periodically():
        """Periodically check if we should exit - backup method"""
        if escape_pressed:
            return
        # This is a backup - the bind should work, but this ensures we can exit
        root.after(100, check_escape_periodically)
    
    # System-level keyboard listener for Escape (works even without window focus)
    def on_key_release(key):
        try:
            if key == keyboard.Key.esc:
                root.after(0, on_escape)  # Schedule on main thread
        except AttributeError:
            pass
    
    keyboard_listener = keyboard.Listener(on_release=on_key_release)
    keyboard_listener.start()
    
    # Bind events - use bind_all to capture Escape globally
    canvas.bind('<Button-1>', on_button_press)
    canvas.bind('<B1-Motion>', on_move_press)
    canvas.bind('<ButtonRelease-1>', on_button_release)
    
    # Try multiple ways to bind Escape - use bind_all for global capture
    root.bind_all('<KeyPress-Escape>', on_escape, add='+')
    root.bind_all('<Escape>', on_escape, add='+')
    root.bind('<KeyPress-Escape>', on_escape, add='+')
    root.bind('<Escape>', on_escape, add='+')
    canvas.bind('<KeyPress-Escape>', on_escape, add='+')
    canvas.bind('<Escape>', on_escape, add='+')
    
    # Also bind to Key events and check keycode
    def on_key_press(event):
        if event.keysym == 'Escape' or event.keycode == 9:  # Escape key code
            on_escape(event)
    
    root.bind_all('<Key>', on_key_press, add='+')
    canvas.bind('<Key>', on_key_press, add='+')
    
    # Force focus and make sure window can receive keyboard events
    root.focus_force()
    root.focus_set()
    canvas.focus_set()
    canvas.focus_force()
    
    # Grab all keyboard and mouse events to ensure we capture Escape
    try:
        root.grab_set()  # Grab all events to this window
    except:
        pass
    
    # Start periodic check as backup
    check_escape_periodically()
    
    # Store keyboard listener for cleanup
    root._keyboard_listener = keyboard_listener
    
    print("Click and drag to select a region (Press ESC to cancel)...")
    root.mainloop()
    
    # If escape was pressed, exit immediately
    if escape_pressed:
        sys.exit(0)
    
    # Clean up screenshot file if selection was completed
    if selection_complete:
        try:
            if os.path.exists(screenshot_path):
                os.unlink(screenshot_path)
        except Exception:
            pass
    
    return selected_region if selection_complete else None


def send_notification(text):
    """Send a desktop notification using notify-send (dunst)"""
    # Truncate text if too long for notification
    max_length = 200
    display_text = text[:max_length] + "..." if len(text) > max_length else text
    
    try:
        subprocess.run(
            ['notify-send', 'Neocr: text captured', display_text],
            check=True,
            timeout=5
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        # Silently fail if notify-send is not available
        pass


def main():
    """Main entry point for neocr"""
    # Get last used model or default
    model_name = get_last_model()
    print(f"Using model: {model_name}")
    
    # Model change callback for the region selection window
    def create_change_model_callback():
        """Create a callback function that can change the model"""
        def change_model_callback(region_window):
            """Callback to change model from region selection window"""
            region_window.destroy()
            new_model = select_model()
            if new_model:
                # Save the new model immediately
                save_last_model(new_model)
                print(f"Changed to model: {new_model}")
                # Restart with new model
                main()
            else:
                # User cancelled, exit
                sys.exit(0)
        return change_model_callback
    
    # Start with the last model
    main_with_model(model_name, create_change_model_callback())


def main_with_model(model_name, on_model_change_callback=None):
    """Main processing with a specific model"""
    # Get screen region from user
    region = select_region(model_name, on_model_change_callback)
    
    if region is None:
        print("Selection cancelled.")
        sys.exit(0)
    
    # Take a screenshot of the selected region
    print(f"Capturing region: x={region['x']}, y={region['y']}, width={region['width']}, height={region['height']}")
    with mss.mss() as sct:
        # Capture the selected region
        monitor = {
            "top": region['y'],
            "left": region['x'],
            "width": region['width'],
            "height": region['height']
        }
        screenshot = sct.grab(monitor)
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            tmp_path = tmp_file.name
            mss.tools.to_png(screenshot.rgb, screenshot.size, output=tmp_path)
        
        print(f"Screenshot saved to: {tmp_path}")
    
    # Initialize OCR processor with selected model
    print(f"Initializing OCR processor with model: {model_name}...")
    ocr = OCRProcessor(model_name=model_name)
    
    # Process the screenshot with OCR
    print("Processing image with OCR...")
    result = ocr.process_image(
        image_path=tmp_path,
        format_type="markdown",
        custom_prompt="Extract the exact text in the image and output only the text.",
        language="English"
    )
    
    # Copy result to clipboard
    print("Copying result to clipboard...")
    pyperclip.copy(result)
    
    # Save the model as last used
    save_last_model(model_name)
    
    # Send desktop notification
    send_notification(result)
    
    # Clean up temporary file
    os.unlink(tmp_path)
    
    print("\n" + "="*50)
    print("OCR Result (also copied to clipboard):")
    print("="*50)
    print(result)


if __name__ == '__main__':
    main()

