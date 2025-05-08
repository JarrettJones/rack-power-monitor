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
            """Home page showing all monitored racks."""
            rack_list = []
            if hasattr(self.app, 'monitor_tab'):
                for item_id in self.app.monitor_tab.rscm_tree.get_children():
                    item = self.app.monitor_tab.rscm_tree.item(item_id)
                    rack_list.append({
                        'name': item['values'][0],
                        'address': item['values'][1],
                        'status': item['values'][2]
                    })
            return render_template('index.html', racks=rack_list)
            
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