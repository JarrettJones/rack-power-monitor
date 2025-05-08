from flask import Flask, render_template, jsonify
import threading
import webbrowser
import os

class WebMonitorServer:
    def __init__(self, app_instance, port=5000):
        """Initialize the web monitor server."""
        self.app = app_instance  # Main application instance
        self.port = port
        self.flask_app = Flask(__name__,
                              template_folder=os.path.join(os.path.dirname(__file__), 'web_templates'),
                              static_folder=os.path.join(os.path.dirname(__file__), 'web_static'))
        self.setup_routes()
        self.server_thread = None
        self.is_running = False
        
    def setup_routes(self):
        """Set up the Flask routes."""
        
        @self.flask_app.route('/')
        def index():
            # Example of properly formatting rack data
            racks = []
            
            # Check if monitoring_data attribute exists before trying to access it
            if not hasattr(self.app, 'monitoring_data'):
                self.app.monitoring_data = {}
            
            # Also ensure monitoring_tasks exists
            if not hasattr(self.app, 'monitoring_tasks'):
                self.app.monitoring_tasks = {}
            
            # Get rack data from either monitoring_data or rack_tabs
            data_source = {}
            if hasattr(self.app, 'monitor_tab') and hasattr(self.app.monitor_tab, 'rack_tabs'):
                data_source = self.app.monitor_tab.rack_tabs
            elif hasattr(self.app, 'monitoring_data') and self.app.monitoring_data:
                data_source = self.app.monitoring_data
            
            # Debug logging to see what's happening
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Found {len(data_source)} racks in data source")
            
            for rack_key, rack_data in data_source.items():
                try:
                    # Parse rack key (format typically: "name_address")
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
                            import datetime
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
                    
                    logger.info(f"Rack {name}: signals={signals}, status={status}")
                    
                    # Get statistics if available
                    stats = None
                    if 'data' in rack_data and rack_data['data']:
                        power_values = [entry[1] for entry in rack_data['data']]
                        if power_values:
                            current = power_values[-1]
                            
                            # Format mode if we have enough data
                            mode_text = None
                            if len(power_values) > 1:
                                from collections import Counter
                                rounded_values = [round(x, 2) for x in power_values]
                                value_counts = Counter(rounded_values)
                                most_common = value_counts.most_common(1)
                                if most_common and most_common[0][1] > 1:  # If count > 1
                                    mode_power, mode_count = most_common[0]
                                    mode_text = f"{mode_power:.2f} W ({mode_count} times)"
                            
                            stats = {
                                'current': f"{current:.2f} W",  # Format with units
                                'count': str(len(power_values)),
                                'mode': mode_text
                            }
                    
                    racks.append({
                        'name': name,
                        'address': address,
                        'status': status,
                        'stats': stats
                    })
                except Exception as e:
                    # Log the error but continue processing other racks
                    import logging
                    logging.error(f"Error processing rack {rack_key}: {e}")
                    import traceback
                    logging.error(traceback.format_exc())
            
            return render_template('index.html', racks=racks)
            
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
            data = []
            if hasattr(self.app, 'monitor_tab'):
                for rack_key, rack_data in self.app.monitor_tab.rack_tabs.items():
                    if rack_key.startswith(f"{rack_name}_"):
                        # Process the data to a format suitable for web display
                        timestamps = []
                        power_values = []
                        for point in rack_data.get('data', []):
                            timestamps.append(point[0].isoformat())
                            power_values.append(point[1])
                        data = {
                            'timestamps': timestamps,
                            'power': power_values,
                            'name': rack_name,
                            'min': min(power_values) if power_values else 0,
                            'max': max(power_values) if power_values else 0,
                            'avg': sum(power_values)/len(power_values) if power_values else 0
                        }
                        break
            return jsonify(data)
        
        @self.flask_app.route('/api/rack/<rack_name>/data')
        def rack_data(rack_name):
            # Find the rack in the app's data
            rack_data = None
            for rack_key, data in self.app.monitoring_data.items():
                if rack_name in rack_key:
                    rack_data = data
                    break
            
            if not rack_data:
                return jsonify({"error": "Rack not found"}), 404
            
            # Extract timestamps and power values
            timestamps = [entry[0] for entry in rack_data['data']]
            power = [entry[1] for entry in rack_data['data']]
            
            # Calculate statistics
            min_power = min(power) if power else 0
            max_power = max(power) if power else 0
            avg_power = sum(power) / len(power) if power else 0
            
            # Calculate mode (most frequent value)
            mode_power = None
            mode_count = 0
            
            if power:
                from collections import Counter
                # Round to 2 decimal places to handle floating point values
                rounded_values = [round(x, 2) for x in power]
                value_counts = Counter(rounded_values)
                
                # Get the most common value
                most_common = value_counts.most_common(1)
                if most_common:
                    mode_power, mode_count = most_common[0]
            
            # Return data as JSON
            return jsonify({
                "timestamps": timestamps,
                "power": power,
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
                import logging
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
                                import datetime
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
                            from collections import Counter
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