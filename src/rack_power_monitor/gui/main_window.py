import tkinter as tk
from tkinter import ttk, messagebox
import sys
import logging
import os
import importlib

# Determine if we're running as a packaged app
is_packaged = getattr(sys, 'frozen', False)

# Setup paths based on environment
if is_packaged:
    # We're running as a packaged executable
    base_dir = os.path.dirname(sys.executable)
    
    # In packaged mode, all imports should be non-src based
    try:
        from rack_power_monitor.gui.monitor_tab import MonitorTab
        from rack_power_monitor.gui.analyze_tab import AnalyzeTab
        from rack_power_monitor.gui.settings_tab import SettingsTab
        from rack_power_monitor.utils.config_manager import ConfigManager
        
        # Try importing web_server directly
        try:
            from rack_power_monitor.gui.web_server import WebMonitorServer
        except ImportError:
            # Fallback to local import
            web_server_path = os.path.join(os.path.dirname(__file__), 'web_server.py')
            if os.path.exists(web_server_path):
                spec = importlib.util.spec_from_file_location("web_server", web_server_path)
                web_server = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(web_server)
                WebMonitorServer = web_server.WebMonitorServer
            else:
                WebMonitorServer = None
                logging.warning("WebMonitorServer not available")
                
    except ImportError as e:
        logging.error(f"Import error in packaged mode: {e}")
        raise

else:
    # We're in development mode
    # Add the src directory to the path for development imports
    current_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
        
    # Now import using the src prefixes for development
    from src.rack_power_monitor.gui.monitor_tab import MonitorTab
    from src.rack_power_monitor.gui.analyze_tab import AnalyzeTab
    from src.rack_power_monitor.gui.settings_tab import SettingsTab
    from src.rack_power_monitor.utils.config_manager import ConfigManager
    
    # Try to import web_server
    try:
        from src.rack_power_monitor.gui.web_server import WebMonitorServer
    except ImportError:
        # Fallback to direct import
        web_server_path = os.path.join(os.path.dirname(__file__), 'web_server.py')
        if os.path.exists(web_server_path):
            spec = importlib.util.spec_from_file_location("web_server", web_server_path)
            web_server = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(web_server)
            WebMonitorServer = web_server.WebMonitorServer
        else:
            WebMonitorServer = None
            logging.warning("WebMonitorServer not available")

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

