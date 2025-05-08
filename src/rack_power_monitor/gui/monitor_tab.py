import tkinter
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, StringVar
import threading
import datetime
import logging
import os
import csv
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import asyncio
import matplotlib.dates as mdates
import os.path
import concurrent.futures

# Import our modules
from ..core.monitor import RackPowerMonitor

logger = logging.getLogger("power_monitor")

class MonitorTab(ttk.Frame):
    """Monitor tab for the application."""
    
    def __init__(self, parent, app):
        """Initialize the monitor tab."""
        super().__init__(parent)
        self.app = app
        self.monitoring_active = False
        self.rack_tabs = {}  # Store references to RSCM tabs
        
        # Add these new variables for per-rack monitoring
        self.monitoring_tasks = {}  # Store monitoring tasks for each rack
        self.monitoring_status = {}  # Track monitoring status per rack
        
        # Set up the tab UI
        self._init_ui()
        
        # Call _setup_async_support to initialize self.monitor and async support
        self._setup_async_support()
        
        # Load saved RSCMs
        self._load_rscm_list()
        
        # Add default RSCMs if none were loaded
        if not self.rscm_tree.get_children():
            self._add_default_rscms()
        
        # Initialize status
        self.app.set_status("Ready")
    
#####################################
    def _init_ui(self):
        """Initialize the UI components."""
        # First create the main frame that will contain all other elements
        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Initialize essential variables FIRST - before they're used in any UI components
        self.data_dir_var = tk.StringVar(value=self.app.config.get('data_dir', 'power_data'))
        self.full_path_var = tk.StringVar(value=os.path.abspath(self.data_dir_var.get()))
        
        # Initialize credentials variables
        self.use_manual_creds_var = tk.BooleanVar(value=False)
        self.username_var = tk.StringVar(value="root")
        self.password_var = tk.StringVar()
        
        # Initialize monitoring parameter variables
        self.interval_var = tk.DoubleVar(value=self.app.config.get('monitoring', {}).get('default_interval_minutes', 1.0))
        self.duration_var = tk.DoubleVar(value=self.app.config.get('monitoring', {}).get('default_duration_hours', 1.0))
        
        # Initialize RSCM address variable for testing
        self.rscm_address_var = tk.StringVar()
        
        # Initialize rack name variable
        self.rack_name_var = tk.StringVar()
        
        # Configure row and column weights for main frame to ensure proper scaling
        self.main_frame.columnconfigure(0, weight=0)  # Left controls panel (fixed width)
        self.main_frame.columnconfigure(1, weight=3)  # Right graphs panel (expandable)
        self.main_frame.rowconfigure(0, weight=1)  # Both sides are expandable vertically
        
        # Create left controls panel
        left_panel = ttk.Frame(self.main_frame)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Configure left panel rows
        left_panel.columnconfigure(0, weight=1)
        left_panel.rowconfigure(0, weight=0)  # RSCM List (fixed height)
        left_panel.rowconfigure(1, weight=1)  # Log (expandable) - was 2, now 1
        
        # === Left Panel Content ===
        # RSCM List section with Add/Remove buttons
        list_frame = ttk.LabelFrame(left_panel, text="RSCM List")
        list_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Configure list_frame columns and rows
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=0)  # Controls (fixed height)
        list_frame.rowconfigure(1, weight=1)  # Tree (expandable)
        
        # Controls above the list
        controls_frame = ttk.Frame(list_frame)
        controls_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        # Add buttons for RSCM management
        add_btn = ttk.Button(controls_frame, text="Add RSCM", command=self._show_add_rscm_dialog)
        add_btn.pack(side=tk.LEFT, padx=5)
        
        remove_btn = ttk.Button(controls_frame, text="Remove Selected", command=self._remove_rscm)
        remove_btn.pack(side=tk.LEFT, padx=5)
        
        clear_btn = ttk.Button(controls_frame, text="Clear All", command=self._clear_rscms)
        clear_btn.pack(side=tk.LEFT, padx=5)
        
        import_btn = ttk.Button(controls_frame, text="Import CSV", command=self._import_from_csv)
        import_btn.pack(side=tk.LEFT, padx=5)
        
        # RSCM Tree (Table) in a frame that can expand
        tree_frame = ttk.Frame(list_frame)
        tree_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        
        # Configure tree_frame for scaling
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        
        columns = ("Name", "Address", "Status")
        self.rscm_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", 
                                    selectmode="browse", height=8)  # Show more rows
        
        # Configure columns
        self.rscm_tree.heading("Name", text="Name")
        self.rscm_tree.heading("Address", text="Address")
        self.rscm_tree.heading("Status", text="Status")
        
        # Use proportional column widths
        self.rscm_tree.column("Name", width=100, anchor=tk.W, stretch=True)
        self.rscm_tree.column("Address", width=100, anchor=tk.W, stretch=True)
        self.rscm_tree.column("Status", width=80, anchor=tk.CENTER, stretch=True)
        
        # Add a scrollbar
        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.rscm_tree.yview)
        self.rscm_tree.configure(yscroll=tree_scroll.set)
        
        # Grid the tree and scrollbar
        self.rscm_tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll.grid(row=0, column=1, sticky="ns")
        
        # Add double-click event to tree for quick testing
        self.rscm_tree.bind("<Double-1>", self._on_tree_double_click)
        
        # Add right-click context menu for the tree
        self.tree_menu = tk.Menu(self, tearoff=0)
        self.tree_menu.add_command(label="Start Monitoring", command=self._start_selected_monitoring)
        self.tree_menu.add_command(label="Stop Monitoring", command=self._stop_selected_monitoring)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="Test Connection", command=self._test_connection)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="Remove", command=self._remove_rscm)

        self.rscm_tree.bind("<Button-3>", self._show_tree_menu)
        
        # Logging section at the bottom of the left panel
        log_frame = ttk.LabelFrame(left_panel, text="Log Messages")
        log_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)  # Changed from row=2 to row=1
        
        # Configure log frame scaling
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, width=40, wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.log_text.config(state=tk.DISABLED)
        
        # Create right panel for graphs
        right_panel = ttk.Frame(self.main_frame)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        
        # Configure right panel scaling
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(0, weight=1)
        
        # Tab notebook for rack graphs
        self.rack_notebook = ttk.Notebook(right_panel)
        self.rack_notebook.grid(row=0, column=0, sticky="nsew")
        
        # Instead of adding a default "No RSCMs" tab, create instructions frame
        self.instructions_frame = ttk.Frame(right_panel)
        self.instructions_frame.grid(row=0, column=0, sticky="nsew")
        
        # Configure instructions frame for scaling and centering
        self.instructions_frame.columnconfigure(0, weight=1)
        self.instructions_frame.rowconfigure(0, weight=1)  # Top padding
        self.instructions_frame.rowconfigure(1, weight=0)  # Centered content
        self.instructions_frame.rowconfigure(2, weight=1)  # Bottom padding
        
        # Create a frame for the centered content
        centered_content = ttk.Frame(self.instructions_frame)
        centered_content.grid(row=1, column=0, sticky="n")
        
        # Instructions heading
        heading_label = ttk.Label(
            centered_content, 
            text="Rack Power Monitor", 
            font=("Arial", 16, "bold")
        )
        heading_label.pack(pady=(0, 20))
        
        # Add instructions
        instruction_label = ttk.Label(
            centered_content,
            text="1. Add RSCMs using the 'Add RSCM' button\n" +
                 "2. Right-click on a rack to start monitoring\n" +
                 "3. Monitoring data will appear here in rack-specific tabs",
            font=("Arial", 12),
            justify=tk.LEFT
        )
        instruction_label.pack(pady=10)
        
        # Add a decorative icon or separator
        separator = ttk.Separator(centered_content, orient="horizontal")
        separator.pack(fill="x", pady=20)
        
        # Initially, show instructions instead of empty notebook
        self._toggle_instructions_visibility()
