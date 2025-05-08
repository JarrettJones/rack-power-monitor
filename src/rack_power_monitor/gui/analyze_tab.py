import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd
import numpy as np
import os
import datetime
import logging
from datetime import timedelta
from matplotlib.dates import DateFormatter

logger = logging.getLogger("power_monitor")

class AnalyzeTab(ttk.Frame):
    """Analyze tab for the application."""
    
    def __init__(self, parent, app):
        """Initialize the analyze tab."""
        super().__init__(parent)
        self.app = app
        self.data = None
        self.current_file = None
        
        # Set up UI components
        self._init_ui()
        
        # Initialize empty chart
        self._create_empty_chart()
        
    def _init_ui(self):
        """Initialize the UI components."""
        # Configure grid for main frame
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)  # Controls area
        self.rowconfigure(1, weight=1)  # Chart area
        self.rowconfigure(2, weight=0)  # Statistics area
        
        # === Controls Area ===
        controls_frame = ttk.LabelFrame(self, text="Data Controls")
        controls_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        
        # Configure controls grid
        controls_frame.columnconfigure(0, weight=0)
        controls_frame.columnconfigure(1, weight=1)
        controls_frame.columnconfigure(2, weight=0)
        controls_frame.columnconfigure(3, weight=0)
        controls_frame.columnconfigure(4, weight=0)
        
        # File selection
        ttk.Label(controls_frame, text="Data File:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.file_path_var = tk.StringVar()
        file_entry = ttk.Entry(controls_frame, textvariable=self.file_path_var, width=50)
        file_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        
        ttk.Button(controls_frame, text="Browse...", command=self._browse_file).grid(
            row=0, column=2, sticky="w", padx=5, pady=5)
        
        # Time range selector
        ttk.Label(controls_frame, text="Time Range:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        
        time_range_frame = ttk.Frame(controls_frame)
        time_range_frame.grid(row=1, column=1, columnspan=2, sticky="w", padx=5, pady=5)
        
        # Quick time buttons
        ttk.Button(time_range_frame, text="All Data", command=lambda: self._set_time_range("all")).pack(
            side=tk.LEFT, padx=5)
        ttk.Button(time_range_frame, text="Last Hour", command=lambda: self._set_time_range("hour")).pack(
            side=tk.LEFT, padx=5)
        ttk.Button(time_range_frame, text="Last Day", command=lambda: self._set_time_range("day")).pack(
            side=tk.LEFT, padx=5)
        ttk.Button(time_range_frame, text="Last Week", command=lambda: self._set_time_range("week")).pack(
            side=tk.LEFT, padx=5)
        
        # Load and refresh buttons
        ttk.Button(controls_frame, text="Load Data", command=self._load_data).grid(
            row=0, column=3, sticky="w", padx=5, pady=5)
        ttk.Button(controls_frame, text="Refresh", command=self._refresh_chart).grid(
            row=1, column=3, sticky="w", padx=5, pady=5)
        
        # === Chart Area ===
        self.chart_frame = ttk.LabelFrame(self, text="Power Usage Chart")
        self.chart_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        
        # Configure chart frame
        self.chart_frame.columnconfigure(0, weight=1)
        self.chart_frame.rowconfigure(0, weight=1)
        
        # === Statistics Area ===
        stats_frame = ttk.LabelFrame(self, text="Statistics")
        stats_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        
        # Configure stats frame grid
        stats_frame.columnconfigure(0, weight=1)
        stats_frame.columnconfigure(1, weight=1)
        stats_frame.columnconfigure(2, weight=1)
        stats_frame.columnconfigure(3, weight=1)
        stats_frame.columnconfigure(4, weight=1)
        
        # Statistics labels
        ttk.Label(stats_frame, text="Data Points:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.data_points_var = tk.StringVar(value="0")
        ttk.Label(stats_frame, textvariable=self.data_points_var).grid(row=1, column=0, padx=5, pady=5)
        
        ttk.Label(stats_frame, text="Average Power:").grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.avg_power_var = tk.StringVar(value="0 W")
        ttk.Label(stats_frame, textvariable=self.avg_power_var).grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(stats_frame, text="Min Power:").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.min_power_var = tk.StringVar(value="0 W")
        ttk.Label(stats_frame, textvariable=self.min_power_var).grid(row=1, column=2, padx=5, pady=5)
        
        ttk.Label(stats_frame, text="Max Power:").grid(row=0, column=3, padx=5, pady=5, sticky="w")
        self.max_power_var = tk.StringVar(value="0 W")
        ttk.Label(stats_frame, textvariable=self.max_power_var).grid(row=1, column=3, padx=5, pady=5)
        
        ttk.Label(stats_frame, text="Time Range:").grid(row=0, column=4, padx=5, pady=5, sticky="w")
        self.time_range_var = tk.StringVar(value="N/A")
        ttk.Label(stats_frame, textvariable=self.time_range_var).grid(row=1, column=4, padx=5, pady=5)
        
    def _create_empty_chart(self):
        """Create an empty chart as a placeholder."""
        # Create figure and add to UI
        self.figure = Figure(figsize=(8, 4), dpi=100)
        self.figure.subplots_adjust(left=0.1, right=0.95, top=0.95, bottom=0.15)
        self.ax = self.figure.add_subplot(111)
        
        # Set up labels and grid
        self.ax.set_title("Power Usage Over Time")
        self.ax.set_xlabel("Time")
        self.ax.set_ylabel("Power (W)")
        self.ax.grid(True)
        
        # Add "No data loaded" text
        self.ax.text(0.5, 0.5, "No data loaded\nUse 'Browse...' to select a data file", 
                    horizontalalignment='center', verticalalignment='center',
                    transform=self.ax.transAxes, fontsize=14)
        
        # Create canvas
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.chart_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.grid(row=0, column=0, sticky="nsew")
        
    def _browse_file(self):
        """Open file browser to select a CSV data file."""
        # Try to get the data directory from app config
        initial_dir = self.app.config.get('data_dir', os.path.join(os.getcwd(), "power_data"))
        if not os.path.isdir(initial_dir):
            initial_dir = os.getcwd()
            
        file_path = filedialog.askopenfilename(
            title="Select Power Data File",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            initialdir=initial_dir
        )
        
        if file_path:
            self.file_path_var.set(file_path)
            self._load_data()
            
    def _load_data(self):
        """Load data from the selected file."""
        file_path = self.file_path_var.get()
        
        if not file_path or not os.path.isfile(file_path):
            messagebox.showerror("Error", "Please select a valid data file")
            return
            
        try:
            # Load data from CSV
            df = pd.read_csv(file_path)
            logger.info(f"Loaded CSV with columns: {df.columns.tolist()}")
            
            # Check for various possible column name formats
            timestamp_candidates = ['timestamp', 'Timestamp', 'TIMESTAMP', 'time', 'Time']
            power_candidates = ['power', 'Power', 'POWER', 'power (w)', 'Power (W)', 'POWER (W)']
            
            # Find matching columns
            timestamp_col = None
            for col in timestamp_candidates:
                if col in df.columns:
                    timestamp_col = col
                    break
                    
            power_col = None
            for col in power_candidates:
                if col in df.columns:
                    power_col = col
                    break
            
            # If we found the columns, rename them to our standard format
            if timestamp_col and power_col:
                # Create a rename mapping
                rename_map = {}
                if timestamp_col != 'timestamp':
                    rename_map[timestamp_col] = 'timestamp'
                if power_col != 'power':
                    rename_map[power_col] = 'power'
                    
                # Rename if needed
                if rename_map:
                    df = df.rename(columns=rename_map)
                
                logger.info(f"Using columns: timestamp={timestamp_col}, power={power_col}")
            else:
                # No matching columns found
                messagebox.showerror("Format Error", 
                                  "CSV file must have columns for timestamp and power.\n"
                                  f"Found columns: {', '.join(df.columns)}")
                return
            
            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Set as current data
            self.data = df
            self.current_file = os.path.basename(file_path)
            
            # Update chart
            self._refresh_chart()
            
            # Update statistics
            self._update_statistics()
            
            logger.info(f"Successfully loaded data file: {file_path} with {len(df)} rows")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load data: {str(e)}")
            logger.error(f"Error loading data file: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
    def _set_time_range(self, range_type):
        """Set the time range for filtering data."""
        if self.data is None or len(self.data) == 0:
            return
            
        now = datetime.datetime.now()
        min_time = self.data['timestamp'].min()
        max_time = self.data['timestamp'].max()
        
        if range_type == "all":
            # Use full range
            pass
        elif range_type == "hour":
            min_time = max_time - timedelta(hours=1)
        elif range_type == "day":
            min_time = max_time - timedelta(days=1)
        elif range_type == "week":
            min_time = max_time - timedelta(weeks=1)
            
        # Filter data by time range
        self.data_filtered = self.data[
            (self.data['timestamp'] >= min_time) & 
            (self.data['timestamp'] <= max_time)
        ]
        
        # Update chart and statistics
        self._refresh_chart()
        self._update_statistics()
            
    def _refresh_chart(self):
        """Refresh the chart with current data."""
        if self.data is None or len(self.data) == 0:
            return
            
        # Clear the chart
        self.ax.clear()
        
        # Set up filtered data if not already done
        if not hasattr(self, 'data_filtered') or self.data_filtered is None:
            self.data_filtered = self.data
            
        # Plot the data
        self.ax.plot(self.data_filtered['timestamp'], self.data_filtered['power'], 
                    marker='.', linestyle='-', color='blue', alpha=0.7, linewidth=1)
        
        # Format the x-axis
        if len(self.data_filtered) > 0:
            time_range = (self.data_filtered['timestamp'].max() - self.data_filtered['timestamp'].min()).total_seconds()
            if time_range < 3600:  # Less than an hour
                date_format = DateFormatter('%H:%M:%S')
            elif time_range < 86400:  # Less than a day
                date_format = DateFormatter('%H:%M')
            else:  # More than a day
                date_format = DateFormatter('%m-%d %H:%M')
                
            self.ax.xaxis.set_major_formatter(date_format)
            self.ax.figure.autofmt_xdate()
            
        # Update chart title
        if self.current_file:
            self.ax.set_title(f"Power Usage - {self.current_file}")
        else:
            self.ax.set_title("Power Usage Over Time")
            
        # Set up labels and grid
        self.ax.set_xlabel("Time")
        self.ax.set_ylabel("Power (W)")
        self.ax.grid(True)
        
        # Update the canvas
        self.canvas.draw()
        
    def _update_statistics(self):
        """Update statistics from the current dataset."""
        if not hasattr(self, 'data_filtered') or self.data_filtered is None or len(self.data_filtered) == 0:
            return
            
        # Calculate statistics
        count = len(self.data_filtered)
        avg_power = self.data_filtered['power'].mean()
        min_power = self.data_filtered['power'].min()
        max_power = self.data_filtered['power'].max()
        
        # Calculate time range
        min_time = self.data_filtered['timestamp'].min()
        max_time = self.data_filtered['timestamp'].max()
        time_range_str = f"{min_time.strftime('%m-%d %H:%M')} to {max_time.strftime('%m-%d %H:%M')}"
        
        # Update UI
        self.data_points_var.set(f"{count:,}")
        self.avg_power_var.set(f"{avg_power:.2f} W")
        self.min_power_var.set(f"{min_power:.2f} W")
        self.max_power_var.set(f"{max_power:.2f} W")
        self.time_range_var.set(time_range_str)