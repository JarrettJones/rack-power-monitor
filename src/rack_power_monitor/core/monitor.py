import asyncio
import datetime
import logging
import os
import csv
from ..utils.api_client import RedfishAPIClient

logger = logging.getLogger("power_monitor")

class RackPowerMonitor:
    """Core class for monitoring server rack power usage."""
    
    def __init__(self):
        """Initialize the power monitor."""
        self.api_client = RedfishAPIClient()
        self.monitoring_active = False
        self.racks_data = {}
        self.data_dir = None
    
    def initialize_results_folder(self, base_dir="power_data"):
        """Initialize results folder for data storage."""
        # Create a directory structure for results
        os.makedirs(base_dir, exist_ok=True)
        
        # Get timestamp for this monitoring session
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        
        # Create session-specific directory
        session_dir = os.path.join(base_dir, f"session_{timestamp}")
        os.makedirs(session_dir, exist_ok=True)
        
        self.data_dir = session_dir
        return session_dir
    
    async def monitor_all_racks(self, interval_minutes=1.0, duration_hours=None, callback=None):
        """Monitor all configured racks for a specified duration."""
        import logging
        import asyncio
        import datetime
        from ..utils.api_client import RedfishAPIClient
        import json
        
        logger = logging.getLogger("power_monitor")
        logger.info(f"Starting monitor_all_racks with interval={interval_minutes}min, duration={duration_hours}hrs")
        
        # Create a new session ID for this monitoring run to ensure new CSV files
        self.reset_session()
        
        # Add a paused attribute if it doesn't exist
        if not hasattr(self, 'paused'):
            self.paused = False
        
        # Add detailed diagnostic logging
        logger.info(f"DIAGNOSTIC: Racks configuration: {json.dumps({k: {
            'address': v['address'],
            'username_length': len(v.get('username', '')) if v.get('username') else 0,
            'password_length': len(v.get('password', '')) if v.get('password') else 0
        } for k, v in self.racks.items()})}")
        
        # Calculate interval in seconds
        interval_seconds = interval_minutes * 60
        
        # Calculate end time if duration is specified
        end_time = None
        if duration_hours:
            end_time = datetime.datetime.now() + datetime.timedelta(hours=duration_hours)
        
        # Reset stop flag
        self.stop_requested = False
        
        try:
            # Main monitoring loop
            while not self.stop_requested:
                start_time = datetime.datetime.now()
                
                # Check if monitoring is paused
                if not self.paused:
                    logger.info(f"Polling at {start_time}")
                    
                    # Check if we've exceeded the duration
                    if end_time and datetime.datetime.now() >= end_time:
                        logger.info("Monitoring duration reached")
                        break
                    
                    # Process each rack
                    for rack_name, rack_info in self.racks.items():
                        try:
                            # Get credentials
                            address = rack_info["address"]
                            username = rack_info["username"]
                            password = rack_info["password"]
                            
                            # Log that we're getting a power reading
                            logger.info(f"Getting power reading for {rack_name} ({address})...")
                            
                            # Use self to call the method
                            success, power = await self._direct_api_call(address, username, password)
                            
                            # If we got a valid power reading
                            if success and power is not None:
                                timestamp = datetime.datetime.now()
                                logger.info(f"Power reading for {rack_name}: {power:.2f}W")
                                
                                # Record the data
                                if rack_name not in self.racks_data:
                                    self.racks_data[rack_name] = []
                                self.racks_data[rack_name].append((timestamp, power))
                                
                                # Save to CSV file
                                self._save_to_csv(rack_name, timestamp, power)
                                
                                # Call the callback function if provided
                                if callback:
                                    try:
                                        callback(rack_name, timestamp, power)
                                    except Exception as callback_ex:
                                        logger.error(f"Error in callback for {rack_name}: {str(callback_ex)}")
                            else:
                                logger.warning(f"No power data returned for {rack_name}")
                                
                        except Exception as e:
                            logger.error(f"Error monitoring {rack_name}: {str(e)}")
                else:
                    logger.info(f"Monitoring is paused, skipping polling cycle at {start_time}")
                
                # Calculate time to wait until next measurement
                elapsed = (datetime.datetime.now() - start_time).total_seconds()
                wait_time = max(0, interval_seconds - elapsed)
                
                if self.stop_requested:
                    logger.info("Stop requested during monitoring loop")
                    break
                    
                # Wait for the next interval, checking periodically for stop request or pause state changes
                if wait_time > 0:
                    if not self.paused:
                        logger.info(f"Waiting {wait_time:.1f} seconds until next measurement")
                    else:
                        logger.info(f"Paused: Waiting {wait_time:.1f} seconds until next check")
                        
                    wait_chunks = min(1.0, wait_time / 10)  # Check for stop/pause every 1 second or less
                    waited = 0
                    
                    while waited < wait_time and not self.stop_requested:
                        await asyncio.sleep(min(wait_chunks, wait_time - waited))
                        waited += wait_chunks
                        
                        if self.stop_requested:
                            logger.info("Stop requested during wait period")
                            break
                
            logger.info("Monitoring loop completed")
            return True
                
        except asyncio.CancelledError:
            logger.info("Monitoring task was cancelled")
            return False
        except Exception as e:
            logger.error(f"Error in monitoring loop: {str(e)}")
            import traceback
            logger.error(f"Exception details: {traceback.format_exc()}")
            return False
        
    # Add this helper function to make direct API calls with the working authentication logic
    async def _direct_api_call(self, address, username, password):
        """Make a direct API call using the successful authentication approach from test_connection_with_power."""
        import logging
        import aiohttp
        import asyncio
        import base64
        
        logger = logging.getLogger("power_monitor")
        
        # Add diagnostic logging
        logger.info(f"DIAGNOSTIC: _direct_api_call for {address}")
        logger.info(f"DIAGNOSTIC: Username length: {len(username) if username else 0}")
        logger.info(f"DIAGNOSTIC: Password length: {len(password) if password else 0}")
        
        # Create a new session for this call
        session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(verify_ssl=False)
        )
        
        try:
            # Use ONLY this specific endpoint and port that works in tests
            endpoint = "/redfish/v1/PowerEquipment/PowerShelves/1/Oem/Microsoft/PowerMeter"
            url = f"https://{address}:8080{endpoint}"
            
            # Prepare both types of authentication
            auth = aiohttp.BasicAuth(username, password)
            basic_auth_header = f"Basic {base64.b64encode(f'{username}:{password}'.encode()).decode()}"
            
            # Log the auth header without exposing credentials completely
            masked_header = basic_auth_header[:15] + '...' + basic_auth_header[-5:] if len(basic_auth_header) > 20 else basic_auth_header
            logger.info(f"DIAGNOSTIC: Auth header: {masked_header}")
            
            headers = {
                "Authorization": basic_auth_header,
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            # Try with explicit headers first since that's working more reliably in test
            async with session.get(url, headers=headers, timeout=10, ssl=False) as headers_response:
                if headers_response.status == 200:
                    data = await headers_response.json()
                    if "TotalInputPowerInWatts" in data:
                        power_watts = data.get("TotalInputPowerInWatts")
                        logger.info(f"Power reading (headers auth): {power_watts}W")
                        return True, power_watts
                else:
                    logger.warning(f"HTTP {headers_response.status} using explicit headers")
                    
            # Try with basic auth as backup
            async with session.get(url, auth=auth, timeout=10, ssl=False) as response:
                if response.status == 200:
                    data = await response.json()
                    if "TotalInputPowerInWatts" in data:
                        power_watts = data.get("TotalInputPowerInWatts")
                        logger.info(f"Power reading (basic auth): {power_watts}W")
                        return True, power_watts
                else:
                    logger.warning(f"HTTP {response.status} using basic auth")
                    
            # If we get here, both attempts failed
            return False, None
            
        except Exception as e:
            logger.error(f"Error accessing {address}: {str(e)}")
            return False, None
        finally:
            # Always close the session
            if not session.closed:
                await session.close()
    
    async def monitor_rack(self, rack_name, interval_minutes=1.0, duration_hours=None, callback=None):
        """Monitor a specific rack.
        This is a convenience wrapper around monitor_all_racks that filters for a single rack.
        """
        # Save the original racks_data
        original_racks = self.racks_data.copy()
        
        # Filter to only the specific rack
        if rack_name in self.racks_data:
            filtered_racks = {rack_name: self.racks_data[rack_name]}
            self.racks_data = filtered_racks
            
            # Create a filtered callback that ensures the rack_name and address are passed
            def enhanced_callback(name, timestamp, power):
                if callback:
                    rack_address = original_racks[name]['address']
                    return callback(rack_name=name, rack_address=rack_address, timestamp=timestamp, power=power)
            
            try:
                # Call the main monitoring method with just this rack
                result = await self.monitor_all_racks(
                    interval_minutes=interval_minutes,
                    duration_hours=duration_hours,
                    callback=enhanced_callback
                )
                return result
            finally:
                # Restore the original racks data
                self.racks_data = original_racks
        else:
            logger.error(f"Rack {rack_name} not found for monitoring")
            return False
    
    async def _monitor_rack(self, rack_name, address, username, password, formatted_time, csv_path, callback=None):
        """Monitor a single rack and update its data."""
        try:
            # Get power reading
            power_watts = await self.api_client.get_power_reading(address, username, password)
            
            # Log the reading
            if power_watts is not None:
                logger.info(f"{formatted_time} | {rack_name} ({address}) | {power_watts} W")
            else:
                logger.error(f"{formatted_time} | {rack_name} ({address}) | ERROR")
            
            # Store data if valid
            current_time = datetime.datetime.now()
            if power_watts is not None:
                # Ensure the rack data structure has the necessary lists
                if 'timestamps' not in self.racks_data[rack_name]:
                    self.racks_data[rack_name]['timestamps'] = []
                if 'power_values' not in self.racks_data[rack_name]:
                    self.racks_data[rack_name]['power_values'] = []
                    
                self.racks_data[rack_name]['timestamps'].append(current_time)
                self.racks_data[rack_name]['power_values'].append(power_watts)
                
            # Write to CSV
            with open(csv_path, 'a', newline='', encoding='utf-8') as f:
                f.write(f"{formatted_time},{address},{power_watts if power_watts is not None else 'ERROR'}\n")
                
            # Call the callback function if provided
            if callback:
                callback(rack_name, current_time, power_watts)
                
        except Exception as e:
            logger.error(f"Error monitoring rack {rack_name} ({address}): {str(e)}")
    
    async def _wait_with_cancellation_check(self, wait_seconds):
        """Wait for the specified interval but check for cancellation."""
        chunk_size = 0.2  # Check every 0.2 seconds
        waited = 0
        
        while waited < wait_seconds and self.monitoring_active:
            await asyncio.sleep(chunk_size)
            waited += chunk_size
    
    def add_rack(self, name, address, username, password):
        """Add a rack to be monitored."""
        self.racks_data[name] = {
            'address': address,
            'username': username,
            'password': password,
            'timestamps': [],
            'power_values': []
        }
        return True
    
    def remove_rack(self, name):
        """Remove a rack from monitoring."""
        if name in self.racks_data:
            del self.racks_data[name]
            return True
        return False
    
    def start_monitoring(self):
        """Set the monitoring active flag."""
        self.monitoring_active = True
    
    def stop_monitoring(self):
        """Clear the monitoring active flag."""
        self.monitoring_active = False

    def _save_to_csv(self, rack_name, timestamp, power):
        """Save power reading to CSV file with unique session-based naming."""
        # Create the filename using rack name, date and session start time
        # This ensures each monitoring session gets its own file
        
        # If we don't have a session_id yet, create one based on start time
        if not hasattr(self, 'session_id'):
            self.session_id = timestamp.strftime("%Y%m%d_%H%M%S")
        
        # Create a unique filename for this monitoring session
        filename = f"{rack_name}_{self.session_id}.csv"
        
        # Create power_data directory if it doesn't exist
        if not hasattr(self, 'data_dir') or self.data_dir is None:
            self.data_dir = "power_data"
            
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)
        
        filepath = os.path.join(self.data_dir, filename)
        
        # Check if file exists
        file_exists = os.path.isfile(filepath)
        
        # Format timestamp for CSV
        formatted_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        
        # Open file in append mode
        with open(filepath, 'a', newline='') as f:
            writer = csv.writer(f)
            
            # Write header if new file
            if not file_exists:
                writer.writerow(["Timestamp", "Power (W)"])
            
            # Write data
            writer.writerow([formatted_time, power])
                
        logger.info(f"Saved power reading for {rack_name} to {filepath}")
        
        # Store the last saved file name for reference
        self.last_saved_file = filename
        
        return filepath

    # Add this method to the RackPowerMonitor class
    def reset_session(self):
        """Reset the session ID to create a new file for a new monitoring session."""
        import datetime
        self.session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        logger.info(f"Reset monitoring session with new ID: {self.session_id}")