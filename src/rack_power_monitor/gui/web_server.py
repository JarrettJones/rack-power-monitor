from flask import Flask, render_template, jsonify
import threading
import webbrowser
import os
import logging
import traceback
import datetime
from collections import Counter

class WebMonitorServer:
    def __init__(self, app_instance, port=5000):
        """Initialize the web monitor server."""
        self.app = app_instance  # Main application instance
        self.port = port
        
        # Correct static folder path
        static_folder = os.path.join(os.path.dirname(__file__), 'web_static')
        template_folder = os.path.join(os.path.dirname(__file__), 'web_templates')
        
        # Ensure Flask knows where to find the static files
        self.flask_app = Flask(__name__,
                          template_folder=template_folder,
                          static_folder=static_folder,
                          static_url_path='/static')
    
        self.setup_routes()
        self.server_thread = None
        self.is_running = False
        
    def setup_routes(self):
        """Set up the Flask routes."""
        
        @self.flask_app.route('/')
        def index():
            # Set up empty rack lists
            active_racks = []
            standby_racks = []
            
            # Get data sources 
            data_source = {}
            if hasattr(self.app, 'monitor_tab') and hasattr(self.app.monitor_tab, 'rack_tabs'):
                data_source = self.app.monitor_tab.rack_tabs
            elif hasattr(self.app, 'monitoring_data') and self.app.monitoring_data:
                data_source = self.app.monitoring_data
            
            # Process each rack
            for rack_key, rack_data in data_source.items():
                # Parse rack name
                if '_' in rack_key:
                    name, address = rack_key.split('_', 1)
                else:
                    name = rack_key
                    address = "Unknown"
                
                # Multiple signals that a rack might be monitored
                signals = {
                    "has_monitor_task": False,
                    "has_monitor_object": False,
                    "has_data": False,
                    "in_notebook": False,
                    "recent_data": False
                }
                
                # Check for monitoring task
                if hasattr(self.app, 'monitoring_tasks') and rack_key in self.app.monitoring_tasks:
                    signals["has_monitor_task"] = True
                    if 'monitor' in self.app.monitoring_tasks[rack_key]:
                        signals["has_monitor_object"] = True
                
                # Check for data
                if 'data' in rack_data and rack_data['data']:
                    signals["has_data"] = True
                    
                    # Check if data is recent (last 5 minutes)
                    if len(rack_data['data']) > 0:
                        last_timestamp = rack_data['data'][-1][0]
                        if isinstance(last_timestamp, datetime.datetime):
                            time_diff = datetime.datetime.now() - last_timestamp
                            if time_diff.total_seconds() < 300:  # 5 minutes
                                signals["recent_data"] = True
                
                # Check if in notebook
                if 'added_to_notebook' in rack_data:
                    signals["in_notebook"] = rack_data['added_to_notebook']
                
                # Determine status based on signals
                status = "Not Monitoring"
                is_monitoring = (
                    (signals["has_monitor_task"] and signals["has_monitor_object"]) or
                    (signals["has_data"] and signals["in_notebook"]) or
                    signals["recent_data"] or
                    (signals["has_data"] and name == "G24")  # Special case for G24
                )
                
                if is_monitoring:
                    # Check if paused
                    is_paused = False
                    
                    # Check rack_data directly
                    if 'paused' in rack_data:
                        is_paused = rack_data['paused']
                    
                    # Check pause button state
                    elif 'controls' in rack_data and 'pause_var' in rack_data['controls']:
                        pause_text = rack_data['controls']['pause_var'].get()
                        is_paused = (pause_text == "Resume")
                    
                    # Also check monitoring_tasks
                    if not is_paused and hasattr(self.app, 'monitoring_tasks') and rack_key in self.app.monitoring_tasks:
                        if 'paused' in self.app.monitoring_tasks[rack_key]:
                            is_paused = self.app.monitoring_tasks[rack_key]['paused']
                    
                    status = "Paused" if is_paused else "Monitoring"
        
                # For active racks, calculate additional statistics
                if status == "Monitoring":
                    # Get power values from data
                    power_values = []
                    if 'data' in rack_data and rack_data['data']:
                        power_values = [entry[1] for entry in rack_data['data'] if isinstance(entry, (list, tuple)) and len(entry) > 1]
                    
                    # Calculate statistics
                    current_power = None
                    avg_power = None
                    count = len(power_values)
                    
                    if power_values:
                        current_power = f"{power_values[-1]:.2f} W"
                        avg_power = f"{sum(power_values) / count:.2f} W"
                    
                    # Add to active racks with stats
                    active_racks.append({
                        'name': name,
                        'address': address,
                        'status': status,
                        'stats': {
                            'current': current_power,
                            'avg': avg_power,
                            'count': count
                        }
                    })
                else:
                    # Add to the standby racks
                    standby_racks.append({
                        'name': name,
                        'address': address,
                        'status': status
                    })
        
            # Sort racks by name for consistent display
            active_racks.sort(key=lambda x: x['name'])
            standby_racks.sort(key=lambda x: x['name'])
            
            # Get counts for the tab headers
            active_count = len(active_racks)
            standby_count = len(standby_racks)
            
            # Return the template with all data
            return render_template('index.html', 
                                  active_racks=active_racks,
                                  standby_racks=standby_racks,
                                  active_count=active_count,
                                  standby_count=standby_count)
            
        @self.flask_app.route('/rack/<rack_name>')
        def rack_detail(rack_name):
            """Detail view for a specific rack."""
            return render_template('rack_detail.html', rack_name=rack_name)
            
        @self.flask_app.route('/api/racks')
        def api_racks():
            """API endpoint to get all racks."""
            rack_list = []
            if hasattr(self.app, 'monitor_tab'):
                for item_id in self.app.monitor_tab.rscm_tree.get_children():
                    item = self.app.monitor_tab.rscm_tree.item(item_id)
                    rack_list.append({
                        'name': item['values'][0],
                        'address': item['values'][1],
                        'status': item['values'][2]
                    })
            return jsonify(racks=rack_list)
            
        @self.flask_app.route('/api/rack/<rack_name>/data')
        def api_rack_data(rack_name):
            """API endpoint to get power data for a specific rack."""
            # Initialize response data
            timestamps = []
            power_values = []
            rack_data = None
            
            # First try monitor_tab.rack_tabs
            if hasattr(self.app, 'monitor_tab') and hasattr(self.app.monitor_tab, 'rack_tabs'):
                for rack_key, data in self.app.monitor_tab.rack_tabs.items():
                    if rack_name in rack_key and 'data' in data and data['data']:
                        rack_data = data
                        timestamps = [point[0].isoformat() if hasattr(point[0], 'isoformat') else str(point[0]) for point in data['data']]
                        power_values = [point[1] for point in data['data']]
                        break
            
            # If not found, then try monitoring_data
            if not power_values and hasattr(self.app, 'monitoring_data'):
                for rack_key, data in self.app.monitoring_data.items():
                    if rack_name in rack_key and 'data' in data and data['data']:
                        rack_data = data
                        timestamps = [point[0].isoformat() if hasattr(point[0], 'isoformat') else str(point[0]) for point in data['data']]
                        power_values = [point[1] for point in data['data']]
                        break
            
            # If still no data found, return an error
            if not power_values:
                return jsonify({"error": "No data available for rack"}), 404
            
            # Calculate statistics
            min_power = min(power_values) if power_values else 0
            max_power = max(power_values) if power_values else 0
            avg_power = sum(power_values) / len(power_values) if power_values else 0
            
            # Calculate mode (most frequent value)
            mode_power = None
            mode_count = 0
            
            try:
                # Round to 2 decimal places to handle floating point values
                rounded_values = [round(x, 2) for x in power_values]
                value_counts = Counter(rounded_values)
                
                # Get the most common value
                most_common = value_counts.most_common(1)
                if most_common:
                    mode_power, mode_count = most_common[0]
            except Exception as e:
                logging.warning(f"Failed to calculate mode: {str(e)}")
            
            # Return data as JSON
            return jsonify({
                "timestamps": timestamps,
                "power": power_values,
                "name": rack_name,
                "min": min_power,
                "max": max_power,
                "avg": avg_power,
                "mode": mode_power,
                "mode_count": mode_count,
            })
        
        @self.flask_app.route('/api/rack/<rack_name>/status')
        def get_rack_status(rack_name):
            """API endpoint to get current status and stats for a specific rack"""
            try:
                logger = logging.getLogger(__name__)
                
                # Initialize response
                rack_data = {
                    "name": rack_name,
                    "address": "Unknown",
                    "status": "Not Monitoring",
                    "stats": None
                }
                
                # Find the rack in data sources
                found_rack = False
                rack_key = None
                
                # Check monitoring_data first
                if hasattr(self.app, 'monitoring_data'):
                    # Try to find the matching rack by name
                    for key in self.app.monitoring_data.keys():
                        if rack_name in key:
                            rack_key = key
                            found_rack = True
                            if '_' in key:
                                _, address = key.split('_', 1)
                                rack_data['address'] = address
                            break
                
                # If not found in monitoring_data, try rack_tabs
                if not found_rack and hasattr(self.app, 'monitor_tab') and hasattr(self.app.monitor_tab, 'rack_tabs'):
                    for key in self.app.monitor_tab.rack_tabs.keys():
                        if rack_name in key:
                            rack_key = key
                            found_rack = True
                            if '_' in key:
                                _, address = key.split('_', 1)
                                rack_data['address'] = address
                            break
                
                if not found_rack:
                    logger.warning(f"Rack not found: {rack_name}")
                    return jsonify(rack_data), 404
                
                logger.info(f"Found rack: {rack_key}")
                
                # Determine status - UPDATED LOGIC
                status = "Not Monitoring"
                is_monitoring = False
                
                # Multiple signals that a rack might be monitored
                signals = {
                    "has_monitor_task": False,
                    "has_monitor_object": False,
                    "has_data": False,
                    "in_notebook": False,
                    "recent_data": False
                }
                
                # Check for monitoring task
                if hasattr(self.app, 'monitoring_tasks') and rack_key in self.app.monitoring_tasks:
                    signals["has_monitor_task"] = True
                    if 'monitor' in self.app.monitoring_tasks[rack_key]:
                        signals["has_monitor_object"] = True
                
                # Check for data
                data_source = None
                if hasattr(self.app, 'monitor_tab') and hasattr(self.app.monitor_tab, 'rack_tabs'):
                    if rack_key in self.app.monitor_tab.rack_tabs:
                        tab_data = self.app.monitor_tab.rack_tabs[rack_key]
                        
                        # Check if added to notebook
                        if 'added_to_notebook' in tab_data:
                            signals["in_notebook"] = tab_data['added_to_notebook']
                        
                        # Check if it has data
                        if 'data' in tab_data and tab_data['data']:
                            signals["has_data"] = True
                            
                            # Check if data is recent (last 5 minutes)
                            if len(tab_data['data']) > 0:
                                last_timestamp = tab_data['data'][-1][0]
                                if isinstance(last_timestamp, datetime.datetime):
                                    time_diff = datetime.datetime.now() - last_timestamp
                                    if time_diff.total_seconds() < 300:  # 5 minutes
                                        signals["recent_data"] = True
                        
                        data_source = tab_data
                
                # Also check monitoring_data
                if not data_source and hasattr(self.app, 'monitoring_data'):
                    if rack_key in self.app.monitoring_data:
                        md_data = self.app.monitoring_data[rack_key]
                        if 'data' in md_data and md_data['data']:
                            signals["has_data"] = True
                            data_source = md_data
                
                # Log the signals we found
                logger.info(f"Monitoring signals for {rack_name}: {signals}")
                
                # Determine if monitoring based on signals
                # We consider a rack monitored if:
                # 1. It has a monitor task and object, OR
                # 2. It has data AND is in the notebook, OR
                # 3. It has recent data
                is_monitoring = (
                    (signals["has_monitor_task"] and signals["has_monitor_object"]) or
                    (signals["has_data"] and signals["in_notebook"]) or
                    signals["recent_data"] or
                    (signals["has_data"] and rack_name == "G24")  # Special case for G24
                )
                
                if is_monitoring:
                    # Check if paused
                    is_paused = False
                    
                    if hasattr(self.app, 'monitor_tab') and hasattr(self.app.monitor_tab, 'rack_tabs'):
                        if rack_key in self.app.monitor_tab.rack_tabs:
                            tab_data = self.app.monitor_tab.rack_tabs[rack_key]
                            
                            # Check for explicit paused flag
                            if 'paused' in tab_data:
                                is_paused = tab_data['paused']
                            
                            # Check pause button state
                            elif 'controls' in tab_data and 'pause_var' in tab_data['controls']:
                                pause_text = tab_data['controls']['pause_var'].get()
                                is_paused = (pause_text == "Resume")
                    
                    # Also check monitoring_tasks
                    if hasattr(self.app, 'monitoring_tasks') and rack_key in self.app.monitoring_tasks:
                        if 'paused' in self.app.monitoring_tasks[rack_key]:
                            is_paused = self.app.monitoring_tasks[rack_key]['paused']
                    
                    status = "Paused" if is_paused else "Monitoring"
                
                logger.info(f"Rack {rack_name} final status: {status} (is_monitoring={is_monitoring})")
                rack_data['status'] = status
                
                # Get statistics if we have data
                if data_source and 'data' in data_source and data_source['data']:
                    power_values = [entry[1] for entry in data_source['data']]
                    
                    if power_values:
                        current = power_values[-1]
                        
                        # Format mode if we have enough data
                        mode_text = None
                        if len(power_values) > 1:
                            rounded_values = [round(x, 2) for x in power_values]
                            value_counts = Counter(rounded_values)
                            most_common = value_counts.most_common(1)
                            if most_common and most_common[0][1] > 1:
                                mode_power, mode_count = most_common[0]
                                mode_text = f"{mode_power:.2f} W ({mode_count} times)"
                        
                        rack_data['stats'] = {
                            'current': f"{current:.2f} W",
                            'count': str(len(power_values)),
                            'mode': mode_text
                        }
                        logger.info(f"Rack {rack_name}: has stats with current={rack_data['stats']['current']}")
                
                return jsonify(rack_data)
                
            except Exception as e:
                import logging, traceback
                logging.error(f"Error in get_rack_status for {rack_name}: {str(e)}")
                logging.error(traceback.format_exc())
                return jsonify({"error": str(e)}), 500
        
        @self.flask_app.route('/api/racks/active')
        def api_active_racks():
            """API endpoint to get active racks only."""
            active_racks = []
            
            # Use the same logic as the index route to determine active racks
            data_source = {}
            if hasattr(self.app, 'monitor_tab') and hasattr(self.app.monitor_tab, 'rack_tabs'):
                data_source = self.app.monitor_tab.rack_tabs
            elif hasattr(self.app, 'monitoring_data') and self.app.monitoring_data:
                data_source = self.app.monitoring_data
            
            for rack_key, rack_data in data_source.items():
                try:
                    # Parse rack name and address
                    if '_' in rack_key:
                        name, address = rack_key.split('_', 1)
                    else:
                        name = rack_key
                        address = "Unknown"
                    
                    # Determine if active using the same monitoring signals
                    is_monitoring = False
                    status = "Not Monitoring"
                    
                    # Check for monitoring task
                    if hasattr(self.app, 'monitoring_tasks') and rack_key in self.app.monitoring_tasks:
                        has_task = True
                        has_monitor = 'monitor' in self.app.monitoring_tasks[rack_key]
                        
                        if has_task and has_monitor:
                            is_monitoring = True
                    
                    # Check for recent data
                    if 'data' in rack_data and rack_data['data']:
                        has_data = True
                        
                        # Special case for G24
                        if name == "G24" and has_data:
                            is_monitoring = True
                        
                        # Check if in notebook
                        if 'added_to_notebook' in rack_data and rack_data['added_to_notebook'] and has_data:
                            is_monitoring = True
                        
                        # Check if data is recent (last 5 minutes)
                        if len(rack_data['data']) > 0:
                            last_timestamp = rack_data['data'][-1][0]
                            if isinstance(last_timestamp, datetime.datetime):
                                time_diff = datetime.datetime.now() - last_timestamp
                                if time_diff.total_seconds() < 300:  # 5 minutes
                                    is_monitoring = True
                
                    if is_monitoring:
                        # Check if paused
                        is_paused = False
                        
                        if 'paused' in rack_data:
                            is_paused = rack_data['paused']
                        elif 'controls' in rack_data and 'pause_var' in rack_data['controls']:
                            pause_text = rack_data['controls']['pause_var'].get()
                            is_paused = (pause_text == "Resume")
                        elif hasattr(self.app, 'monitoring_tasks') and rack_key in self.app.monitoring_tasks:
                            if 'paused' in self.app.monitoring_tasks[rack_key]:
                                is_paused = self.app.monitoring_tasks[rack_key]['paused']
                        
                        status = "Paused" if is_paused else "Monitoring"
                        
                        # Only add if actually monitoring (not paused)
                        if status == "Monitoring":
                            # Get current power if available
                            current_power = None
                            if 'data' in rack_data and rack_data['data']:
                                power_values = [entry[1] for entry in rack_data['data']]
                                if power_values:
                                    current_power = f"{power_values[-1]:.2f} W"
                            
                            active_racks.append({
                                'name': name,
                                'address': address,
                                'status': status,
                                'current_power': current_power
                            })
                        
                except Exception as e:
                    logging.error(f"Error in api_active_racks for rack {rack_key}: {e}")
            
            return jsonify({"active_racks": active_racks})
        
        @self.flask_app.route('/api/racks/standby')
        def api_standby_racks():
            """API endpoint to get standby racks only."""
            # Similar to active but returns racks that are not monitoring or are paused
            standby_racks = []
            
            # Get data sources
            data_source = {}
            if hasattr(self.app, 'monitor_tab') and hasattr(self.app.monitor_tab, 'rack_tabs'):
                data_source = self.app.monitor_tab.rack_tabs
            elif hasattr(self.app, 'monitoring_data') and self.app.monitoring_data:
                data_source = self.app.monitoring_data
            
            # Process each rack
            for rack_key, rack_data in data_source.items():
                try:
                    # Parse rack name
                    if '_' in rack_key:
                        name, address = rack_key.split('_', 1)
                    else:
                        name = rack_key
                        address = "Unknown"
                    
                    # Determine if monitoring using same logic as before
                    is_monitoring = False
                    has_task = hasattr(self.app, 'monitoring_tasks') and rack_key in self.app.monitoring_tasks
                    has_monitor = has_task and 'monitor' in self.app.monitoring_tasks[rack_key]
                    has_data = 'data' in rack_data and rack_data['data']
                    in_notebook = 'added_to_notebook' in rack_data and rack_data['added_to_notebook']
                    
                    # Check for recent data
                    has_recent_data = False
                    if has_data and rack_data['data']:
                        last_timestamp = rack_data['data'][-1][0]
                        if isinstance(last_timestamp, datetime.datetime):
                            time_diff = datetime.datetime.now() - last_timestamp
                            if time_diff.total_seconds() < 300:
                                has_recent_data = True
                    
                    # Determine monitoring state
                    is_monitoring = (
                        (has_task and has_monitor) or
                        (has_data and in_notebook) or
                        has_recent_data or
                        (has_data and name == "G24")
                    )
                    
                    # Check if paused
                    is_paused = False
                    if 'paused' in rack_data:
                        is_paused = rack_data['paused']
                    elif 'controls' in rack_data and 'pause_var' in rack_data['controls']:
                        pause_text = rack_data['controls']['pause_var'].get()
                        is_paused = (pause_text == "Resume")
                    elif has_task and 'paused' in self.app.monitoring_tasks[rack_key]:
                        is_paused = self.app.monitoring_tasks[rack_key]['paused']
                    
                    # Only add if not actively monitoring (either not monitoring at all or paused)
                    if not is_monitoring or is_paused:
                        # Get last power reading if available
                        last_power = None
                        if has_data and rack_data['data']:
                            power_values = [entry[1] for entry in rack_data['data']]
                            if power_values:
                                last_power = f"{power_values[-1]:.2f} W"
                        
                        status = "Paused" if (is_monitoring and is_paused) else "Not Monitoring"
                        
                        standby_racks.append({
                            'name': name,
                            'address': address,
                            'status': status,
                            'last_power': last_power
                        })
        
                except Exception as e:
                    logging.error(f"Error in api_standby_racks for rack {rack_key}: {e}")
            
            return jsonify({"standby_racks": standby_racks})


    def start(self):
        """Start the web server in a separate thread."""
        if self.is_running:
            return
            
        def run_server():
            # '0.0.0.0' binds to all network interfaces
            self.flask_app.run(host='0.0.0.0', port=self.port, debug=False)
            
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        self.is_running = True
    
        # Display the actual IP address for easier access
        import socket
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        print(f"Web monitoring server started")
        print(f"Access locally: http://localhost:{self.port}")
        print(f"Access from network: http://{local_ip}:{self.port}")
        
    def stop(self):
        """Stop the web server."""
        # Flask doesn't have a clean shutdown mechanism when run in a thread
        # In a production app, you would use a proper WSGI server like Waitress or Gunicorn
        self.is_running = False
        # The thread will be terminated when the main app exits
        
    def open_browser(self):
        """Open the web interface in the default browser."""
        webbrowser.open(f"http://localhost:{self.port}")