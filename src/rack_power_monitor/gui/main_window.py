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
            
    def add_rscm(self, rack_name, ip_address, username=None, password=None, auto_monitor=True, poll_rate=60):
        """Add a new R-SCM to monitor."""
        try:
            # Get the monitoring_data from monitor_tab
            if not hasattr(self, 'monitoring_data'):
                if hasattr(self, 'monitor_tab') and hasattr(self.monitor_tab, 'rack_tabs'):
                    self.monitoring_data = self.monitor_tab.rack_tabs
                else:
                    self.monitoring_data = {}
            
            # Check if rack already exists
            if rack_name in self.monitoring_data:
                logger.error(f"Rack {rack_name} already exists")
                return False
            
            # Create new rack entry
            rack_key = f"{rack_name}_{ip_address}"
            
            # Get default credentials from config
            default_username = self.config.get('default_username', 'admin')
            default_password = self.config.get('default_password', 'admin')
            
            self.monitoring_data[rack_key] = {
                'address': ip_address,
                'username': username or default_username,
                'password': password or default_password,
                'poll_rate': poll_rate,
                'data': [],
                'status': 'Not Monitoring',
                'last_reading': None
            }
            
            # Start monitoring if auto_monitor is True and monitor_tab exists
            if auto_monitor and hasattr(self, 'monitor_tab'):
                self.start_monitoring(rack_name)
            
            # Save configuration by delegating to monitor_tab if available
            self.save_config()
            
            logger.info(f"Added new R-SCM: {rack_name} at {ip_address}")
            return True
        
        except Exception as e:
            logger.error(f"Error adding R-SCM {rack_name}: {str(e)}")
            return False

    def update_rscm(self, original_rack_name, rack_name, ip_address, username=None, password=None, poll_rate=60):
        """Update an existing R-SCM configuration via the web interface."""
        try:
            # Check if the name is changing and if the new name already exists
            if original_rack_name != rack_name:
                existing_rscms = self.config.get('rscms', [])
                for rscm in existing_rscms:
                    if rscm.get('name') == rack_name:
                        logger.error(f"Cannot rename to {rack_name}: A rack with this name already exists")
                        return False
        
            # Find the rack in config
            found_index = None
            if 'rscms' in self.config:
                for i, rscm in enumerate(self.config['rscms']):
                    if rscm.get('name') == original_rack_name:
                        found_index = i
                        break
        
            if found_index is None:
                logger.error(f"Rack {original_rack_name} not found in configuration")
                return False
        
            # Update the RSCM in config
            self.config['rscms'][found_index]['name'] = rack_name  # Update the rack name
            self.config['rscms'][found_index]['address'] = ip_address
            if username:
                self.config['rscms'][found_index]['username'] = username
            if password:
                # Should encrypt password before storing
                self.config['rscms'][found_index]['password'] = password
        
            # Update rscm_list for backward compatibility
            self.config['rscm_list'] = self.config['rscms']
        
            # Save configuration
            if hasattr(self, 'config_manager'):
                self.config_manager.save_settings(self.config)
        
            # Update in monitor tab if it exists
            if hasattr(self, 'monitor_tab'):
                for item_id in self.monitor_tab.rscm_tree.get_children():
                    item = self.monitor_tab.rscm_tree.item(item_id)
                    if item['values'][0] == original_rack_name:
                        # Update both the rack name and address
                        status = item['values'][2]
                        self.monitor_tab.rscm_tree.item(item_id, values=(rack_name, ip_address, status))
                        
                        # If we have active monitoring or tabs, we'd need to update them
                        if hasattr(self.monitor_tab, 'rack_tabs'):
                            old_key = f"{original_rack_name}_{ip_address}"
                            new_key = f"{rack_name}_{ip_address}"
                            
                            # Rename the rack tab if it exists
                            if old_key in self.monitor_tab.rack_tabs:
                                self.monitor_tab.rack_tabs[new_key] = self.monitor_tab.rack_tabs[old_key]
                                del self.monitor_tab.rack_tabs[old_key]
                                
                                # Update tab label if displayed in notebook
                                if self.monitor_tab.rack_tabs[new_key].get('added_to_notebook', False):
                                    tab = self.monitor_tab.rack_tabs[new_key]['tab']
                                    tab_index = self.monitor_tab.rack_notebook.index(tab)
                                    self.monitor_tab.rack_notebook.tab(tab_index, text=f"{rack_name}")
                        
                        # Update monitoring tasks if active
                        if hasattr(self.monitor_tab, 'monitoring_tasks'):
                            old_key = f"{original_rack_name}_{ip_address}"
                            new_key = f"{rack_name}_{ip_address}"
                            
                            if old_key in self.monitor_tab.monitoring_tasks:
                                self.monitor_tab.monitoring_tasks[new_key] = self.monitor_tab.monitoring_tasks[old_key]
                                del self.monitor_tab.monitoring_tasks[old_key]
                        
                        break
        
            logger.info(f"Updated R-SCM: {original_rack_name} -> {rack_name}")
            return True
    
        except Exception as e:
            logger.error(f"Error updating R-SCM {original_rack_name}: {str(e)}")
            return False

    def delete_rscm(self, rack_name):
        """Delete an R-SCM from monitoring."""
        try:
            # Get the monitoring_data if not already available
            if not hasattr(self, 'monitoring_data'):
                if hasattr(self, 'monitor_tab') and hasattr(self.monitor_tab, 'rack_tabs'):
                    self.monitoring_data = self.monitor_tab.rack_tabs
                else:
                    logger.error("No monitoring data available")
                    return False
            
            # Find the rack
            rack_key = None
            for key in list(self.monitoring_data.keys()):
                if key.startswith(f"{rack_name}_"):
                    rack_key = key
                    break
            
            if not rack_key:
                logger.error(f"Rack {rack_name} not found")
                return False
            
            # Stop monitoring first if active
            if self.monitoring_data[rack_key].get('status') == 'Monitoring':
                self.pause_monitoring(rack_name)
            
            # Delete the rack
            del self.monitoring_data[rack_key]
            
            # Save configuration
            self.save_config()
            
            logger.info(f"Deleted R-SCM: {rack_name}")
            return True
        
        except Exception as e:
            logger.error(f"Error deleting R-SCM {rack_name}: {str(e)}")
            return False

    def start_monitoring(self, rack_name):
        """Start monitoring for a specific rack."""
        try:
            # Get the monitoring_data if not already available
            if not hasattr(self, 'monitoring_data'):
                if hasattr(self, 'monitor_tab') and hasattr(self.monitor_tab, 'rack_tabs'):
                    self.monitoring_data = self.monitor_tab.rack_tabs
                else:
                    logger.error("No monitoring data available")
                    return False
            
            # Find the rack
            rack_key = None
            for key in self.monitoring_data:
                if key.startswith(f"{rack_name}_"):
                    rack_key = key
                    break
            
            if not rack_key:
                logger.error(f"Rack {rack_name} not found")
                return False
            
            # Start monitoring
            self.monitoring_data[rack_key]['status'] = 'Monitoring'
            
            # Delegate actual monitoring to monitor_tab if available
            if hasattr(self, 'monitor_tab') and hasattr(self.monitor_tab, 'start_monitoring_rack'):
                name, address = rack_key.split('_', 1)
                self.monitor_tab.start_monitoring_rack(name, address)
            
            logger.info(f"Started monitoring for {rack_name}")
            return True
        
        except Exception as e:
            logger.error(f"Error starting monitoring for {rack_name}: {str(e)}")
            return False

    def pause_monitoring(self, rack_name):
        """Pause monitoring for a specific rack."""
        try:
            # Get the monitoring_data if not already available
            if not hasattr(self, 'monitoring_data'):
                if hasattr(self, 'monitor_tab') and hasattr(self.monitor_tab, 'rack_tabs'):
                    self.monitoring_data = self.monitor_tab.rack_tabs
                else:
                    logger.error("No monitoring data available")
                    return False
            
            # Find the rack
            rack_key = None
            for key in self.monitoring_data:
                if key.startswith(f"{rack_name}_"):
                    rack_key = key
                    break
            
            if not rack_key:
                logger.error(f"Rack {rack_name} not found")
                return False
            
            # Pause monitoring
            self.monitoring_data[rack_key]['status'] = 'Paused'
            
            # Delegate to monitor_tab if available
            if hasattr(self, 'monitor_tab') and hasattr(self.monitor_tab, 'pause_monitoring_rack'):
                self.monitor_tab.pause_monitoring_rack(rack_key)
            
            logger.info(f"Paused monitoring for {rack_name}")
            return True
        
        except Exception as e:
            logger.error(f"Error pausing monitoring for {rack_name}: {str(e)}")
            return False

    def get_rscm_info(self, rack_name):
        """Get information about a specific R-SCM."""
        try:
            # Get the monitoring_data if not already available
            if not hasattr(self, 'monitoring_data'):
                if hasattr(self, 'monitor_tab') and hasattr(self.monitor_tab, 'rack_tabs'):
                    self.monitoring_data = self.monitor_tab.rack_tabs
                else:
                    logger.error("No monitoring data available")
                    return None
            
            # Find the rack
            rack_key = None
            for key in self.monitoring_data:
                if key.startswith(f"{rack_name}_"):
                    rack_key = key
                    break
            
            if not rack_key:
                logger.error(f"Rack {rack_name} not found")
                return None
            
            # Get rack info
            info = self.monitoring_data[rack_key].copy()
            info['name'] = rack_name
            
            # Remove sensitive or large data
            if 'password' in info:
                del info['password']
            if 'data' in info:
                del info['data']
                
            return info
            
        except Exception as e:
            logger.error(f"Error getting info for {rack_name}: {str(e)}")
            return None

    def get_all_racks(self):
        """Get a list of all racks for the management interface."""
        all_racks = []
        
        logger.info("============ DEBUG: get_all_racks called ============")

        try:
            # Use the config as the source of truth for which racks exist
            if 'rscms' in self.config:
                for rscm in self.config['rscms']:
                    rack_name = rscm.get('name')
                    address = rscm.get('address')
                    
                    if rack_name and address:
                        rack_key = f"{rack_name}_{address}"
                        logger.info(f"DEBUG: Processing rack: {rack_name} with key {rack_key}")
                        
                        # Default values
                        status = 'Not Monitoring'
                        is_monitoring = False
                        
                        # Get status directly from the tree view - this is our source of truth
                        tree_status_found = False
                        if hasattr(self, 'monitor_tab'):
                            for item_id in self.monitor_tab.rscm_tree.get_children():
                                item = self.monitor_tab.rscm_tree.item(item_id)
                                if item['values'][0] == rack_name:
                                    status = item['values'][2]
                                    logger.info(f"DEBUG: Tree status for {rack_name} is: {status}")
                                    
                                    # IMPORTANT: Only set is_monitoring to True if status is EXACTLY "Monitoring"
                                    # This ensures "Complete" is correctly reported as not monitoring
                                    is_monitoring = (status == "Monitoring")
                                    logger.info(f"DEBUG: is_monitoring set to {is_monitoring} based on exact status match")
                                    tree_status_found = True
                                    break
                                    
                            if not tree_status_found:
                                logger.info(f"DEBUG: No tree status found for {rack_name}")
                        
                        rack_info = {
                            'name': rack_name,
                            'address': address,
                            'status': status,
                            'is_monitoring': is_monitoring,
                            'last_reading': None
                        }
                        
                        # Get last reading if available
                        if hasattr(self, 'monitor_tab') and hasattr(self.monitor_tab, 'rack_tabs'):
                            if rack_key in self.monitor_tab.rack_tabs:
                                tab_data = self.monitor_tab.rack_tabs[rack_key]
                                if 'data' in tab_data and tab_data['data']:
                                    try:
                                        last_power = tab_data['data'][-1][1]
                                        rack_info['last_reading'] = f"{last_power:.2f} W"
                                    except Exception as e:
                                        logger.debug(f"Error getting last reading: {e}")
                        
                        logger.info(f"DEBUG: Final rack info: {rack_info}")
                        all_racks.append(rack_info)
        
        except Exception as e:
            logger.error(f"Error getting all racks: {str(e)}")

        return all_racks

    def save_config(self):
        """Save configuration to persist changes."""
        try:
            # First, save rack configuration if MonitorTab is available
            if hasattr(self, 'monitor_tab') and hasattr(self.monitor_tab, 'save_rack_config'):
                self.monitor_tab.save_rack_config()
            
            # Then save general application settings
            if hasattr(self, 'config_manager'):
                self.config_manager.save_settings(self.config)
                
            return True
        except Exception as e:
            logger.error(f"Error saving configuration: {str(e)}")
            return False
    
    def add_rscm(self, rack_name, ip_address, username=None, password=None, auto_monitor=True, poll_rate=60):
        """Add a new R-SCM to monitor via the web interface."""
        try:
            # Check if rack already exists in config
            existing_rscms = self.config.get('rscms', [])
            for rscm in existing_rscms:
                if rscm.get('name') == rack_name:
                    logger.error(f"Rack {rack_name} already exists")
                    return False
        
            # Add to config
            new_rscm = {
                'name': rack_name,
                'address': ip_address
            }
        
            # Store username/password if provided
            if username:
                new_rscm['username'] = username
            if password:
                # Should encrypt password before storing
                new_rscm['password'] = password
        
            # Add poll rate if provided and different from default
            if poll_rate != 60:
                new_rscm['poll_rate'] = poll_rate
        
            # Add to rscms list
            if 'rscms' not in self.config:
                self.config['rscms'] = []
            self.config['rscms'].append(new_rscm)
        
            # Also update rscm_list for backward compatibility
            self.config['rscm_list'] = self.config['rscms']
        
            # Save configuration
            if hasattr(self, 'config_manager'):
                self.config_manager.save_settings(self.config)
        
            # Add to monitor tab if it exists
            if hasattr(self, 'monitor_tab'):
                # Add to the tree view
                self.monitor_tab.rscm_tree.insert('', 'end', values=(rack_name, ip_address, "Not Started"))
            
                # Create a tab for it (without showing)
                self.monitor_tab._create_rack_tab_without_showing(rack_name, ip_address)
            
                # NOTE: We're removing the automatic monitoring start to avoid UI prompts
                # Uncomment this block if you want monitoring to start automatically after fixing the UI prompt issue
                '''
                # Start monitoring if requested
                if auto_monitor:
                    # Find the item in the tree
                    for item_id in self.monitor_tab.rscm_tree.get_children():
                        item = self.monitor_tab.rscm_tree.item(item_id)
                        if item['values'][0] == rack_name:
                            # Select this item
                            self.monitor_tab.rscm_tree.selection_set(item_id)
                            # Start monitoring
                            self.monitor_tab._start_selected_monitoring()
                            break
                '''
        
            logger.info(f"Added new R-SCM: {rack_name} at {ip_address}")
            return True
    
        except Exception as e:
            logger.error(f"Error adding R-SCM {rack_name}: {str(e)}")
            return False

    def update_rscm(self, original_rack_name, rack_name, ip_address, username=None, password=None, poll_rate=60):
        """Update an existing R-SCM configuration via the web interface."""
        try:
            # Check if the name is changing and if the new name already exists
            if original_rack_name != rack_name:
                existing_rscms = self.config.get('rscms', [])
                for rscm in existing_rscms:
                    if rscm.get('name') == rack_name:
                        logger.error(f"Cannot rename to {rack_name}: A rack with this name already exists")
                        return False
        
            # Find the rack in config
            found_index = None
            if 'rscms' in self.config:
                for i, rscm in enumerate(self.config['rscms']):
                    if rscm.get('name') == original_rack_name:
                        found_index = i
                        break
        
            if found_index is None:
                logger.error(f"Rack {original_rack_name} not found in configuration")
                return False
        
            # Update the RSCM in config
            self.config['rscms'][found_index]['name'] = rack_name  # Update the rack name
            self.config['rscms'][found_index]['address'] = ip_address
            if username:
                self.config['rscms'][found_index]['username'] = username
            if password:
                # Should encrypt password before storing
                self.config['rscms'][found_index]['password'] = password
        
            # Update rscm_list for backward compatibility
            self.config['rscm_list'] = self.config['rscms']
        
            # Save configuration
            if hasattr(self, 'config_manager'):
                self.config_manager.save_settings(self.config)
        
            # Update in monitor tab if it exists
            if hasattr(self, 'monitor_tab'):
                for item_id in self.monitor_tab.rscm_tree.get_children():
                    item = self.monitor_tab.rscm_tree.item(item_id)
                    if item['values'][0] == original_rack_name:
                        # Update both the rack name and address
                        status = item['values'][2]
                        self.monitor_tab.rscm_tree.item(item_id, values=(rack_name, ip_address, status))
                        
                        # If we have active monitoring or tabs, we'd need to update them
                        if hasattr(self.monitor_tab, 'rack_tabs'):
                            old_key = f"{original_rack_name}_{ip_address}"
                            new_key = f"{rack_name}_{ip_address}"
                            
                            # Rename the rack tab if it exists
                            if old_key in self.monitor_tab.rack_tabs:
                                self.monitor_tab.rack_tabs[new_key] = self.monitor_tab.rack_tabs[old_key]
                                del self.monitor_tab.rack_tabs[old_key]
                                
                                # Update tab label if displayed in notebook
                                if self.monitor_tab.rack_tabs[new_key].get('added_to_notebook', False):
                                    tab = self.monitor_tab.rack_tabs[new_key]['tab']
                                    tab_index = self.monitor_tab.rack_notebook.index(tab)
                                    self.monitor_tab.rack_notebook.tab(tab_index, text=f"{rack_name}")
                        
                        # Update monitoring tasks if active
                        if hasattr(self.monitor_tab, 'monitoring_tasks'):
                            old_key = f"{original_rack_name}_{ip_address}"
                            new_key = f"{rack_name}_{ip_address}"
                            
                            if old_key in self.monitor_tab.monitoring_tasks:
                                self.monitor_tab.monitoring_tasks[new_key] = self.monitor_tab.monitoring_tasks[old_key]
                                del self.monitor_tab.monitoring_tasks[old_key]
                        
                        break
        
            logger.info(f"Updated R-SCM: {original_rack_name} -> {rack_name}")
            return True
    
        except Exception as e:
            logger.error(f"Error updating R-SCM {original_rack_name}: {str(e)}")
            return False

    def delete_rscm(self, rack_name):
        """Delete an R-SCM from configuration via the web interface."""
        try:
            # Check if the rack is being monitored
            if hasattr(self, 'monitor_tab'):
                for item_id in self.monitor_tab.rscm_tree.get_children():
                    item = self.monitor_tab.rscm_tree.item(item_id)
                    if item['values'][0] == rack_name:
                        address = item['values'][1]
                        rack_key = f"{rack_name}_{address}"
                        
                        if rack_key in self.monitor_tab.monitoring_tasks:
                            logger.error(f"Cannot delete {rack_name} while it is being monitored")
                            return False
                        
                        # Remove from tree and tabs if not monitoring
                        self.monitor_tab.rscm_tree.delete(item_id)
                        
                        if rack_key in self.monitor_tab.rack_tabs:
                            if self.monitor_tab.rack_tabs[rack_key].get('added_to_notebook', False):
                                try:
                                    tab_idx = self.monitor_tab.rack_notebook.index(self.monitor_tab.rack_tabs[rack_key]['tab'])
                                    self.monitor_tab.rack_notebook.forget(tab_idx)
                                except Exception as tab_e:
                                    logger.warning(f"Could not remove tab for {rack_name}: {str(tab_e)}")
                            
                            del self.monitor_tab.rack_tabs[rack_key]
                        
                        break
            
            # Remove from config
            if 'rscms' in self.config:
                self.config['rscms'] = [rscm for rscm in self.config['rscms'] if rscm.get('name') != rack_name]
                # Update rscm_list for backward compatibility
                self.config['rscm_list'] = self.config['rscms']
                
                # Save configuration
                if hasattr(self, 'config_manager'):
                    self.config_manager.save_settings(self.config)
        
            logger.info(f"Deleted R-SCM: {rack_name}")
            return True
    
        except Exception as e:
            logger.error(f"Error deleting R-SCM {rack_name}: {str(e)}")
            return False

    def start_monitoring(self, rack_name):
        """Start monitoring for a specific rack via the web interface."""
        try:
            if hasattr(self, 'monitor_tab'):
                # Find the rack in the tree
                found = False
                for item_id in self.monitor_tab.rscm_tree.get_children():
                    item = self.monitor_tab.rscm_tree.item(item_id)
                    if item['values'][0] == rack_name:
                        address = item['values'][1]
                        status = item['values'][2]
                        
                        # Check if already monitoring
                        if status == "Monitoring":
                            logger.info(f"{rack_name} is already being monitored")
                            return True
                        
                        # Select this item in the tree
                        self.monitor_tab.rscm_tree.selection_set(item_id)
                        
                        # Use the existing monitoring start method with default parameters
                        # Get default interval from config or use 1.0
                        interval = self.config.get('monitoring', {}).get('default_interval_minutes', 1.0)
                        # Start monitoring (duration None means continuous)
                        self.monitor_tab._monitor_single_rack_isolated(rack_name, address, interval, None)
                        
                        found = True
                        break
                
                if not found:
                    logger.error(f"Rack {rack_name} not found in tree")
                    return False
                
                return True
            else:
                logger.error("Monitor tab not available")
                return False
        
        except Exception as e:
            logger.error(f"Error starting monitoring for {rack_name}: {str(e)}")
            return False

    def pause_monitoring(self, rack_name):
        """Pause monitoring for a specific rack via the web interface."""
        try:
            if hasattr(self, 'monitor_tab'):
                # Find the rack in the tree
                found = False
                for item_id in self.monitor_tab.rscm_tree.get_children():
                    item = self.monitor_tab.rscm_tree.item(item_id)
                    if item['values'][0] == rack_name:
                        address = item['values'][1]
                        
                        # Stop monitoring for this rack
                        self.monitor_tab._stop_rack_monitoring(rack_name, address)
                        found = True
                        break
                
                if not found:
                    logger.error(f"Rack {rack_name} not found in tree")
                    return False
                
                return True
            else:
                logger.error("Monitor tab not available")
                return False
        
        except Exception as e:
            logger.error(f"Error pausing monitoring for {rack_name}: {str(e)}")
            return False

    def get_rscm_info(self, rack_name):
        """Get information about a specific R-SCM for the web interface."""
        try:
            logger.debug(f"Looking for RSCM with name: {rack_name}")
        
            # Find rack in config
            if 'rscms' in self.config:
                for rscm in self.config['rscms']:
                    if rscm.get('name') == rack_name:
                        # Create a copy to avoid modifying original
                        info = rscm.copy()
                        logger.debug(f"Found RSCM: {info}")
                        
                        # Set default values for fields not in config
                        info['status'] = 'Not Monitoring'
                        info['is_monitoring'] = False
                        
                        # Get status from tree if monitor_tab is available
                        if hasattr(self, 'monitor_tab'):
                            for item_id in self.monitor_tab.rscm_tree.get_children():
                                item = self.monitor_tab.rscm_tree.item(item_id)
                                if item['values'][0] == rack_name:
                                    status = item['values'][2]
                                    info['status'] = status
                                    info['is_monitoring'] = (status == "Monitoring")
                                    break
                    
                        return info
        
            logger.warning(f"RSCM not found: {rack_name}")
            return None
    
        except Exception as e:
            logger.error(f"Error getting info for {rack_name}: {str(e)}")
            return None

    def get_all_racks(self):
        """Get a list of all racks for the management interface."""
        all_racks = []

        try:
            # Use the config as the source of truth for which racks exist
            if 'rscms' in self.config:
                for rscm in self.config['rscms']:
                    rack_name = rscm.get('name')
                    address = rscm.get('address')
                    
                    if rack_name and address:
                        rack_info = {
                            'name': rack_name,
                            'address': address,
                            'status': 'Not Monitoring',
                            'is_monitoring': False,
                            'last_reading': None
                        }
                        
                        # Get status from tree if monitor_tab is available
                        if hasattr(self, 'monitor_tab'):
                            # First check monitoring_tasks for active monitoring
                            rack_key = f"{rack_name}_{address}"
                            if hasattr(self.monitor_tab, 'monitoring_tasks') and rack_key in self.monitor_tab.monitoring_tasks:
                                rack_info['status'] = 'Monitoring'
                                rack_info['is_monitoring'] = True
                            else:
                                # Check the tree view for visual status
                                for item_id in self.monitor_tab.rscm_tree.get_children():
                                    item = self.monitor_tab.rscm_tree.item(item_id)
                                    if item['values'][0] == rack_name:
                                        status = item['values'][2]
                                        rack_info['status'] = status
                                        # Only mark as monitoring if the status explicitly says so
                                        # This ensures "Complete" status is properly reflected
                                        rack_info['is_monitoring'] = (status == "Monitoring")
                                        break
                        
                        # Get last reading if available
                        if rack_key in self.monitor_tab.rack_tabs:
                            tab_data = self.monitor_tab.rack_tabs[rack_key]
                            if 'data' in tab_data and tab_data['data']:
                                last_power = tab_data['data'][-1][1]
                                rack_info['last_reading'] = f"{last_power:.2f} W"
                        
                        all_racks.append(rack_info)
        except Exception as e:
            logger.error(f"Error getting all racks: {str(e)}")

        return all_racks
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