######################################
        
    def _setup_async_support(self):
        """Set up asynchronous support for monitoring."""
        # Get the event loop
        self.async_loop = asyncio.get_event_loop()
        
        # Create a monitor instance for general use
        self.monitor = RackPowerMonitor()
        # Get data directory from app config
        self.data_dir_var.set(self.app.config.get('data_dir', 'power_data'))
        self.monitor.data_dir = self.data_dir_var.get()
        os.makedirs(self.monitor.data_dir, exist_ok=True)
        
        self.log_message("Async support initialized")

    def _show_tree_menu(self, event):
        """Show the context menu for the tree view."""
        # Get the item under the cursor
        iid = self.rscm_tree.identify_row(event.y)
        if iid:
            # Select the item
            self.rscm_tree.selection_set(iid)
            
            # Get the status of the selected item
            item = self.rscm_tree.item(iid)
            status = item['values'][2]
            
            # Enable/disable menu items based on status
            if status == "Monitoring":
                self.tree_menu.entryconfigure("Start Monitoring", state="disabled")
                self.tree_menu.entryconfigure("Stop Monitoring", state="normal")
            else:
                self.tree_menu.entryconfigure("Start Monitoring", state="normal")
                self.tree_menu.entryconfigure("Stop Monitoring", state="disabled")
            
            # Show the menu
            self.tree_menu.post(event.x_root, event.y_root)

    def _start_selected_monitoring(self):
        """Start monitoring for the selected RSCM."""
        selected = self.rscm_tree.selection()
        if not selected:
            messagebox.showinfo("Selection", "Please select an RSCM to monitor")
            return
        
        # Get the selected item's values
        item = self.rscm_tree.item(selected[0])
        name = item['values'][0]
        address = item['values'][1]
        current_status = item['values'][2]
        
        # Check if this rack is already being monitored
        if current_status in ["Monitoring", "Connecting"]:
            messagebox.showinfo("Already Monitoring", f"{name} is already being monitored")
            return
        
        # Show a dialog to get monitoring parameters
        dialog = tk.Toplevel(self)
        dialog.title(f"Monitor {name}")
        dialog.geometry("300x200")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        # Center dialog
        x = self.winfo_rootx() + (self.winfo_width() // 2) - (300 // 2)
        y = self.winfo_rooty() + (self.winfo_height() // 2) - (200 // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Create form for parameters
        frame = ttk.Frame(dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Interval
        ttk.Label(frame, text="Interval (min):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        interval_var = tk.DoubleVar(value=self.interval_var.get())
        interval_spin = ttk.Spinbox(frame, from_=0.1, to=60, increment=0.1, textvariable=interval_var, width=8)
        interval_spin.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Duration
        ttk.Label(frame, text="Duration (hrs):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        duration_var = tk.DoubleVar(value=self.duration_var.get())
        duration_spin = ttk.Spinbox(frame, from_=0.1, to=24, increment=0.1, textvariable=duration_var, width=8)
        duration_spin.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Continuous monitoring option
        continuous_var = tk.BooleanVar(value=False)
        continuous_check = ttk.Checkbutton(frame, text="Continuous monitoring (no end time)", variable=continuous_var)
        continuous_check.grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        
        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, sticky=tk.E, padx=5, pady=10)
        
        # Function to start monitoring THIS ONE RACK ONLY
        def do_start():
            interval = interval_var.get()
            duration = duration_var.get() if not continuous_var.get() else None
            
            # Save settings as new defaults
            self.interval_var.set(interval)
            if duration:
                self.duration_var.set(duration)
            
            dialog.destroy()
            
            # Only monitor THIS ONE rack - not any others
            self._monitor_single_rack_isolated(name, address, interval, duration)
        
        start_btn = ttk.Button(btn_frame, text="Start", command=do_start, width=10)
        start_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = ttk.Button(btn_frame, text="Cancel", command=dialog.destroy, width=10)
        cancel_btn.pack(side=tk.LEFT, padx=5)
        
        # Make dialog modal
        dialog.wait_window()

    def _stop_selected_monitoring(self):
        """Stop monitoring for the selected RSCM."""
        selected = self.rscm_tree.selection()
        if not selected:
            messagebox.showinfo("Selection", "Please select an RSCM to stop monitoring")
            return
        
        # Get the selected item's values
        item = self.rscm_tree.item(selected[0])
        name = item['values'][0]
        address = item['values'][1]
        current_status = item['values'][2]
        
        # Check if this rack is being monitored
        if current_status not in ["Monitoring", "Connecting"]:
            messagebox.showinfo("Not Monitoring", f"{name} is not currently being monitored")
            return
        
        # Stop monitoring
        self._stop_rack_monitoring(name, address)

    def _stop_monitoring(self):
        """Stop all monitoring processes."""
        self.log_message("Stopping all monitoring processes")
        
        # Stop each rack monitoring task
        for rack_key in list(self.monitoring_tasks.keys()):
            parts = rack_key.split('_')
            if len(parts) >= 2:
                name = parts[0]
                address = '_'.join(parts[1:])  # Handle addresses that might have underscores
                self._stop_rack_monitoring(name, address)
        
        # Clear all monitoring tasks
        self.monitoring_tasks.clear()
        self.monitoring_status.clear()
        
        # Update global monitoring state
        self.monitoring_active = False

    def _stop_rack_monitoring(self, rack_name, rack_address):
        """Stop monitoring for a specific rack."""
        rack_key = f"{rack_name}_{rack_address}"
        
        if rack_key not in self.monitoring_tasks:
            self.log_message(f"{rack_name} is not currently being monitored")
            return
                
        # Set flag to indicate manual stopping
        if rack_key in self.monitoring_status:
            self.monitoring_status[rack_key] = False
        
        # Update status
        self._update_rack_status(rack_name, rack_address, "Stopping")
        
        # Stop the monitor and cancel the future
        task_info = self.monitoring_tasks.get(rack_key, {})
        
        try:
            # Stop the monitor instance if it exists
            if 'monitor' in task_info and task_info['monitor']:
                # Set the stop_requested flag on the monitor
                task_info['monitor'].stop_requested = True
                self.log_message(f"Stop flag set for {rack_name}")
                
            # Cancel the future if it exists
            if 'future' in task_info and task_info['future']:
                task_info['future'].cancel()
                self.log_message(f"Future cancelled for {rack_name}")
                
            self.log_message(f"Stopping monitoring for {rack_name} ({rack_address})")
            
            # Update status to reflect stopping
            self._update_rack_status(rack_name, rack_address, "Stopped")
        except Exception as e:
            error_msg = str(e) if str(e) else "Task was already cancelled"
            self.log_message(f"Error while stopping monitoring for {rack_name}: {error_msg}", level="WARNING")
        
        # Clean up the task regardless of any errors
        if rack_key in self.monitoring_tasks:
            del self.monitoring_tasks[rack_key]
        
        if rack_key in self.monitoring_status:
            del self.monitoring_status[rack_key]
        
        # FIXED: Only remove the specific tab for this rack
        if rack_key in self.rack_tabs and self.rack_tabs[rack_key].get('added_to_notebook', False):
            try:
                tab_idx = self.rack_notebook.index(self.rack_tabs[rack_key]['tab'])
                self.rack_notebook.forget(tab_idx)
                self.rack_tabs[rack_key]['added_to_notebook'] = False
            except (ValueError, tkinter.TclError) as e:
                self.log_message(f"Could not remove tab for {rack_name}: {str(e)}", level="WARNING")
        
        # Update global monitoring state if no tasks left
        if not self.monitoring_tasks:
            self.monitoring_active = False
            
            # Show the instructions frame only if no more tabs
            if not self.rack_notebook.tabs():
                self._toggle_instructions_visibility()
        else:
            # If there are still active monitoring tasks, make sure we show tabs for them
            active_monitoring_keys = list(self.monitoring_tasks.keys())
            for active_key in active_monitoring_keys:
                if active_key in self.rack_tabs and not self.rack_tabs[active_key].get('added_to_notebook', False):
                    parts = active_key.split('_')
                    active_name = parts[0]
                    self.rack_notebook.add(self.rack_tabs[active_key]['tab'], text=active_name)
                    self.rack_tabs[active_key]['added_to_notebook'] = True

    def _update_rack_status(self, rack_name, rack_address, status):
        """Update the status of a rack in the tree."""
        # Find the item
        for item_id in self.rscm_tree.get_children():
            item = self.rscm_tree.item(item_id)
            if item['values'][0] == rack_name and item['values'][1] == rack_address:
                # Update the status
                self.rscm_tree.item(item_id, values=(rack_name, rack_address, status))
                break

    def _monitor_single_rack_isolated(self, rack_name, rack_address, interval_minutes, duration_hours=None):
        """Start monitoring for a specific rack with complete isolation."""
        # Add debug logging
        self.log_message(f"Starting isolated monitoring for {rack_name} ({rack_address}) with interval={interval_minutes}min")
        
        try:
            # Initialize credential manager
            from ..utils.credential_manager import CredentialManager
            cred_manager = CredentialManager()
            
            # Get default credentials
            credentials = self.app.config.get('credentials', {})
            default_username = credentials.get('default_username', 'root')
            default_encrypted_password = credentials.get('default_password', '')
            default_password = cred_manager.decrypt_password(default_encrypted_password) if default_encrypted_password else None
            
            # If using manual credentials, get them
            use_manual = self.use_manual_creds_var.get()
            manual_username = self.username_var.get() if use_manual else None
            manual_password = self.password_var.get() if use_manual else None
            
            # Determine which credentials to use
            if use_manual and manual_username and manual_password:
                username = manual_username
                password = manual_password
                self.log_message(f"Using manual credentials for {rack_name} ({rack_address})")
            elif default_username and default_password:
                username = default_username
                password = default_password
                self.log_message(f"Using default credentials for {rack_name} ({rack_address})")
            else:
                # Failed to get credentials
                self.log_message(f"No credentials available for {rack_name} ({rack_address})", level="ERROR")
                messagebox.showerror("Authentication Error", f"No credentials available for {rack_name} ({rack_address})")
                return
            
            # Test the connection first to verify credentials
            success = self._test_connection_sync(rack_name, rack_address, username, password)
            if not success:
                self.log_message(f"Connection test failed before monitoring {rack_name} ({rack_address})", level="ERROR")
                messagebox.showerror("Connection Error", f"Failed to connect to {rack_name} ({rack_address}). Please check credentials and try again.")
                return
                
            # Log the credentials being used
            self.log_message(f"Verified credentials work for {rack_name} ({rack_address})")
            
            # Create a monitor just for this rack
            from ..core.monitor import RackPowerMonitor
            monitor = RackPowerMonitor()
            
            # IMPORTANT: Set up data directory
            monitor.data_dir = self.data_dir_var.get()
            import os
            os.makedirs(monitor.data_dir, exist_ok=True)
            
            # FIX: Initialize racks attribute properly with credentials
            monitor.racks = {
                rack_name: {
                    "address": rack_address,
                    "username": username,  # Make sure this is passed
                    "password": password   # Make sure this is passed
                }
            }
            
            # Log the configuration to verify credentials are passed
            self.log_message(f"Monitor configured for {rack_name} with username: {username}")
            self.log_message(f"Credentials length: username={len(username)}, password={len(password)}")
            
            # Create rack tab if it doesn't exist
            rack_key = f"{rack_name}_{rack_address}"
            if rack_key not in self.rack_tabs:
                self._create_rack_tab_without_showing(rack_name, rack_address)
            
            # Remove the instructions frame if it is visible
            self._toggle_instructions_visibility(show_instructions=False)

            # MODIFY THIS SECTION: Instead of removing all tabs, keep tabs for active monitors
            # Get a list of racks being actively monitored (including the current one we're adding)
            active_monitoring_keys = [k for k in self.monitoring_tasks.keys()]
            active_monitoring_keys.append(rack_key)  # Add current rack
            
            # Only keep tabs for active monitoring sessions
            for existing_key in list(self.rack_tabs.keys()):
                # If this tab is not being monitored and is in the notebook, remove it
                if existing_key not in active_monitoring_keys and self.rack_tabs[existing_key].get('added_to_notebook', False):
                    self.rack_notebook.forget(self.rack_notebook.index(self.rack_tabs[existing_key]['tab']))
                    self.rack_tabs[existing_key]['added_to_notebook'] = False
            
            # Make sure the current monitoring tab is added to the notebook
            if not self.rack_tabs[rack_key].get('added_to_notebook', False):
                self.rack_notebook.add(self.rack_tabs[rack_key]['tab'], text=rack_name)
                self.rack_tabs[rack_key]['added_to_notebook'] = True
            
            # Select the tab for the rack we're starting to monitor
            tab_idx = self.rack_notebook.index(self.rack_tabs[rack_key]['tab'])
            self.rack_notebook.select(tab_idx)
            
            # Toggle visibility after adding a tab
            self._toggle_instructions_visibility()
            
            # Initialize data if needed
            if 'data' not in self.rack_tabs[rack_key]:
                self.rack_tabs[rack_key]['data'] = []
            
            # Store this monitoring task in the monitoring_tasks dictionary
            self.monitoring_tasks[rack_key] = {
                'monitor': monitor,
                'future': None  # Will be set by the thread
            }
            
            # Run the monitoring thread
            import threading
            monitor_thread = threading.Thread(
                target=self._run_isolated_rack_monitoring,
                args=(monitor, rack_name, rack_address, interval_minutes, duration_hours, username, password)  # Pass credentials
            )
            monitor_thread.daemon = True
            monitor_thread.start()
            
            # Log thread started
            self.log_message(f"Started monitoring thread for {rack_name}")
            
        except Exception as e:
            self.log_message(f"Error starting monitoring for {rack_name}: {str(e)}", level="ERROR")
            import traceback
            self.log_message(f"Exception details: {traceback.format_exc()}", level="ERROR")
            messagebox.showerror("Monitoring Error", f"Error starting monitoring for {rack_name}: {str(e)}")

    def _run_isolated_rack_monitoring(self, monitor, rack_name, rack_address, interval_minutes, duration_hours=None, username=None, password=None):
        """Run completely isolated monitoring for a single rack."""
        try:
            # Update status
            self.after(0, lambda: self._update_rack_status(rack_name, rack_address, "Monitoring"))
            
            # Track rack status
            rack_key = f"{rack_name}_{rack_address}"
            self.monitoring_status[rack_key] = True
            
            # Make sure the monitor has the correct rack configuration and CREDENTIALS
            monitor.racks = {
                rack_name: {
                    "address": rack_address,
                    "username": username,  # Use the passed username 
                    "password": password   # Use the passed password
                }
            }
            
            # Log the configuration
            import logging
            logger = logging.getLogger("power_monitor")
            logger.info(f"Monitor configured for rack {rack_name} with address {rack_address}")
            
            # Define callback to handle data
            def isolated_callback(callback_name, timestamp, power):
                # Log the data received
                logger.info(f"CALLBACK: Received data for {callback_name}: {power:.2f}W at {timestamp}")
                
                # Important: Use after() to update UI from background thread
                self.after(0, lambda: self._update_data(
                    rack_name=rack_name, 
                    rack_address=rack_address, 
                    timestamp=timestamp, 
                    power=power
                ))
            
            # Run the monitoring task in the event loop
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Log before running
            logger.info(f"Starting monitor_all_racks with rack {rack_name}")
            
            # Run the coroutine directly in this thread
            result = loop.run_until_complete(
                monitor.monitor_all_racks(
                    interval_minutes=interval_minutes,
                    duration_hours=duration_hours,
                    callback=isolated_callback
                )
            )
            
            logger.info(f"monitor_all_racks completed with result: {result}")
            
            # Close the loop when done
            loop.close()
            
            # Update status when finished
            self.after(0, lambda: self._update_rack_status(rack_name, rack_address, "Complete"))
            
        except Exception as e:
            self.after(0, lambda: self._update_rack_status(rack_name, rack_address, "Error"))
            self.after(0, lambda msg=str(e): self.log_message(f"Error in monitoring thread: {msg}", level="ERROR"))
            
            # Log the full exception for debugging
            import traceback
            import logging
            logger = logging.getLogger("power_monitor")
            logger.error(f"Exception in monitoring thread: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")

    def _test_connection_sync(self, rack_name, rack_address, username, password):
        """Test connection synchronously before starting monitoring."""
        try:
            import asyncio
            from ..utils.api_client import RedfishAPIClient
            
            # Create a new event loop for this test
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            client = RedfishAPIClient()
            
            # Run the connection test
            self.log_message(f"Testing connection before monitoring {rack_name} ({rack_address})...")
            success = loop.run_until_complete(client.test_connection(rack_address, username, password))
            
            # Close the loop when done
            loop.close()
            
            if success:
                self.log_message(f"Pre-monitoring connection test succeeded for {rack_name}")
                return True
            else:
                self.log_message(f"Pre-monitoring connection test failed for {rack_name}", level="ERROR")
                return False
        except Exception as e:
            self.log_message(f"Error in pre-monitoring connection test: {str(e)}", level="ERROR")
            return False

    def log_message(self, message, level="INFO"):
        """Log a message to the text widget and application logger."""
        # Get the current time
        timestamp = datetime.datetime.now().strftime("[%H:%M:%S]")
        
        # Format the message
        formatted = f"{timestamp} {level}: {message}"
        
        # Determine the tag based on level
        tag = level.lower()
        
        # Enable editing of text widget
        self.log_text.config(state=tk.NORMAL)
        
        # Add message at the end
        self.log_text.insert(tk.END, formatted + "\n", tag)
        
        # Configure tag colors based on level
        if level == "ERROR":
            self.log_text.tag_configure(tag, foreground="red")
        elif level == "WARNING":
            self.log_text.tag_configure(tag, foreground="orange")
        elif level == "INFO":
            self.log_text.tag_configure(tag, foreground="black")
        
        # Scroll to the end
        self.log_text.see(tk.END)
        
        # Disable editing again
        self.log_text.config(state=tk.DISABLED)
        
        # Log to the application logger
        if level == "ERROR":
            logger.error(message)
        elif level == "WARNING":
            logger.warning(message)
        else:
            logger.info(message)

    def update_from_settings(self):
        """Update components based on settings."""
        # Update the data directory
        self.data_dir_var.set(self.app.config.get('data_dir', 'power_data'))
        self.full_path_var.set(os.path.abspath(self.data_dir_var.get()))
        
##################
    def _show_add_rscm_dialog(self):
        """Show dialog to add a new RSCM."""
        # Create a dialog window
        dialog = tk.Toplevel(self)
        dialog.title("Add RSCM")
        dialog.geometry("300x160")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        # Center dialog
        x = self.winfo_rootx() + (self.winfo_width() // 2) - (300 // 2)
        y = self.winfo_rooty() + (self.winfo_height() // 2) - (160 // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Create form
        frame = ttk.Frame(dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Name field
        ttk.Label(frame, text="Name:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        name_var = tk.StringVar()
        name_entry = ttk.Entry(frame, textvariable=name_var, width=20)
        name_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Address field
        ttk.Label(frame, text="Address:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        address_var = tk.StringVar()
        address_entry = ttk.Entry(frame, textvariable=address_var, width=20)
        address_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=2, column=0, columnspan=2, sticky=tk.E, padx=5, pady=10)
        
        # Function to add the RSCM
        def do_add():
            name = name_var.get().strip()
            address = address_var.get().strip()
            
            if not name or not address:
                messagebox.showerror("Input Error", "Please enter both name and address")
                return
            
            # Check if this RSCM already exists
            exists = False
            for item_id in self.rscm_tree.get_children():
                item = self.rscm_tree.item(item_id)
                if item['values'][0] == name or item['values'][1] == address:
                    exists = True
                    break
            
            if exists:
                messagebox.showerror("Duplicate", "An RSCM with this name or address already exists")
                return
            
            # Add to tree
            self.rscm_tree.insert('', 'end', values=(name, address, "Not Started"))
            
            # Create tab WITHOUT adding to notebook (changed from _create_rack_tab)
            self._create_rack_tab_without_showing(name, address)
            
            # Save config
            self._save_rscm_list()
            
            self.log_message(f"Added RSCM: {name} ({address})")
            
            # Close dialog
            dialog.destroy()
        
        add_btn = ttk.Button(btn_frame, text="Add", command=do_add, width=10)
        add_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = ttk.Button(btn_frame, text="Cancel", command=dialog.destroy, width=10)
        cancel_btn.pack(side=tk.LEFT, padx=5)
        
        # Focus on the name entry
        name_entry.focus_set()
        
        # Make dialog modal
        dialog.wait_window()

    def _create_rack_tab(self, name, address):
        """Create a new tab for a specific RSCM."""
        # Check if tab already exists
        rack_key = f"{name}_{address}"
        if rack_key in self.rack_tabs:
            return
        
        # Create a new tab
        rack_tab = ttk.Frame(self.rack_notebook)
        self.rack_notebook.add(rack_tab, text=name)
        
        # Toggle visibility after adding a tab
        self._toggle_instructions_visibility()
        
        # Configure rack tab scaling
        rack_tab.columnconfigure(0, weight=1)
        rack_tab.rowconfigure(0, weight=4)  # Chart gets more space
        rack_tab.rowconfigure(1, weight=1)  # Info panel gets less space
        
        # Chart frame (top)
        chart_frame = ttk.Frame(rack_tab)
        chart_frame.grid(row=0, column=0, sticky="nsew")
        
        # Configure chart frame
        chart_frame.columnconfigure(0, weight=1)
        chart_frame.rowconfigure(0, weight=1)
        
        # Create Figure and Canvas for the chart
        fig = plt.Figure(figsize=(8, 5), dpi=100)
        fig.subplots_adjust(left=0.10, right=0.95, top=0.92, bottom=0.12)
        ax = fig.add_subplot(111)
        
        ax.set_title(f"Power Usage for {name} ({address})")
        ax.set_xlabel("Time")
        ax.set_ylabel("Power (W)")
        ax.grid(True)
        
        canvas = FigureCanvasTkAgg(fig, master=chart_frame)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.grid(row=0, column=0, sticky="nsew")
        
        # Add a toolbar if needed
        # from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
        # toolbar = NavigationToolbar2Tk(canvas, chart_frame)
        # toolbar.update()
        # canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        
        # Info panel (bottom)
        info_frame = ttk.Frame(rack_tab)
        info_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        
        # Configure info frame
        info_frame.columnconfigure(0, weight=1)  # Stats
        info_frame.columnconfigure(1, weight=0)  # Export button
        info_frame.rowconfigure(0, weight=1)
        
        # Stats frame
        stats_frame = ttk.LabelFrame(info_frame, text="Statistics")
        stats_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Configure stats frame
        stats_frame.columnconfigure(0, weight=0)  # Labels
        stats_frame.columnconfigure(1, weight=1)  # Values
        stats_frame.rowconfigure(0, weight=1)
        stats_frame.rowconfigure(1, weight=1)
        stats_frame.rowconfigure(2, weight=1)
        stats_frame.rowconfigure(3, weight=1)
        
        # Add statistics
        ttk.Label(stats_frame, text="Current:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Label(stats_frame, text="Minimum:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Label(stats_frame, text="Maximum:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Label(stats_frame, text="Average:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        
        # Create StringVars for statistics
        current_var = tk.StringVar(value="0 W")
        min_var = tk.StringVar(value="0 W")
        max_var = tk.StringVar(value="0 W")
        avg_var = tk.StringVar(value="0 W")
        
        # Add value labels
        current_label = ttk.Label(stats_frame, textvariable=current_var, font=("Arial", 10, "bold"))
        current_label.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        min_label = ttk.Label(stats_frame, textvariable=min_var)
        min_label.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        max_label = ttk.Label(stats_frame, textvariable=max_var)
        max_label.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
        avg_label = ttk.Label(stats_frame, textvariable=avg_var)
        avg_label.grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)
        
        # Export button
        export_btn = ttk.Button(info_frame, text="Export Data", 
                            command=lambda: self._export_rack_data(name, address))
        export_btn.grid(row=0, column=1, sticky=tk.E, padx=5, pady=5)
        
        # Store references to the tab and its components
        self.rack_tabs[rack_key] = {
            'tab': rack_tab,
            'figure': fig,
            'axes': ax,
            'canvas': canvas,
            'data': [],  # Will store (timestamp, power) tuples
            'stats': {
                'current': current_var,
                'min': min_var,
                'max': max_var,
                'avg': avg_var
            }
        }


    def _create_rack_tab_without_showing(self, name, address):
        """Create a new tab for a specific RSCM without showing it."""
        # Check if tab already exists
        rack_key = f"{name}_{address}"
        if rack_key in self.rack_tabs:
            return
        
        # Create a new tab but don't add it to the notebook yet
        rack_tab = ttk.Frame(self)  # Create frame but don't attach to notebook
        
        # Configure rack tab scaling
        rack_tab.columnconfigure(0, weight=1)
        rack_tab.rowconfigure(0, weight=4)  # Chart gets more space
        rack_tab.rowconfigure(1, weight=1)  # Info panel gets less space
        
        # Chart frame (top)
        chart_frame = ttk.Frame(rack_tab)
        chart_frame.grid(row=0, column=0, sticky="nsew")
        
        # Configure chart frame
        chart_frame.columnconfigure(0, weight=1)
        chart_frame.rowconfigure(0, weight=1)
        
        # Create Figure and Canvas for the chart
        fig = plt.Figure(figsize=(8, 5), dpi=100)
        fig.subplots_adjust(left=0.10, right=0.95, top=0.92, bottom=0.12)
        ax = fig.add_subplot(111)
        
        ax.set_title(f"Power Usage for {name} ({address})")
        ax.set_xlabel("Time")
        ax.set_ylabel("Power (W)")
        ax.grid(True)
        
        canvas = FigureCanvasTkAgg(fig, master=chart_frame)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.grid(row=0, column=0, sticky="nsew")
        
        # Info panel (bottom)
        info_frame = ttk.Frame(rack_tab)
        info_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        
        # Configure info frame
        info_frame.columnconfigure(0, weight=1)  # Stats
        info_frame.columnconfigure(1, weight=0)  # Control buttons
        info_frame.rowconfigure(0, weight=1)
        
        # Stats frame
        stats_frame = ttk.LabelFrame(info_frame, text="Statistics")
        stats_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Configure stats frame
        stats_frame.columnconfigure(0, weight=0)  # Labels
        stats_frame.columnconfigure(1, weight=1)  # Values
        stats_frame.rowconfigure(0, weight=1)
        stats_frame.rowconfigure(1, weight=1)
        stats_frame.rowconfigure(2, weight=1)
        stats_frame.rowconfigure(3, weight=1)
        stats_frame.rowconfigure(4, weight=1)  # Added for mode
        stats_frame.rowconfigure(5, weight=1)  # Added for reading count
        
        # Add statistics
        ttk.Label(stats_frame, text="Current:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Label(stats_frame, text="Minimum:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Label(stats_frame, text="Maximum:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Label(stats_frame, text="Average:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Label(stats_frame, text="Mode:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=2)  # Added for mode
        ttk.Label(stats_frame, text="Readings:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=2)  # Added for count
        
        # Create StringVars for statistics
        current_var = tk.StringVar(value="0 W")
        min_var = tk.StringVar(value="0 W")
        max_var = tk.StringVar(value="0 W")
        avg_var = tk.StringVar(value="0 W")
        mode_var = tk.StringVar(value="0 W")  # Added for mode
        count_var = tk.StringVar(value="0")  # Added for reading count
        
        # Add value labels
        current_label = ttk.Label(stats_frame, textvariable=current_var, font=("Arial", 10, "bold"))
        current_label.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        min_label = ttk.Label(stats_frame, textvariable=min_var)
        min_label.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        max_label = ttk.Label(stats_frame, textvariable=max_var)
        max_label.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
        avg_label = ttk.Label(stats_frame, textvariable=avg_var)
        avg_label.grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)
        mode_label = ttk.Label(stats_frame, textvariable=mode_var)  # Added for mode
        mode_label.grid(row=4, column=1, sticky=tk.W, padx=5, pady=2)
        count_label = ttk.Label(stats_frame, textvariable=count_var)  # Added for count
        count_label.grid(row=5, column=1, sticky=tk.W, padx=5, pady=2)
        
        # Create a control button frame
        control_frame = ttk.Frame(info_frame)
        control_frame.grid(row=0, column=1, sticky=tk.E, padx=5, pady=5)
        
        # Add Pause/Resume button
        pause_var = tk.StringVar(value="Pause")
        pause_btn = ttk.Button(control_frame, textvariable=pause_var, 
                        command=lambda: self._pause_resume_monitoring(rack_name=name, rack_address=address))
        pause_btn.pack(side=tk.LEFT, padx=2)
        
        # Add Stop button
        stop_btn = ttk.Button(control_frame, text="Stop", 
                        command=lambda: self._stop_rack_monitoring_with_confirmation(name, address))
        stop_btn.pack(side=tk.LEFT, padx=2)
        
        # Export button
        export_btn = ttk.Button(control_frame, text="Export", 
                            command=lambda: self._export_rack_data(name, address))
        export_btn.pack(side=tk.LEFT, padx=2)
        
        # Store references to the tab and its components
        self.rack_tabs[rack_key] = {
            'tab': rack_tab,
            'figure': fig,
            'axes': ax,
            'canvas': canvas,
            'data': [],  # Will store (timestamp, power) tuples
            'stats': {
                'current': current_var,
                'min': min_var,
                'max': max_var,
                'avg': avg_var,
                'mode': mode_var,  # Added for mode
                'count': count_var  # Added for count
            },
            'controls': {
                'pause_var': pause_var,
                'pause_btn': pause_btn,
                'stop_btn': stop_btn
            },
            'added_to_notebook': False,  # Track whether tab is in the notebook
            'paused': False  # Track if monitoring is paused
        }


    def _remove_rscm(self):
        """Remove selected RSCM from the tree."""
        selected_items = self.rscm_tree.selection()
        if not selected_items:
            messagebox.showinfo("Selection Required", "Please select an RSCM to remove.")
            return
        
        # Process each selected item
        for item_id in selected_items:
            item = self.rscm_tree.item(item_id)
            name = item['values'][0]
            address = item['values'][1]
            
            # Check if the rack is being monitored
            rack_key = f"{name}_{address}"
            if rack_key in self.monitoring_tasks:
                messagebox.showwarning("Monitoring Active", 
                                    f"Cannot remove {name} while it is being monitored. "
                                    "Please stop monitoring first.")
                continue
                
            # Confirm removal
            confirm = messagebox.askyesno("Confirm Removal", f"Are you sure you want to remove {name}?")
            if not confirm:
                continue
            
            # Remove from tree
            self.rscm_tree.delete(item_id)
            
            # Remove the rack tab if it exists and is in the notebook
            if rack_key in self.rack_tabs:
                try:
                    # Only try to remove from notebook if it's actually there
                    if self.rack_tabs[rack_key].get('added_to_notebook', False):
                        try:
                            tab_idx = self.rack_notebook.index(self.rack_tabs[rack_key]['tab'])
                            self.rack_notebook.forget(tab_idx)
                        except (ValueError, tkinter.TclError) as e:
                            self.log_message(f"Could not remove tab for {name}: {str(e)}", level="WARNING")
                            
                    # Clean up the rack_tabs dict regardless of whether tab was in notebook
                    del self.rack_tabs[rack_key]
                except Exception as e:
                    self.log_message(f"Error removing tab for {name}: {str(e)}", level="ERROR")
            
            # Log removal
            self.log_message(f"Removed RSCM: {name} ({address})")
        
        # Save changes to configuration
        self._save_rscm_list()
        
        # Toggle visibility based on whether there are any tabs left
        self._toggle_instructions_visibility()


    def _clear_rscms(self):
        """Remove all RSCMs from the tree."""
        # Check if any are being monitored
        monitoring_racks = []
        for item_id in self.rscm_tree.get_children():
            item = self.rscm_tree.item(item_id)
            name = item['values'][0]
            address = item['values'][1]
            
            rack_key = f"{name}_{address}"
            if rack_key in self.monitoring_tasks:
                monitoring_racks.append(name)
        
        if monitoring_racks:
            messagebox.showwarning("Monitoring Active", 
                                f"Cannot clear RSCMs while monitoring is active for: {', '.join(monitoring_racks)}. "
                                "Please stop all monitoring first.")
            return
        
        # Confirm clear
        confirm = messagebox.askyesno("Confirm Clear", "Are you sure you want to remove all RSCMs?")
        if not confirm:
            return
        
        # Clear all items from tree
        for item_id in self.rscm_tree.get_children():
            self.rscm_tree.delete(item_id)
        
        # Clear all rack tabs safely
        for rack_key in list(self.rack_tabs.keys()):
            try:
                if self.rack_tabs[rack_key].get('added_to_notebook', False):
                    try:
                        tab_idx = self.rack_notebook.index(self.rack_tabs[rack_key]['tab'])
                        self.rack_notebook.forget(tab_idx)
                    except (ValueError, tkinter.TclError) as e:
                        self.log_message(f"Could not remove tab for {rack_key}: {str(e)}", level="WARNING")
                        
                # Delete from dictionary anyway
                del self.rack_tabs[rack_key]
            except Exception as e:
                self.log_message(f"Error removing tab: {str(e)}", level="ERROR")
        
        # Save changes to configuration
        self._save_rscm_list()
        
        # Toggle visibility - this will show instructions since notebook is now empty
        self._toggle_instructions_visibility()
        
        # Log clear
        self.log_message("Cleared all RSCMs")

    def _import_from_csv(self):
        """Import RSCMs from a CSV file."""
        from tkinter import filedialog
        
        # Ask for file
        file_path = filedialog.askopenfilename(
            title="Import RSCM List", 
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            # Read CSV
            with open(file_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader)  # Skip header
                
                # Check header format
                if len(header) < 2 or 'name' not in header[0].lower() or 'address' not in header[1].lower():
                    messagebox.showerror(
                        "Format Error", 
                        "CSV file must have 'Name' and 'Address' columns"
                    )
                    return
                
                # Track how many were added
                added = 0
                
                # Read rows
                for row in reader:
                    if len(row) >= 2:
                        name = row[0].strip()
                        address = row[1].strip()
                        
                        if name and address:
                            # Check if this RSCM already exists
                            exists = False
                            for item_id in self.rscm_tree.get_children():
                                item = self.rscm_tree.item(item_id)
                                if item['values'][0] == name and item['values'][1] == address:
                                    exists = True
                                    break
                            
                            if not exists:
                                # Add to tree
                                self.rscm_tree.insert('', 'end', values=(name, address, "Not Started"))
                                
                                # Create tab
                                self._create_rack_tab(name, address)
                                
                                added += 1
            
            # Save the updated list
            self._save_rscm_list()
            
            self.log_message(f"Imported {added} RSCM(s) from {os.path.basename(file_path)}")
            
        except Exception as e:
            messagebox.showerror("Import Error", f"Error importing from CSV: {str(e)}")

    def _test_connection(self):
        """Test connection to the selected RSCM."""
        selected = self.rscm_tree.selection()
        if not selected:
            messagebox.showinfo("Selection", "Please select an RSCM to test")
            return
        
        # Get the selected item's values
        item = self.rscm_tree.item(selected[0])
        name = item['values'][0]
        address = item['values'][1]
        
        # Update status
        self._update_rack_status(name, address, "Testing")
        
        # Create a thread for testing
        threading.Thread(
            target=self._run_test_connection,
            args=(name, address),
            daemon=True
        ).start()

    def _run_test_connection(self, rack_name, rack_address):
        """Run a connection test in a background thread."""
        try:
            # Log the start of the test connection process
            self.log_message(f"STARTING test connection process for {rack_name} ({rack_address})...")
            
            # Update status to indicate testing
            self.after(0, lambda: self._update_rack_status(rack_name, rack_address, "Testing"))
            
            # Initialize credential manager
            from ..utils.credential_manager import CredentialManager
            cred_manager = CredentialManager()
            
            # Get default credentials
            credentials = self.app.config.get('credentials', {})
            default_username = credentials.get('default_username', 'root')
            default_encrypted_password = credentials.get('default_password', '')
            default_password = cred_manager.decrypt_password(default_encrypted_password) if default_encrypted_password else None
            
            # If using manual credentials, get them
            use_manual = self.use_manual_creds_var.get()
            manual_username = self.username_var.get() if use_manual else None
            manual_password = self.password_var.get() if use_manual else None
            
            # Determine which credentials to use
            if use_manual and manual_username and manual_password:
                username = manual_username
                password = manual_password
                self.log_message(f"Using manual credentials for {rack_name} ({rack_address})")
            elif default_username and default_password:
                username = default_username
                password = default_password
                self.log_message(f"Using default credentials for {rack_name} ({rack_address})")
            else:
                # Failed to get credentials
                self.after(0, lambda: self._update_rack_status(rack_name, rack_address, "Auth Error"))
                self.after(0, lambda: self.log_message(f"No credentials available for {rack_name} ({rack_address})", level="ERROR"))
                return
            
            # Create a client for testing
            from ..utils.api_client import RedfishAPIClient
            client = RedfishAPIClient()
            
            self.log_message(f"Testing connection to {rack_name} ({rack_address})...")
            
            # Create and run the test in a separate thread
            import threading
            
            def run_test():
                try:
                    self.log_message(f"Starting test thread for {rack_name} ({rack_address})...")
                    
                    # Create and run the event loop in this thread
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    # Run the test_connection_with_power coroutine synchronously
                    self.log_message(f"Running test_connection_with_power for {rack_name} ({rack_address})...")
                    result, power = loop.run_until_complete(client.test_connection_with_power(rack_address, username, password))
                    
                    # Update UI based on result
                    if result:
                        self.after(0, lambda: self._update_rack_status(rack_name, rack_address, "Ready"))
                        self.after(0, lambda: self.log_message(f"Connection test successful for {rack_name} ({rack_address})"))
                        self.after(0, lambda pwr=power: messagebox.showinfo("Connection Test", 
                            f"Successfully connected to {rack_name} ({rack_address})\nCurrent Power: {pwr:.2f}W"))
                    else:
                        self.after(0, lambda: self._update_rack_status(rack_name, rack_address, "Error"))
                        self.after(0, lambda: self.log_message(f"Connection test failed for {rack_name} ({rack_address})", level="ERROR"))
                        self.after(0, lambda: messagebox.showerror("Connection Test", 
                            f"Failed to connect to {rack_name} ({rack_address}). The RSCM may be unreachable or the API may be unresponsive."))
                    
                    # Close the loop
                    loop.close()
                    
                except Exception as e:
                    self.after(0, lambda: self._update_rack_status(rack_name, rack_address, "Error"))
                    self.after(0, lambda msg=str(e): self.log_message(f"Error in test thread: {msg}", level="ERROR"))
                    self.after(0, lambda msg=str(e): messagebox.showerror("Test Error", f"Error during test: {msg}"))
            
            # Create and start the thread
            test_thread = threading.Thread(target=run_test)
            test_thread.daemon = True
            test_thread.start()
            
        except Exception as e:
            self.after(0, lambda: self._update_rack_status(rack_name, rack_address, "Error"))
            self.after(0, lambda msg=str(e): self.log_message(f"Error testing connection to {rack_name}: {msg}", level="ERROR"))
            self.after(0, lambda msg=str(e): messagebox.showerror("Connection Test", f"Error: {msg}"))

    def _on_tree_double_click(self, event):
        """Handle double-click on a rack in the tree view."""
        # Get the selected item
        selected = self.rscm_tree.selection()
        if not selected:
            return
        
        # Get the selected item's values
        item = self.rscm_tree.item(selected[0])
        name = item['values'][0]
        address = item['values'][1]
        current_status = item['values'][2]
        
        # Handle double-click based on status
        if current_status == "Ready":
            # If the rack is ready, start monitoring
            self._start_selected_monitoring()
        elif current_status == "Monitoring":
            # If the rack is being monitored, stop monitoring
            self._stop_selected_monitoring()
        elif current_status in ["Not Started", "Error", "Stopped"]:
            # If the rack is not started or had an error, test the connection
            self._test_connection()
        
        # Make sure to select the corresponding tab
        rack_key = f"{name}_{address}"
        if rack_key in self.rack_tabs and self.rack_tabs[rack_key].get('added_to_notebook', False):
            tab_idx = self.rack_notebook.index(self.rack_tabs[rack_key]['tab'])
            self.rack_notebook.select(tab_idx)

    def _update_data(self, rack_name, rack_address, timestamp, power):
        """Update the data from monitoring."""
        # Log received data for debugging
        self.log_message(f"GUI: Updating data for {rack_name} = {power:.2f}W at {timestamp}")
        
        # Get the rack key
        rack_key = f"{rack_name}_{rack_address}"
        
        # Check if the tab exists
        if rack_key not in self.rack_tabs:
            self.log_message(f"Warning: Tab for {rack_name} doesn't exist, creating it now...")
            self._create_rack_tab_without_showing(rack_name, rack_address)
            
            # Add the tab to the notebook if it's not already there
            if not self.rack_tabs[rack_key].get('added_to_notebook', False):
                self.rack_notebook.add(self.rack_tabs[rack_key]['tab'], text=rack_name)
                self.rack_tabs[rack_key]['added_to_notebook'] = True
                
            # Select the tab
            tab_idx = self.rack_notebook.index(self.rack_tabs[rack_key]['tab'])
            self.rack_notebook.select(tab_idx)
        
        # Get tab data
        tab_data = self.rack_tabs[rack_key]
        
        # Add data point
        tab_data['data'].append((timestamp, power))
        self.log_message(f"Added data point. Total points: {len(tab_data['data'])}")
        
        # Keep only the last 1000 data points to avoid memory issues
        if len(tab_data['data']) > 1000:
            tab_data['data'] = tab_data['data'][-1000:]
        
        # Update the chart immediately
        self._update_chart(rack_name, rack_address)
        
        # Update statistics
        self._update_statistics(rack_name, rack_address)

    def _update_chart(self, rack_name, rack_address):
        """Update the chart for a specific rack."""
        # Get the rack key
        rack_key = f"{rack_name}_{rack_address}"
        
        # Check if the tab exists
        if rack_key not in self.rack_tabs:
            self.log_message(f"Warning: Cannot update chart - tab for {rack_name} doesn't exist")
            return
        
        # Get tab data
        tab_data = self.rack_tabs[rack_key]
        
        # Check if there's data to plot
        if not tab_data['data']:
            self.log_message(f"Warning: No data to plot for {rack_name}")
            return
            
        # Log that we're updating the chart
        self.log_message(f"Updating chart for {rack_name} with {len(tab_data['data'])} data points")
        
        # Clear the axes
        tab_data['axes'].clear()
        
        # Set title and labels
        tab_data['axes'].set_title(f"Power Usage for {rack_name} ({rack_address})")
        tab_data['axes'].set_xlabel("Time")
        tab_data['axes'].set_ylabel("Power (W)")
        tab_data['axes'].grid(True)
        
        # Extract data for plotting
        timestamps = [d[0] for d in tab_data['data']]
        power_values = [d[1] for d in tab_data['data']]
        
        # Plot the data
        tab_data['axes'].plot(timestamps, power_values, 'b-', marker='o', markersize=2)
        
        # Format the time axis
        tab_data['axes'].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        plt.setp(tab_data['axes'].xaxis.get_majorticklabels(), rotation=45)
        
        # Set y-axis limits to give some padding
        if power_values:
            min_power = min(power_values)
            max_power = max(power_values)
            padding = (max_power - min_power) * 0.1 if max_power > min_power else max_power * 0.1
            tab_data['axes'].set_ylim(min_power - padding, max_power + padding)
        
        # Force tight layout to ensure everything fits
        tab_data['figure'].tight_layout()
        
        # Redraw the canvas
        tab_data['canvas'].draw_idle()
        
        # Log that chart update completed
        self.log_message(f"Chart update complete for {rack_name}")

    def _update_statistics(self, rack_name, rack_address):
        """Update statistics for a specific rack."""
        # Get the rack key
        rack_key = f"{rack_name}_{rack_address}"
        
        # Check if the tab exists
        if rack_key not in self.rack_tabs:
            return
        
        # Get tab data
        tab_data = self.rack_tabs[rack_key]
        
        # Check if there's data
        if not tab_data['data']:
            return
        
        # Extract power values
        power_values = [d[1] for d in tab_data['data']]
        
        # Calculate statistics
        current_power = power_values[-1]
        min_power = min(power_values)
        max_power = max(power_values)
        avg_power = sum(power_values) / len(power_values)
        
        # Calculate mode (most frequent value)
        # Round to 2 decimal places to handle floating point values
        rounded_values = [round(x, 2) for x in power_values]
        
        # Count occurrences of each value
        from collections import Counter
        value_counts = Counter(rounded_values)
        
        # Find the most common value(s)
        most_common = value_counts.most_common(1)
        
        # Check if we have a mode
        if most_common:
            mode_power, mode_count = most_common[0]
            # Only show mode if it appears more than once
            if mode_count > 1:
                mode_text = f"{mode_power:.2f} W ({mode_count} times)"
            else:
                mode_text = "No mode (all values unique)"
        else:
            mode_text = "N/A"
        
        # Get reading count
        reading_count = len(power_values)
        
        # Update statistics variables
        tab_data['stats']['current'].set(f"{current_power:.2f} W")
        tab_data['stats']['min'].set(f"{min_power:.2f} W")
        tab_data['stats']['max'].set(f"{max_power:.2f} W")
        tab_data['stats']['avg'].set(f"{avg_power:.2f} W")
        tab_data['stats']['mode'].set(mode_text)
        tab_data['stats']['count'].set(f"{reading_count}")

    def _save_rscm_list(self):
        """Save the list of RSCMs to the configuration."""
        rscms = []
        
        # Iterate through tree items
        for item_id in self.rscm_tree.get_children():
            item = self.rscm_tree.item(item_id)
            name = item['values'][0]
            address = item['values'][1]
            
            # Add to list
            rscms.append({
                'name': name,
                'address': address
            })
        
        # Save to both config keys for backward compatibility
        self.app.config['rscms'] = rscms  # New format
        self.app.config['rscm_list'] = rscms  # Old format
        
        # Use the config_manager from the app to save settings
        if hasattr(self.app, 'config_manager'):
            self.app.config_manager.save_settings(self.app.config)
            self.log_message(f"Saved {len(rscms)} RSCMs to configuration")
        else:
            self.log_message("Could not save RSCM list - config_manager not available", level="ERROR")

    def _load_rscm_list(self):
        """Load the list of RSCMs from the configuration."""
        # Clear the tree first
        for item_id in self.rscm_tree.get_children():
            self.rscm_tree.delete(item_id)
        
        # Get the list from config
        rscms = []
        
        # First try the 'rscms' key (new format)
        if 'rscms' in self.app.config:
            rscms = self.app.config['rscms']
        # If not found, try 'rscm_list' key (old format)
        elif 'rscm_list' in self.app.config:
            rscms = self.app.config['rscm_list']
        
        self.log_message(f"Found {len(rscms)} RSCMs in configuration")
        
        # Add each RSCM to the tree
        added_count = 0
        for rscm in rscms:
            name = rscm.get('name', '')
            address = rscm.get('address', '')
            
            if name and address:
                # Add to tree
                self.rscm_tree.insert('', 'end', values=(name, address, "Not Started"))
                
                # Create tab WITHOUT adding to notebook
                self._create_rack_tab_without_showing(name, address)
                added_count += 1
        
        self.log_message(f"Loaded {added_count} RSCMs from configuration")
        
        # Toggle visibility based on whether there are any tabs loaded
        has_tabs = False
        for rack_key, rack_data in self.rack_tabs.items():
            if rack_data.get('added_to_notebook', False):
                has_tabs = True
                break
        
        # Call toggle after loading RSCMs
        self._toggle_instructions_visibility()

    def _export_rack_data(self, rack_name, rack_address):
        """Export the data for a specific rack to a CSV file."""
        from tkinter import filedialog
        import os
        import csv
        
        # Get the rack key
        rack_key = f"{rack_name}_{rack_address}"
        
        # Check if the tab exists
        if rack_key not in self.rack_tabs:
            messagebox.showinfo("Export", f"No data available for {rack_name}")
            return
        
        # Get tab data
        tab_data = self.rack_tabs[rack_key]
        
        # Check if there's data to export
        if not tab_data['data']:
            messagebox.showinfo("Export", f"No data available for {rack_name}")
            return
        
        # Ask for file location
        file_path = filedialog.asksaveasfilename(
            title=f"Export Data for {rack_name}",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            initialfile=f"{rack_name}_power_data.csv"
        )
        
        if not file_path:
            return
        
        try:
            # Write to CSV
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Write header
                writer.writerow(["Timestamp", "Power (W)"])
                
                # Write data
                for timestamp, power in tab_data['data']:
                    writer.writerow([timestamp, power])
            
            self.log_message(f"Exported {len(tab_data['data'])} data points for {rack_name} to {os.path.basename(file_path)}")
            messagebox.showinfo("Export Complete", f"Data for {rack_name} exported successfully")
            
        except Exception as e:
            self.log_message(f"Error exporting data for {rack_name}: {str(e)}", level="ERROR")
            messagebox.showerror("Export Error", f"Error exporting data: {str(e)}")

    def _add_default_rscms(self):
        """Add default RSCMs if none exist."""
        
        if not self.rscm_tree.get_children():
            self.log_message("No RSCMs found. Adding default RSCMs.")
            
            default_rscms = [
                {"name": "G24", "address": "10.57.189.43"},
                {"name": "H24", "address": "10.57.191.37"}
            ]
            
            for rscm in default_rscms:
                name = rscm["name"]
                address = rscm["address"]
                
                # Add to tree
                self.rscm_tree.insert('', 'end', values=(name, address, "Not Started"))
                
                # Create tab WITHOUT adding to notebook
                self._create_rack_tab_without_showing(name, address)
                
            # Save to configuration
            self._save_rscm_list()
            
            self.log_message(f"Added {len(default_rscms)} default RSCMs to configuration")

    def _toggle_instructions_visibility(self, show_instructions=None):
        """Toggle between rack notebook and instructions based on whether there are tabs.
        
        Args:
            show_instructions: If provided, explicitly show (True) or hide (False) instructions.
                              If None, determine visibility based on whether notebook has tabs.
        """
        if show_instructions is not None:
            # Explicit override
            if show_instructions:
                # Show instructions, hide notebook
                self.rack_notebook.grid_remove()
                self.instructions_frame.grid(row=0, column=0, sticky="nsew")
            else:
                # Hide instructions, show notebook
                self.instructions_frame.grid_remove()
                self.rack_notebook.grid(row=0, column=0, sticky="nsew")
        else:
            # Auto-determine based on tabs
            if self.rack_notebook.tabs():
                # If there are tabs, show the notebook and hide instructions
                self.rack_notebook.grid(row=0, column=0, sticky="nsew")
                self.instructions_frame.grid_remove()
            else:
                # If no tabs, hide the notebook and show instructions
                self.rack_notebook.grid_remove()
                self.instructions_frame.grid(row=0, column=0, sticky="nsew")

    def _pause_resume_monitoring(self, rack_name, rack_address):
        """Pause or resume monitoring for a specific rack."""
        rack_key = f"{rack_name}_{rack_address}"
        
        if rack_key not in self.rack_tabs:
            return
        
        # Get the current pause state
        paused = self.rack_tabs[rack_key].get('paused', False)
        
        # Toggle the state
        paused = not paused
        self.rack_tabs[rack_key]['paused'] = paused
        
        # Update button text
        if paused:
            self.rack_tabs[rack_key]['controls']['pause_var'].set("Resume")
            self.log_message(f"Monitoring paused for {rack_name}")
            self._update_rack_status(rack_name, rack_address, "Paused")
        else:
            self.rack_tabs[rack_key]['controls']['pause_var'].set("Pause")
            self.log_message(f"Monitoring resumed for {rack_name}")
            self._update_rack_status(rack_name, rack_address, "Monitoring")
        
        # Update monitoring task's paused state
        if rack_key in self.monitoring_tasks and 'monitor' in self.monitoring_tasks[rack_key]:
            # Check if the monitor object has a paused attribute, if not add it
            monitor = self.monitoring_tasks[rack_key]['monitor']
            if not hasattr(monitor, 'paused'):
                monitor.paused = paused
            else:
                monitor.paused = paused

    def _stop_rack_monitoring_with_confirmation(self, rack_name, rack_address):
        """Stop monitoring with confirmation and file location information."""
        # Ask for confirmation
        if not messagebox.askyesno("Confirm Stop", 
                                f"Are you sure you want to stop monitoring for {rack_name}?\n\n"
                                "This will save the current data and close the monitoring session."):
            return
        
        # Stop the monitoring
        rack_key = f"{rack_name}_{rack_address}"
        
        # Get CSV file path that will be created
        data_dir = self.data_dir_var.get()
        import datetime
        current_date = datetime.datetime.now().strftime("%Y%m%d")
        csv_filename = f"{rack_name}_{current_date}.csv"
        csv_filepath = os.path.join(data_dir, csv_filename)
        csv_fullpath = os.path.abspath(csv_filepath)
        
        # Save chart as image before stopping
        graph_file = None
        if rack_key in self.rack_tabs:
            try:
                # Create timestamped filename for the graph
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                graph_filename = f"{rack_name}_power_{timestamp}.png"
                graph_filepath = os.path.join(data_dir, graph_filename)
                
                # Save the figure
                self.rack_tabs[rack_key]['figure'].savefig(graph_filepath)
                graph_file = os.path.abspath(graph_filepath)
                self.log_message(f"Saved graph image to {graph_filepath}")
            except Exception as e:
                self.log_message(f"Error saving graph image: {str(e)}", level="ERROR")
        
        # Stop the monitoring
        self._stop_rack_monitoring(rack_name, rack_address)
        
        # Show confirmation with file paths
        message = f"Monitoring for {rack_name} has been stopped.\n\n"
        message += f"Data saved to:\n{csv_fullpath}"
        
        if graph_file:
            message += f"\n\nGraph image saved to:\n{graph_file}"
        
        messagebox.showinfo("Monitoring Stopped", message)