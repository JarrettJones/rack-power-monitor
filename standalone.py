"""
Standalone version of Rack Power Monitor
This file imports directly from the source files without relying on package structure
"""
import sys
import os
import tkinter as tk
from tkinter import ttk, messagebox
import logging
import importlib.util

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("power_monitor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("power_monitor")

# Determine paths
is_packaged = getattr(sys, 'frozen', False)
if is_packaged:
    # We're running from a PyInstaller bundle
    base_dir = os.path.dirname(sys.executable)
    
    # Add the src directory to Python's path
    src_dir = os.path.join(base_dir, 'src')
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    
    # Debug info
    logger.info(f"Python path: {sys.path}")
    logger.info(f"Base dir: {base_dir}")
    
    # Show what files are available
    if os.path.exists(src_dir):
        logger.info(f"Contents of {src_dir}: {os.listdir(src_dir)}")
        rack_power_dir = os.path.join(src_dir, 'rack_power_monitor')
        if os.path.exists(rack_power_dir):
            logger.info(f"Contents of {rack_power_dir}: {os.listdir(rack_power_dir)}")
            gui_dir = os.path.join(rack_power_dir, 'gui')
            if os.path.exists(gui_dir):
                logger.info(f"Contents of {gui_dir}: {os.listdir(gui_dir)}")
    else:
        logger.warning(f"src directory not found: {src_dir}")
else:
    # We're running in development
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Add the base directory to Python's path
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)

# Import modules
try:
    # Try direct imports first
    try:
        if is_packaged:
            # Try packaged imports first
            from src.rack_power_monitor.gui.monitor_tab import MonitorTab
            from src.rack_power_monitor.gui.analyze_tab import AnalyzeTab
            from src.rack_power_monitor.gui.settings_tab import SettingsTab
            from src.rack_power_monitor.utils.config_manager import ConfigManager
            try:
                from src.rack_power_monitor.gui.web_server import WebMonitorServer
            except ImportError:
                WebMonitorServer = None
        else:
            # In development
            from src.rack_power_monitor.gui.monitor_tab import MonitorTab
            from src.rack_power_monitor.gui.analyze_tab import AnalyzeTab
            from src.rack_power_monitor.gui.settings_tab import SettingsTab
            from src.rack_power_monitor.utils.config_manager import ConfigManager
            try:
                from src.rack_power_monitor.gui.web_server import WebMonitorServer
            except ImportError:
                WebMonitorServer = None
    except ImportError as e:
        logger.warning(f"Standard imports failed, trying direct file imports: {e}")
        # Fallback to direct file imports
        
        # Debug what's happening
        logger.info(f"Current dir: {os.getcwd()}")
        
        # Build paths based on whether we're packaged
        if is_packaged:
            base_path = base_dir
        else:
            base_path = base_dir
            
        monitor_tab_path = os.path.join(base_path, "src", "rack_power_monitor", "gui", "monitor_tab.py")
        analyze_tab_path = os.path.join(base_path, "src", "rack_power_monitor", "gui", "analyze_tab.py")
        settings_tab_path = os.path.join(base_path, "src", "rack_power_monitor", "gui", "settings_tab.py")
        config_manager_path = os.path.join(base_path, "src", "rack_power_monitor", "utils", "config_manager.py")
        web_server_path = os.path.join(base_path, "src", "rack_power_monitor", "gui", "web_server.py")
        
        # Log the paths we're trying
        logger.info(f"Trying to load from: {monitor_tab_path}")
        
        def import_module_from_path(module_name, file_path):
            if os.path.exists(file_path):
                logger.info(f"Found file: {file_path}")
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                module = importlib.util.module_from_spec(spec)
                try:
                    spec.loader.exec_module(module)
                    return module
                except Exception as e:
                    logger.error(f"Failed to load {module_name} from {file_path}: {e}")
            else:
                logger.error(f"Module file not found: {file_path}")
            return None
            
        monitor_tab_module = import_module_from_path("monitor_tab", monitor_tab_path)
        analyze_tab_module = import_module_from_path("analyze_tab", analyze_tab_path)
        settings_tab_module = import_module_from_path("settings_tab", settings_tab_path)
        config_manager_module = import_module_from_path("config_manager", config_manager_path)
        web_server_module = import_module_from_path("web_server", web_server_path)
        
        if monitor_tab_module:
            MonitorTab = monitor_tab_module.MonitorTab
        else:
            raise ImportError("Failed to import MonitorTab")
            
        if analyze_tab_module:
            AnalyzeTab = analyze_tab_module.AnalyzeTab
        else:
            raise ImportError("Failed to import AnalyzeTab")
            
        if settings_tab_module:
            SettingsTab = settings_tab_module.SettingsTab
        else:
            raise ImportError("Failed to import SettingsTab")
            
        if config_manager_module:
            ConfigManager = config_manager_module.ConfigManager
        else:
            raise ImportError("Failed to import ConfigManager")
            
        if web_server_module:
            WebMonitorServer = web_server_module.WebMonitorServer
        else:
            WebMonitorServer = None
            logger.warning("WebMonitorServer not available")
            
except Exception as e:
    logger.error(f"Error importing modules: {e}")
    messagebox.showerror("Import Error", f"Failed to import required modules: {str(e)}")
    sys.exit(1)

# Main application class
class PowerMonitorApp:
    def __init__(self, root):
        """Initialize the Power Monitor GUI application."""
        self.root = root
        root.title("Server Rack Power Monitoring")
        root.geometry("1200x800")
        
        # Add your PowerMonitorApp implementation here
        ttk.Label(root, text="Power Monitor App").pack(pady=20)
        
        # Create tabs
        notebook = ttk.Notebook(root)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Initialize components
        self.config_manager = ConfigManager()
        
        # Create and add tabs
        self.monitor_tab = MonitorTab(notebook, self.config_manager)
        self.analyze_tab = AnalyzeTab(notebook, self.config_manager)
        self.settings_tab = SettingsTab(notebook, self.config_manager)
        
        notebook.add(self.monitor_tab, text="Monitor")
        notebook.add(self.analyze_tab, text="Analyze")
        notebook.add(self.settings_tab, text="Settings")
        
    def on_close(self):
        """Handle closing the application."""
        self.root.destroy()

def main():
    """Main entry point for the application."""
    try:
        # Create and start the application
        root = tk.Tk()
        app = PowerMonitorApp(root)
        root.protocol("WM_DELETE_WINDOW", app.on_close)
        root.mainloop()
    except Exception as e:
        logger.critical(f"Failed to start application: {e}")
        messagebox.showerror("Error", f"Failed to start application: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()