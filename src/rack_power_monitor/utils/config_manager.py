import os
import json
import logging

logger = logging.getLogger("power_monitor")

class ConfigManager:
    """Manages configuration settings for the application."""
    
    def __init__(self, config_file="config/default_settings.json"):
        """Initialize the configuration manager."""
        self.config_file = config_file
        self.default_config = {
            'data_dir': 'power_data',
            'enable_logging': True,
            'chart_theme': 'default',
            'refresh_interval': 1.0,
            'enable_alerts': False,
            'alert_threshold': 1000
        }
    
    def load_settings(self):
        """Load settings from configuration file."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    settings = json.load(f)
                logger.info(f"Settings loaded from {self.config_file}")
                return settings
            else:
                # If no config file exists, create one with defaults
                self.save_settings(self.default_config)
                logger.info(f"Created default settings file at {self.config_file}")
                return self.default_config
                
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            return self.default_config
    
    def save_settings(self, settings):
        """Save settings to configuration file."""
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            with open(self.config_file, 'w') as f:
                json.dump(settings, f, indent=4)
                
            logger.info(f"Settings saved to {self.config_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            return False