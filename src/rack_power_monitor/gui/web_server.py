from flask import Flask, render_template, jsonify, request
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
            """Main index page that shows all racks."""
            # Get rack information as you currently do
            all_racks = []
            if hasattr(self.app, 'get_all_racks'):
                all_racks = self.app.get_all_racks()
            
            # Enhance rack data with stats from existing API
            for rack in all_racks:
                try:
                    # Use your existing endpoint logic to get stats
                    rack_name = rack['name']
                    rack_key = f"{rack_name}_{rack['address']}"
                    
                    # Initialize stats
                    rack['stats'] = {
                        'current': None,
                        'avg': None,
                        'count': '0'
                    }
                    
                    # Check if we have stats in rack_tabs
                    if hasattr(self.app, 'monitor_tab') and hasattr(self.app.monitor_tab, 'rack_tabs'):
                        if rack_key in self.app.monitor_tab.rack_tabs:
                            tab_data = self.app.monitor_tab.rack_tabs[rack_key]
                            
                            # Get power data points
                            if 'data' in tab_data and tab_data['data']:
                                power_values = [entry[1] for entry in tab_data['data']]
                                
                                if power_values:
                                    # Current power (last reading)
                                    rack['stats']['current'] = f"{power_values[-1]:.2f} W"
                                    
                                    # Average
                                    avg = sum(power_values) / len(power_values)
                                    rack['stats']['avg'] = f"{avg:.2f} W"
                                    
                                    # Count
                                    rack['stats']['count'] = str(len(power_values))
                except Exception as e:
                    import logging
                    logging.error(f"Error enhancing rack data for {rack['name']}: {str(e)}")
            
            # Separate into active and standby
            active_racks = []
            standby_racks = []
            
            for rack in all_racks:
                # Only consider "Monitoring" as active, all other statuses go to standby
                if rack['status'] == "Monitoring":
                    # Add to active_racks
                    active_racks.append(rack)
                else:
                    # Add to standby_racks
                    standby_racks.append(rack)
            
            # Sort racks by name for consistent display
            active_racks.sort(key=lambda x: x['name'])
            standby_racks.sort(key=lambda x: x['name'])
            
            # Get saved data files for the Saved Data tab
            saved_racks = []
            
            try:
                import os
                power_data_dir = os.path.join(os.getcwd(), 'power_data')
                
                if os.path.isdir(power_data_dir):
                    # Get all CSV files
                    csv_files = []
                    for filename in os.listdir(power_data_dir):
                        filepath = os.path.join(power_data_dir, filename)
                        if os.path.isfile(filepath) and filename.endswith('.csv'):
                            # Try to extract rack name from filename
                            rack_name = 'Unknown'
                            parts = filename.split('_')
                            if len(parts) > 0:
                                rack_name = parts[0]
                                
                            csv_files.append({
                                'name': filename,
                                'path': filepath,
                                'size': os.path.getsize(filepath),
                                'modified': os.path.getmtime(filepath),
                                'rack_name': rack_name
                            })
                
                # Group files by rack name
                racks_dict = {}
                for file_info in csv_files:
                    rack_name = file_info['rack_name']
                    if rack_name not in racks_dict:
                        racks_dict[rack_name] = {
                            'name': rack_name,
                            'csv_files': []
                        }
                    racks_dict[rack_name]['csv_files'].append(file_info)
                
                # Sort files by modification time (newest first)
                for rack_name, rack_info in racks_dict.items():
                    rack_info['csv_files'].sort(key=lambda x: x['modified'], reverse=True)
                
                # Convert to list and sort by rack name
                saved_racks = list(racks_dict.values())
                saved_racks.sort(key=lambda x: x['name'])
            except Exception as e:
                import logging
                logging.error(f"Error getting saved data files: {str(e)}")
            
            # Get counts for the tab headers
            active_count = len(active_racks)
            standby_count = len(standby_racks)
            
            # Return the template with all data
            return render_template('index.html', 
                                  active_racks=active_racks,
                                  standby_racks=standby_racks,
                                  all_racks=all_racks,
                                  saved_racks=saved_racks,
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
        
        # Add these routes to your Flask app

        @self.flask_app.route('/api/rscm/add', methods=['POST'])
        def add_rscm():
            """Add a new R-SCM device."""
            try:
                rack_name = request.form.get('rack_name')
                ip_address = request.form.get('ip_address')
                username = request.form.get('username') or None
                password = request.form.get('password') or None
                auto_monitor = request.form.get('auto_monitor') == 'true'
                poll_rate = int(request.form.get('poll_rate', 60))
                
                # Validation
                if not rack_name or not ip_address:
                    return jsonify({"success": False, "message": "Rack name and IP address are required"})
                
                # Add to the main application
                if hasattr(self.app, 'add_rscm'):
                    success = self.app.add_rscm(rack_name, ip_address, username, password, auto_monitor, poll_rate)
                    if success:
                        return jsonify({"success": True, "message": "R-SCM added successfully"})
                    else:
                        return jsonify({"success": False, "message": "Failed to add R-SCM (already exists or invalid data)"})
                else:
                    return jsonify({"success": False, "message": "R-SCM management not available in this application"})
            
            except Exception as e:
                self.app.logger.error(f"Error adding R-SCM: {str(e)}")
                return jsonify({"success": False, "message": f"Error: {str(e)}"})

        @self.flask_app.route('/api/rscm/update', methods=['POST'])
        def update_rscm():
            """Update an existing R-SCM device."""
            try:
                original_rack_name = request.form.get('original_rack_name')
                rack_name = request.form.get('rack_name')
                ip_address = request.form.get('ip_address')
                
                print(f"Update request: Original={original_rack_name}, New={rack_name}, IP={ip_address}")
                
                # Call the app method with the original rack name
                if hasattr(self.app, 'update_rscm'):
                    success = self.app.update_rscm(original_rack_name, rack_name, ip_address)
                    print(f"Update result: {success}")
                    return jsonify({
                        'success': success,
                        'message': 'R-SCM updated successfully' if success else 'Failed to update R-SCM'
                    })
                else:
                    print("Application doesn't have update_rscm method")
                    return jsonify({
                        'success': False,
                        'message': 'The application does not support updating R-SCMs'
                    })
            except Exception as e:
                print(f"Error in update_rscm: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Error: {str(e)}'
                })

        @self.flask_app.route('/api/rscm/delete/<rack_name>', methods=['POST'])
        def delete_rscm(rack_name):
            """Delete an R-SCM device."""
            try:
                # Delete from the main application
                if hasattr(self.app, 'delete_rscm'):
                    success = self.app.delete_rscm(rack_name)
                    if success:
                        return jsonify({"success": True, "message": "R-SCM deleted successfully"})
                    else:
                        return jsonify({"success": False, "message": "Failed to delete R-SCM (not found)"})
                else:
                    return jsonify({"success": False, "message": "R-SCM management not available in this application"})
            
            except Exception as e:
                self.app.logger.error(f"Error deleting R-SCM: {str(e)}")
                return jsonify({"success": False, "message": f"Error: {str(e)}"})

        @self.flask_app.route('/api/rscm/start/<rack_name>', methods=['POST'])
        def start_monitoring(rack_name):
            """Start monitoring for an R-SCM."""
            try:
                if hasattr(self.app, 'start_monitoring'):
                    success = self.app.start_monitoring(rack_name)
                    if success:
                        return jsonify({"success": True, "message": "Monitoring started"})
                    else:
                        return jsonify({"success": False, "message": "Failed to start monitoring"})
                else:
                    return jsonify({"success": False, "message": "Monitoring control not available"})
            
            except Exception as e:
                self.app.logger.error(f"Error starting monitoring: {str(e)}")
                return jsonify({"success": False, "message": f"Error: {str(e)}"})

        @self.flask_app.route('/api/rscm/pause/<rack_name>', methods=['POST'])
        def pause_rack_monitoring(rack_name):
            """Pause monitoring for a specific rack."""
            try:
                # Check if we have a monitor_tab to work with
                if hasattr(self.app, 'monitor_tab') and hasattr(self.app.monitor_tab, '_stop_rack_monitoring'):
                    # First get the rack address - needed for _stop_rack_monitoring
                    rack_address = None
                    
                    # Find the rack in the tree to get its address
                    for item_id in self.app.monitor_tab.rscm_tree.get_children():
                        item = self.app.monitor_tab.rscm_tree.item(item_id)
                        if item['values'][0] == rack_name:
                            rack_address = item['values'][1]
                            break
                    
                    if not rack_address:
                        return jsonify({
                            'success': False,
                            'message': f'Rack {rack_name} not found'
                        })
                    
                    # Try to get the actual saved filename before stopping
                    saved_file = None
                    
                    # Check if the monitor has an active session and stored filename
                    if hasattr(self.app.monitor_tab, 'active_monitors') and rack_name in self.app.monitor_tab.active_monitors:
                        monitor_obj = self.app.monitor_tab.active_monitors[rack_name]
                        if hasattr(monitor_obj, 'last_saved_file'):
                            saved_file = monitor_obj.last_saved_file
                    
                    # Use the same method used in the GUI
                    logging.info(f"Calling _stop_rack_monitoring for {rack_name} at {rack_address}")
                    self.app.monitor_tab._stop_rack_monitoring(rack_name, rack_address)
                    logging.info(f"Successfully stopped monitoring for {rack_name}")
                    
                    # If we couldn't get the actual filename, generate one that follows the same pattern
                    if not saved_file:
                        from datetime import datetime
                        now = datetime.now()
                        session_id = now.strftime("%Y%m%d_%H%M%S")
                        saved_file = f"{rack_name}_{session_id}.csv"
                    
                    return jsonify({
                        'success': True,
                        'message': 'Monitoring paused',
                        'saved_file': saved_file
                    })
                else:
                    logging.error("Monitoring functionality not available")
                    return jsonify({
                        'success': False,
                        'message': 'Monitoring functionality not available'
                    })
            except Exception as e:
                logging.error(f"Error pausing monitoring: {str(e)}")
                import traceback
                logging.error(traceback.format_exc())
                return jsonify({
                    'success': False,
                    'message': f'Error: {str(e)}'
                })

        @self.flask_app.route('/api/rscm/info/<rack_name>')
        def get_rscm_info(rack_name):
            """Get information about a specific R-SCM."""
            try:
                if hasattr(self.app, 'get_rscm_info'):
                    rscm_info = self.app.get_rscm_info(rack_name)
                    if rscm_info:
                        return jsonify({"success": True, "rscm": rscm_info})
                    else:
                        return jsonify({"success": False, "message": "R-SCM not found"})
                else:
                    return jsonify({"success": False, "message": "R-SCM information not available"})
            
            except Exception as e:
                self.app.logger.error(f"Error getting R-SCM info: {str(e)}")
                return jsonify({"success": False, "message": f"Error: {str(e)}"})
        
        # Add or update this route in your WebMonitorServer class setup_routes method
        @self.flask_app.route('/api/rscm/<rack_name>', methods=['GET'])
        def get_rscm(rack_name):
            """Get details for a specific R-SCM."""
            try:
                # URL decode the rack name (important for names with spaces)
                import urllib.parse
                decoded_name = urllib.parse.unquote(rack_name)
                
                # Get RSCM details from the app
                if hasattr(self.app, 'get_rscm_info'):
                    rscm_info = self.app.get_rscm_info(decoded_name)
                    if rscm_info:
                        return jsonify({
                            'success': True,
                            'rscm': rscm_info
                        })
                    else:
                        return jsonify({
                            'success': False,
                            'message': f'R-SCM {decoded_name} not found'
                        })
                else:
                    return jsonify({
                        'success': False,
                        'message': 'The application does not support retrieving R-SCM details'
                    })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'Error: {str(e)}'
                })
        
        @self.flask_app.route('/api/debug/status', methods=['GET'])
        def debug_status():
            """Debug endpoint to get detailed status information."""
            try:
                result = {
                    'tree_status': [],
                    'monitoring_tasks': [],
                    'rack_tabs': []
                }
                
                # Get tree status
                if hasattr(self.app, 'monitor_tab'):
                    for item_id in self.app.monitor_tab.rscm_tree.get_children():
                        item = self.app.monitor_tab.rscm_tree.item(item_id)
                        result['tree_status'].append({
                            'rack_name': item['values'][0],
                            'ip_address': item['values'][1],
                            'status': item['values'][2]
                        })
                    
                    # Get monitoring tasks
                    if hasattr(self.app.monitor_tab, 'monitoring_tasks'):
                        for key, value in self.app.monitor_tab.monitoring_tasks.items():
                            result['monitoring_tasks'].append({
                                'key': key,
                                'stop_flag': value.get('stop_flag', False) if isinstance(value, dict) else 'unknown'
                            })
                    
                    # Get rack tabs
                    if hasattr(self.app.monitor_tab, 'rack_tabs'):
                        for key in self.app.monitor_tab.rack_tabs.keys():
                            result['rack_tabs'].append(key)
                
                return jsonify({
                    'success': True,
                    'debug_info': result
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'Error retrieving debug info: {str(e)}'
                })
        
        @self.flask_app.route('/api/debug/monitor-status', methods=['GET'])
        def debug_monitor_status():
            """Get debug information about the monitoring status."""
            try:
                status = {
                    'monitor_tab_exists': False,
                    'active_monitors': [],
                    'save_data_enabled': False,
                    'power_data_dir_exists': False,
                    'power_data_dir_path': '',
                    'recent_files': []
                }
                
                # Check if monitor_tab exists
                if hasattr(self.app, 'monitor_tab'):
                    status['monitor_tab_exists'] = True
                    
                    # Check if save_data flag is enabled
                    if hasattr(self.app.monitor_tab, 'save_data'):
                        status['save_data_enabled'] = self.app.monitor_tab.save_data
                    
                    # Check for active monitors
                    if hasattr(self.app.monitor_tab, 'active_monitors'):
                        active = self.app.monitor_tab.active_monitors
                        if active:
                            for rack, monitor in active.items():
                                status['active_monitors'].append({
                                    'rack': rack,
                                    'started': str(monitor.get('started', 'unknown')),
                                    'save_enabled': monitor.get('save', False)
                                })
                
                # Check power_data directory
                import os
                power_data_dir = os.path.join(os.getcwd(), 'power_data')
                status['power_data_dir_path'] = power_data_dir
                
                if os.path.exists(power_data_dir):
                    status['power_data_dir_exists'] = True
                    
                    # Get recent files
                    if os.path.isdir(power_data_dir):
                        files = [f for f in os.listdir(power_data_dir) if f.endswith('.csv')]
                        if files:
                            # Sort by modification time, newest first
                            files.sort(key=lambda x: os.path.getmtime(os.path.join(power_data_dir, x)), reverse=True)
                            status['recent_files'] = files[:5]  # Get 5 most recent files
                
                return jsonify(status)
                
            except Exception as e:
                logging.error(f"Error in debug_monitor_status: {str(e)}")
                import traceback
                logging.error(traceback.format_exc())
                return jsonify({
                    'error': str(e),
                    'traceback': traceback.format_exc()
                })
        
        @self.flask_app.template_filter('timestamp')
        def format_timestamp(timestamp):
            """Format a timestamp for display."""
            from datetime import datetime
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Add new API route to get data from saved CSV files
        @self.flask_app.route('/api/saved-data/<filename>')
        def get_saved_data(filename):
            """Get CSV data for a specific file."""
            try:
                import os
                import csv
                from datetime import datetime
                
                # Determine the power_data directory path
                power_data_dir = os.path.join(os.getcwd(), 'power_data')
                if not os.path.isdir(power_data_dir):
                    power_data_dir = os.path.join(os.path.dirname(os.getcwd()), 'power_data')
                    if not os.path.isdir(power_data_dir):
                        return jsonify({'success': False, 'error': 'Power data directory not found'})
                
                # Ensure the filename is safe and points to a CSV file
                if not filename.endswith('.csv') or '..' in filename:
                    return jsonify({'success': False, 'error': 'Invalid filename'})
                
                filepath = os.path.join(power_data_dir, filename)
                if not os.path.isfile(filepath):
                    return jsonify({'success': False, 'error': 'File not found'})
                
                # Read the CSV file
                timestamps = []
                power_values = []
                
                with open(filepath, 'r', newline='') as csvfile:
                    reader = csv.reader(csvfile)
                    # Skip header if it exists
                    try:
                        header = next(reader)
                    except StopIteration:
                        return jsonify({'success': False, 'error': 'Empty file'})
                        
                    for row in reader:
                        try:
                            if len(row) >= 2:
                                # Try to parse timestamp
                                timestamp_str = row[0]
                                # Parse power value
                                power = float(row[1])
                                
                                timestamps.append(timestamp_str)
                                power_values.append(power)
                        except Exception as e:
                            continue
                
                # Calculate statistics
                if power_values:
                    min_power = min(power_values)
                    max_power = max(power_values)
                    avg_power = sum(power_values) / len(power_values)
                    
                    # Find mode (most common value, rounded to 2 decimals)
                    from collections import Counter
                    rounded_values = [round(p, 2) for p in power_values]
                    most_common = Counter(rounded_values).most_common(1)
                    mode = most_common[0][0] if most_common else None
                else:
                    min_power = max_power = avg_power = mode = 0
                
                return jsonify({
                    'success': True,
                    'filename': filename,
                    'timestamps': timestamps,
                    'power': power_values,
                    'stats': {
                        'min': min_power,
                        'max': max_power,
                        'avg': avg_power,
                        'mode': mode,
                        'count': len(power_values)
                    }
                })
            
            except Exception as e:
                import traceback, logging
                logging.error(f"Error in get_saved_data: {str(e)}")
                logging.error(traceback.format_exc())
                return jsonify({'success': False, 'error': str(e)})
        
        # Add this new route inside the setup_routes method
        @self.flask_app.route('/api/rscm/start-monitoring', methods=['POST'])
        def start_rack_monitoring():
            """Start monitoring a rack with specified interval and duration."""
            try:
                rack_name = request.form.get('rack_name')
                interval = float(request.form.get('interval', 1.0))
                duration = float(request.form.get('duration', 0))
                
                # Convert duration 0 to None for continuous monitoring
                if duration == 0:
                    duration = None
                
                logging.info(f"Starting monitoring for {rack_name} with interval={interval} and duration={duration}")
                
                # First find the rack address using the existing get_rscm_info method
                if hasattr(self.app, 'get_rscm_info'):
                    rscm_info = self.app.get_rscm_info(rack_name)
                    if not rscm_info:
                        return jsonify({
                            'success': False,
                            'message': f'Could not find rack {rack_name}'
                        })
                    
                    rack_address = rscm_info.get('address')
                    if not rack_address:
                        return jsonify({
                            'success': False,
                            'message': f'No address found for rack {rack_name}'
                        })
                        
                    # Start monitoring if monitor_tab is available
                    if hasattr(self.app, 'monitor_tab'):
                        # Try to determine which monitoring method to use
                        monitor_method = None
                        
                        # Check for different method names that might exist
                        if hasattr(self.app.monitor_tab, '_monitor_single_rack_isolated'):
                            monitor_method = self.app.monitor_tab._monitor_single_rack_isolated
                        elif hasattr(self.app.monitor_tab, 'monitor_single_rack'):
                            monitor_method = self.app.monitor_tab.monitor_single_rack
                        elif hasattr(self.app.monitor_tab, 'start_monitoring'):
                            monitor_method = self.app.monitor_tab.start_monitoring
                        
                        if monitor_method:
                            # Try to call the monitor method with explicit save parameter
                            try:
                                # Different methods might have different parameter signatures
                                # Try each possible signature
                                try:
                                    # Try with explicit save=True parameter
                                    monitor_method(
                                        rack_name=rack_name,
                                        rack_address=rack_address,
                                        interval_minutes=interval,
                                        duration_hours=duration,
                                        save=True  # Explicitly request saving
                                    )
                                except TypeError:
                                    # If that fails, try without the save parameter
                                    monitor_method(
                                        rack_name=rack_name,
                                        rack_address=rack_address,
                                        interval_minutes=interval,
                                        duration_hours=duration
                                    )
                                    
                                    # Enable saving by setting a flag if available
                                    if hasattr(self.app.monitor_tab, 'save_data'):
                                        self.app.monitor_tab.save_data = True
                                    
                                logging.info(f"Successfully started monitoring for {rack_name}")
                                
                                # Return success
                                return jsonify({
                                    'success': True,
                                    'message': f'Monitoring started for {rack_name}',
                                    'interval': interval,
                                    'duration': 'Continuous' if duration is None else f'{duration} hours'
                                })
                                
                            except Exception as e:
                                logging.error(f"Error starting monitoring: {str(e)}")
                                import traceback
                                logging.error(traceback.format_exc())
                                return jsonify({
                                    'success': False,
                                    'message': f'Error starting monitoring: {str(e)}'
                                })
                        else:
                            return jsonify({
                                'success': False,
                                'message': 'Monitoring method not found'
                            })
                    else:
                        return jsonify({
                            'success': False,
                            'message': 'Monitoring functionality not available'
                        })
                else:
                    return jsonify({
                        'success': False,
                        'message': 'Cannot retrieve rack information'
                    })
                    
            except Exception as e:
                logging.error(f"Error in start_rack_monitoring: {str(e)}")
                import traceback
                logging.error(traceback.format_exc())
                return jsonify({
                    'success': False,
                    'message': f'Error: {str(e)}'
                })
        
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