import os
import csv
import pandas as pd
import logging
import datetime
from pathlib import Path

logger = logging.getLogger("power_monitor")

class DataManager:
    """Manages data storage and retrieval for power monitoring."""
    
    def __init__(self, base_dir="power_data"):
        """Initialize the data manager with a base directory."""
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
    
    def create_session_folder(self):
        """Create a new session folder for storing monitoring data."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        session_dir = os.path.join(self.base_dir, f"session_{timestamp}")
        os.makedirs(session_dir, exist_ok=True)
        return session_dir
    
    def create_csv_file(self, folder, rack_name):
        """Create a new CSV file for storing rack power data."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"PowerMonitoring-{rack_name}-{timestamp}.csv"
        filepath = os.path.join(folder, filename)
        
        # Create file with headers
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            f.write("Timestamp,RSCM_Address,PowerWatts\n")
        
        return filepath
    
    def append_power_reading(self, filepath, timestamp, rscm_address, power_watts):
        """Append a power reading to the CSV file."""
        try:
            with open(filepath, 'a', newline='', encoding='utf-8') as f:
                f.write(f"{timestamp},{rscm_address},{power_watts}\n")
            return True
        except Exception as e:
            logger.error(f"Error writing to {filepath}: {e}")
            return False
    
    def load_csv_data(self, filepath):
        """Load power data from a CSV file into a DataFrame."""
        try:
            if not os.path.exists(filepath):
                logger.error(f"File does not exist: {filepath}")
                return pd.DataFrame()
                
            df = pd.read_csv(filepath)
            
            # Convert timestamp to datetime
            df['Timestamp'] = pd.to_datetime(df['Timestamp'])
            
            return df
        except Exception as e:
            logger.error(f"Error loading data from {filepath}: {e}")
            return pd.DataFrame()
    
    def find_session_folders(self):
        """Find all session folders in the base directory."""
        try:
            sessions = []
            for item in os.listdir(self.base_dir):
                if item.startswith("session_") and os.path.isdir(os.path.join(self.base_dir, item)):
                    sessions.append(os.path.join(self.base_dir, item))
            return sessions
        except Exception as e:
            logger.error(f"Error finding session folders: {e}")
            return []
    
    def find_monitoring_files(self, session_folder=None):
        """Find all monitoring files in the given session folder or all sessions."""
        try:
            files = []
            
            # If no specific session folder is provided, search all sessions
            if session_folder is None:
                session_folders = self.find_session_folders()
                for folder in session_folders:
                    files.extend(self._find_csv_files(folder))
            else:
                files = self._find_csv_files(session_folder)
                
            return files
        except Exception as e:
            logger.error(f"Error finding monitoring files: {e}")
            return []
    
    def _find_csv_files(self, folder):
        """Find all CSV files in a folder that match the monitoring pattern."""
        files = []
        for item in os.listdir(folder):
            if item.startswith("PowerMonitoring-") and item.endswith(".csv"):
                files.append(os.path.join(folder, item))
        return files
    
    def get_rack_name_from_file(self, filepath):
        """Extract rack name from the file path."""
        try:
            filename = os.path.basename(filepath)
            # Format: PowerMonitoring-{rack_name}-{timestamp}.csv
            parts = filename.split('-')
            if len(parts) >= 2:
                return parts[1]
            return "Unknown"
        except:
            return "Unknown"
    
    def get_monitoring_sessions_info(self):
        """Get information about all monitoring sessions."""
        sessions = []
        session_folders = self.find_session_folders()
        
        for folder in session_folders:
            folder_name = os.path.basename(folder)
            timestamp_str = folder_name.replace("session_", "")
            try:
                timestamp = datetime.datetime.strptime(timestamp_str, "%Y%m%d-%H%M%S")
                files = self._find_csv_files(folder)
                
                # Get unique rack names in this session
                rack_names = set()
                for file in files:
                    rack_names.add(self.get_rack_name_from_file(file))
                
                sessions.append({
                    'path': folder,
                    'timestamp': timestamp,
                    'rack_count': len(rack_names),
                    'file_count': len(files),
                    'racks': list(rack_names)
                })
            except:
                # Skip sessions with invalid format
                continue
        
        # Sort by timestamp (newest first)
        return sorted(sessions, key=lambda x: x['timestamp'], reverse=True)