class PowerMonitorApp:
    def __init__(self, root):
        """Initialize the Power Monitor GUI application."""
        self.root = root
        root.title("Server Rack Power Monitoring")
        root.geometry("1200x800")
        root.protocol("WM_DELETE_WINDOW", self.on_close)  # Handle window close button
        
        # Status variable - must be defined before creating tabs
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        
        # Set application icon
        try:
            icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
                                    "resources", "icons", "power_icon.ico")
            if os.path.exists(icon_path):
                root.iconbitmap(icon_path)
        except Exception as e:
            logger.warning(f"Failed to load icon: {e}")
        
        # Get the path to the config file
        config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config")
        config_file = os.path.join(config_dir, "default_settings.json")
        
        # Ensure config directory exists
        os.makedirs(config_dir, exist_ok=True)
        
        # Load configuration
        self.config_manager = ConfigManager(config_file=config_file)
        self.config = self.config_manager.load_settings()
        
        # Create and set up the main frame
        self.main_frame = ttk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create a toolbar (now without the exit button)
        toolbar = ttk.Frame(self.main_frame)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        
        # Create a notebook (tabs)
        self.notebook = ttk.Notebook(self.main_frame)
        
        # Initialize tabs
        try:
            self.monitor_tab = MonitorTab(self.notebook, self)
            self.notebook.add(self.monitor_tab, text="Monitor")
        except Exception as e:
            logger.error(f"Failed to load Monitor tab: {e}")
            messagebox.showerror("Error", f"Failed to load Monitor tab: {e}")
        
        # Create remaining tabs if available
        try:
            self.analyze_tab = AnalyzeTab(self.notebook, self)
            self.notebook.add(self.analyze_tab, text="Analyze")
        except Exception as e:
            logger.error(f"Failed to load Analyze tab: {e}")
        
        try:
            self.settings_tab = SettingsTab(self.notebook, self)
            self.notebook.add(self.settings_tab, text="Settings")
        except Exception as e:
            logger.error(f"Failed to load Settings tab: {e}")
        
        # Pack notebook
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Status bar at bottom
        self.status_bar = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Initialize web server
        self.web_server = None
        self.web_server_enabled = tk.BooleanVar(value=False)
        
        # Set up the web server controls in the settings tab
        self._setup_web_server_settings()

        # Initialize UI components
        self._init_ui()

    def _init_ui(self):
        """Initialize additional UI components."""
        # Create menu bar
        menu_bar = tk.Menu(self.root)
        self.root.config(menu=menu_bar)

        # File menu
        file_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Settings", command=lambda: self.notebook.select(self.settings_tab))
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)

        # Help menu
        help_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)
        help_menu.add_command(label="Documentation", command=self.show_documentation)

    def _setup_web_server_settings(self):
        """Set up web server settings in the Settings tab."""
        if hasattr(self, 'settings_tab'):
            # Add web server section to Settings tab
            web_frame = ttk.LabelFrame(self.settings_tab, text="Web Interface")
            web_frame.pack(fill=tk.X, padx=10, pady=10)
            
            # Enable web server
            web_server_check = ttk.Checkbutton(web_frame, text="Enable Web Interface", 
                                              variable=self.web_server_enabled,
                                              command=self._toggle_web_server)
            web_server_check.pack(anchor=tk.W, padx=10, pady=5)
            
            # Port selection
            port_frame = ttk.Frame(web_frame)
            port_frame.pack(fill=tk.X, padx=10, pady=5)
            
            ttk.Label(port_frame, text="Port:").pack(side=tk.LEFT)
            self.web_port_var = tk.IntVar(value=5000)
            port_entry = ttk.Entry(port_frame, textvariable=self.web_port_var, width=6)
            port_entry.pack(side=tk.LEFT, padx=5)
            
            # Open in browser button
            ttk.Button(web_frame, text="Open in Browser", 
                      command=self._open_web_interface).pack(pady=5)
        
    def _toggle_web_server(self):
        """Toggle the web server on/off."""
        if self.web_server_enabled.get():
            # Start web server
            if not self.web_server:
                self.web_server = WebMonitorServer(self, port=self.web_port_var.get())
            self.web_server.start()
            logging.info(f"Web server started on port {self.web_port_var.get()}")
        else:
            # Stop web server
            if self.web_server:
                self.web_server.stop()
                logging.info("Web server stopped")
    
    def _open_web_interface(self):
        """Open the web interface in a browser."""
        if self.web_server and self.web_server.is_running:
            self.web_server.open_browser()
        else:
            messagebox.showinfo("Web Server", "Web server is not running. Enable it first.")

    def show_about(self):
        """Show application about dialog."""
        messagebox.showinfo(
            "About Rack Power Monitor",
            "Rack Power Monitor v1.01\n\n"
            "A tool for monitoring power usage of rack servers.\n\n"
            "© 2025 Microsoft Corporation\n"
            "All rights reserved.")
            

    def show_documentation(self):
        """Show application documentation."""
        messagebox.showinfo(
            "Documentation",
            "Documentation is available in the docs folder.\n\n"
            "For help, please see the README.md file."
        )

    def set_status(self, message):
        """Update the status bar message."""
        self.status_var.set(message)

    def on_closing(self):
        """Handle window closing."""
        # Stop web server if running
        if self.web_server and self.web_server.is_running:
            self.web_server.stop()
        
        try:
            if hasattr(self, 'monitor_tab') and hasattr(self.monitor_tab, 'is_monitoring_active') and self.monitor_tab.is_monitoring_active():
                if messagebox.askyesno("Confirm Exit", "Monitoring is in progress. Stop monitoring and exit?"):
                    self.monitor_tab.stop_monitoring()
                    self.root.destroy()
            else:
                self.root.destroy()
        except Exception as e:
            logger.error(f"Error during application close: {e}")
            self.root.destroy()

    def on_close(self):
        """Handle window close event properly."""
        try:
            # Stop any ongoing monitoring
            if hasattr(self, 'monitor_tab'):
                if hasattr(self.monitor_tab, 'monitoring_active') and self.monitor_tab.monitoring_active:
                    self.monitor_tab._stop_monitoring()
                
                # Stop the async event loop if it exists
                if hasattr(self.monitor_tab, 'async_loop') and self.monitor_tab.async_loop:
                    self.monitor_tab.async_loop.stop()
            
            # Stop web server if running
            if self.web_server and self.web_server.is_running:
                self.web_server.stop()
            
            # Save any pending settings
            if hasattr(self, 'settings_tab'):
                # Save current settings without showing dialog
                try:
                    self.config_manager.save_settings(self.config)
                except:
                    pass  # Ignore errors during exit
            
            # Destroy the main window
            self.root.destroy()
            
            # Force exit the application
            import sys
            sys.exit(0)
            
        except Exception as e:
            print(f"Error during application shutdown: {e}")
            # Force exit in case of error
            import os
            os._exit(1)
            
def main():
    try:
        root = tk.Tk()
        app = PowerMonitorApp(root)
        root.mainloop()
    except Exception as e:
        print(f"Startup error: {e}")
        logger.critical(f"Application failed to start: {e}")
        # Show error in a messagebox for better visibility
        import tkinter.messagebox as mb
        mb.showerror("Startup Error", f"Application failed to start: {e}")
        raise

# At the end of your main_window.py file
if __name__ == "__main__":
    # Setup proper path for frozen executable
    if getattr(sys, 'frozen', False):
        # Running from frozen executable
        application_path = os.path.dirname(sys.executable)
        os.chdir(application_path)  # Change to executable directory
        
    # Your existing code to run the application
    root = tk.Tk()
    app = PowerMonitorApp(root)
    root.mainloop()