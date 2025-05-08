import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
import logging
import json
import threading
import asyncio

from ..utils.config_manager import ConfigManager

logger = logging.getLogger("power_monitor")

class SettingsTab(ttk.Frame):
    """Settings tab for the application."""
    
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.config_manager = app.config_manager
        self.config = app.config
        
        # Set up the tab UI
        self._init_ui()
        
        # Load current settings
        self._load_current_settings()
    
    def _init_ui(self):
        """Initialize the Settings tab UI."""
        # Main container with padding
        main_frame = ttk.Frame(self, padding=(20, 10))
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create a notebook for categorizing settings
        settings_notebook = ttk.Notebook(main_frame)
        settings_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create tabs for different setting categories
        general_tab = ttk.Frame(settings_notebook)
        credentials_tab = ttk.Frame(settings_notebook)
        appearance_tab = ttk.Frame(settings_notebook)
        
        settings_notebook.add(general_tab, text="General")
        settings_notebook.add(credentials_tab, text="Credentials")
        settings_notebook.add(appearance_tab, text="Appearance")
        
        # === GENERAL SETTINGS TAB ===
        row = 0
        
        # Title
        title_label = ttk.Label(general_tab, text="General Settings", font=("Arial", 12, "bold"))
        title_label.grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(0, 15))
        
        row += 1
        
        # Data Directory Setting
        ttk.Label(general_tab, text="Data Directory:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.data_dir_frame = ttk.Frame(general_tab)
        self.data_dir_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        self.data_dir_var = tk.StringVar()
        self.data_dir_entry = ttk.Entry(self.data_dir_frame, textvariable=self.data_dir_var, width=40)
        self.data_dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.browse_btn = ttk.Button(self.data_dir_frame, text="Browse", command=self.browse_data_dir)
        self.browse_btn.pack(side=tk.RIGHT, padx=(5, 0))
        
        row += 1
        
        # Logging Setting
        ttk.Label(general_tab, text="Enable Logging:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.enable_logging_var = tk.BooleanVar()
        enable_logging_check = ttk.Checkbutton(general_tab, variable=self.enable_logging_var)
        enable_logging_check.grid(row=row, column=1, sticky=tk.W, padx=5, pady=5)
        
        row += 1
        
        # Refresh Interval
        ttk.Label(general_tab, text="Refresh Interval (sec):").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.refresh_interval_var = tk.DoubleVar()
        refresh_spinbox = ttk.Spinbox(general_tab, from_=0.1, to=10.0, increment=0.1, textvariable=self.refresh_interval_var, width=5)
        refresh_spinbox.grid(row=row, column=1, sticky=tk.W, padx=5, pady=5)
        
        row += 1
        
        # Alert Settings
        ttk.Label(general_tab, text="Enable Power Alerts:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.enable_alerts_var = tk.BooleanVar()
        enable_alerts_check = ttk.Checkbutton(general_tab, variable=self.enable_alerts_var, 
                                            command=self._toggle_alert_threshold)
        enable_alerts_check.grid(row=row, column=1, sticky=tk.W, padx=5, pady=5)
        
        row += 1
        
        # Alert Threshold
        ttk.Label(general_tab, text="Alert Threshold (W):").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.alert_threshold_var = tk.IntVar()
        self.alert_threshold_entry = ttk.Spinbox(general_tab, from_=0, to=5000, increment=100, 
                                              textvariable=self.alert_threshold_var, width=5)
        self.alert_threshold_entry.grid(row=row, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Configure column weight for proper expansion
        general_tab.columnconfigure(1, weight=1)
        
        # === CREDENTIALS SETTINGS TAB ===
        row = 0
        
        # Title
        title_label = ttk.Label(credentials_tab, text="Default Credentials", font=("Arial", 12, "bold"))
        title_label.grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(0, 15))
        
        row += 1
        
        # Username
        ttk.Label(credentials_tab, text="Default Username:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.default_username_var = tk.StringVar(value="root")
        default_username_entry = ttk.Entry(credentials_tab, textvariable=self.default_username_var, width=20)
        default_username_entry.grid(row=row, column=1, sticky=tk.W, padx=5, pady=5)
        
        row += 1
        
        # Password
        ttk.Label(credentials_tab, text="Default Password:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        password_frame = ttk.Frame(credentials_tab)
        password_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        self.default_password_var = tk.StringVar()
        self.default_password_entry = ttk.Entry(password_frame, textvariable=self.default_password_var, show="*", width=20)
        self.default_password_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Show/Hide password button
        self.show_password_var = tk.BooleanVar(value=False)
        self.show_password_btn = ttk.Checkbutton(password_frame, text="Show", 
                                               variable=self.show_password_var, 
                                               command=self._toggle_password_visibility)
        self.show_password_btn.pack(side=tk.RIGHT, padx=(5, 0))
        
        row += 1
        
        # Security information
        security_label = ttk.Label(credentials_tab, 
                                 text="Note: Passwords are stored encrypted using machine-specific keys", 
                                 font=("Arial", 9, "italic"))
        security_label.grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(15, 5))
        
        row += 1
        
        # Test Connection button
        test_conn_btn = ttk.Button(credentials_tab, text="Test Connection", command=self._test_connection)
        test_conn_btn.grid(row=row, column=0, columnspan=2, padx=5, pady=10)
        
        # Configure column weight for proper expansion
        credentials_tab.columnconfigure(1, weight=1)
        
        # === APPEARANCE SETTINGS TAB ===
        row = 0
        
        # Title
        title_label = ttk.Label(appearance_tab, text="Appearance Settings", font=("Arial", 12, "bold"))
        title_label.grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(0, 15))
        
        row += 1
        
        # Chart Theme
        ttk.Label(appearance_tab, text="Chart Theme:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.chart_theme_var = tk.StringVar()
        chart_themes = ["default", "dark_background", "bmh", "ggplot", "seaborn", "seaborn-darkgrid"]
        chart_theme_combo = ttk.Combobox(appearance_tab, textvariable=self.chart_theme_var, 
                                     values=chart_themes, width=20, state="readonly")
        chart_theme_combo.grid(row=row, column=1, sticky=tk.W, padx=5, pady=5)
        
        row += 1
        
        # UI Theme
        ttk.Label(appearance_tab, text="UI Theme:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.ui_theme_var = tk.StringVar()
        ui_themes = ["Default", "Dark"]
        ui_theme_combo = ttk.Combobox(appearance_tab, textvariable=self.ui_theme_var, 
                                   values=ui_themes, width=20, state="readonly")
        ui_theme_combo.grid(row=row, column=1, sticky=tk.W, padx=5, pady=5)
        
        row += 1
        
        # Font Size
        ttk.Label(appearance_tab, text="Font Size:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.font_size_var = tk.IntVar()
        font_size_spin = ttk.Spinbox(appearance_tab, from_=8, to=16, textvariable=self.font_size_var, width=5)
        font_size_spin.grid(row=row, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Configure column weight for proper expansion
        appearance_tab.columnconfigure(1, weight=1)
        
        # === BUTTONS SECTION (outside the notebook) ===
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=20)
        
        self.save_btn = ttk.Button(button_frame, text="Save Settings", command=self.save_settings)
        self.save_btn.pack(side=tk.LEFT, padx=5)
        
        self.reset_btn = ttk.Button(button_frame, text="Reset to Defaults", command=self.reset_to_defaults)
        self.reset_btn.pack(side=tk.LEFT, padx=5)
        
        # Status message
        self.status_var = tk.StringVar()
        status_label = ttk.Label(main_frame, textvariable=self.status_var, font=("Arial", 10, "italic"))
        status_label.pack(fill=tk.X, pady=5)
    
    def _load_current_settings(self):
        """Load current settings from the config."""
        # General settings
        self.data_dir_var.set(self.config.get('data_dir', 'power_data'))
        self.enable_logging_var.set(self.config.get('enable_logging', True))
        self.refresh_interval_var.set(self.config.get('refresh_interval', 1.0))
        self.enable_alerts_var.set(self.config.get('enable_alerts', False))
        self.alert_threshold_var.set(self.config.get('alert_threshold', 1000))
        
        # Credentials settings
        self.default_username_var.set(self.config.get('credentials', {}).get('default_username', 'root'))
        
        # Get and decrypt the password if it exists
        encrypted_password = self.config.get('credentials', {}).get('default_password', '')
        if encrypted_password:
            from ..utils.credential_manager import CredentialManager
            cred_manager = CredentialManager()
            decrypted_password = cred_manager.decrypt_password(encrypted_password)
            self.default_password_var.set(decrypted_password)
        
        # Appearance settings
        self.chart_theme_var.set(self.config.get('chart_theme', 'default'))
        self.ui_theme_var.set(self.config.get('ui_theme', 'Default'))
        self.font_size_var.set(self.config.get('font_size', 10))
        
        # Update UI state based on settings
        self._toggle_alert_threshold()
    
    def _toggle_alert_threshold(self):
        """Enable/disable the alert threshold based on the alerts checkbox."""
        if self.enable_alerts_var.get():
            self.alert_threshold_entry.config(state="normal")
        else:
            self.alert_threshold_entry.config(state="disabled")
    
    def _toggle_password_visibility(self):
        """Toggle the visibility of the password field."""
        if self.show_password_var.get():
            self.default_password_entry.config(show="")
        else:
            self.default_password_entry.config(show="*")
    
    def browse_data_dir(self):
        """Open file dialog to select data directory."""
        current_dir = self.data_dir_var.get()
        if not os.path.exists(current_dir):
            current_dir = os.getcwd()
            
        directory = filedialog.askdirectory(initialdir=current_dir, title="Select Data Directory")
        if directory:  # If user didn't cancel
            self.data_dir_var.set(directory)
    
    def _test_connection(self):
        """Test connection with the default credentials."""
        # Get username and password
        username = self.default_username_var.get()
        password = self.default_password_var.get()
        
        if not username or not password:
            self.status_var.set("Error: Username and password are required")
            messagebox.showerror("Input Error", "Please enter both username and password")
            return
        
        # Show testing status
        self.status_var.set("Testing connection...")
        self.update()  # Force UI update
        
        # Ask for an RSCM address to test
        address = simpledialog.askstring(
            "Test Connection", 
            "Enter an RSCM address to test the connection:",
            parent=self.winfo_toplevel()
        )
        
        if not address:
            self.status_var.set("Test cancelled")
            return
        
        # Run test in a separate thread
        def test_conn():
            try:
                # Create API client and test connection
                from ..utils.api_client import RedfishAPIClient
                
                async def run_test():
                    client = RedfishAPIClient()
                    power = await client.get_power_reading(address, username, password)
                    return power
                
                # Run the async test
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                power = loop.run_until_complete(run_test())
                loop.close()
                
                # Update UI with result
                if power is not None:
                    self.after(0, lambda: self.status_var.set("Connection successful"))
                    self.after(0, lambda: messagebox.showinfo(
                        "Connection Success", 
                        f"Successfully connected to {address}\nCurrent power: {power} W"
                    ))
                else:
                    self.after(0, lambda: self.status_var.set("Connection failed"))
                    self.after(0, lambda: messagebox.showerror(
                        "Connection Error",
                        f"Connected to {address} but could not retrieve power data"
                    ))
                    
            except Exception as e:
                self.after(0, lambda: self.status_var.set(f"Error: {str(e)}"))
                self.after(0, lambda: messagebox.showerror(
                    "Connection Error",
                    f"Error connecting to {address}: {str(e)}"
                ))
        
        threading.Thread(target=test_conn, daemon=True).start()
    
    def save_settings(self):
        """Save the current settings."""
        try:
            # Get settings from UI - General tab
            self.config['data_dir'] = self.data_dir_var.get()
            self.config['enable_logging'] = self.enable_logging_var.get()
            self.config['refresh_interval'] = self.refresh_interval_var.get()
            self.config['enable_alerts'] = self.enable_alerts_var.get()
            self.config['alert_threshold'] = self.alert_threshold_var.get()
            
            # Credentials tab
            if 'credentials' not in self.config:
                self.config['credentials'] = {}
                
            self.config['credentials']['default_username'] = self.default_username_var.get()

            # Encrypt the password before saving
            from ..utils.credential_manager import CredentialManager
            cred_manager = CredentialManager()
            password = self.default_password_var.get()
            if password:
                encrypted_password = cred_manager.encrypt_password(password)
                self.config['credentials']['default_password'] = encrypted_password
            
            # Appearance tab
            self.config['chart_theme'] = self.chart_theme_var.get()
            self.config['ui_theme'] = self.ui_theme_var.get()
            self.config['font_size'] = self.font_size_var.get()
            
            # Save settings
            success = self.config_manager.save_settings(self.config)
            
            if success:
                self.status_var.set("Settings saved successfully")
                messagebox.showinfo("Settings Saved", "Settings have been saved successfully.")
                
                # Apply theme changes if needed
                self._apply_theme_changes()
                
                # Update other tabs with new settings
                if hasattr(self.app, 'monitor_tab') and hasattr(self.app.monitor_tab, 'update_from_settings'):
                    self.app.monitor_tab.update_from_settings()
            else:
                self.status_var.set("Failed to save settings")
                messagebox.showerror("Error", "Failed to save settings.")
                
        except Exception as e:
            logger.error(f"Error saving settings: {str(e)}")
            self.status_var.set(f"Error: {str(e)}")
            messagebox.showerror("Error", f"An error occurred while saving settings: {str(e)}")
    
    def _apply_theme_changes(self):
        """Apply theme changes to the application."""
        # Apply chart theme (will take effect on next chart creation)
        
        # Apply UI theme if implemented
        ui_theme = self.ui_theme_var.get()
        if hasattr(self.app, 'theme_manager'):
            self.app.theme_manager.apply_theme(ui_theme)
    
    def reset_to_defaults(self):
        """Reset settings to default values."""
        if messagebox.askyesno("Confirm Reset", "Are you sure you want to reset all settings to default values?"):
            # Load default settings
            self.config = self.config_manager.default_config
            self._load_current_settings()
            self.status_var.set("Settings reset to defaults")
            messagebox.showinfo("Settings Reset", "Settings have been reset to default values.")