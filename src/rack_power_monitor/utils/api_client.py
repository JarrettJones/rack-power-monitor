import aiohttp
import logging
import ssl
import asyncio
from datetime import datetime

logger = logging.getLogger("power_monitor")

class RedfishAPIClient:
    """Client for interacting with the Redfish API to monitor server power consumption."""
    
    def __init__(self):
        """Initialize the API client."""
        self.session = None
    
    async def create_session(self):
        """Create an aiohttp client session."""
        if self.session is None or self.session.closed:
            # Create a session that ignores SSL certificate validation
            self.session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(verify_ssl=False)
            )
        return self.session
    
    async def close_session(self):
        """Close the client session."""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def get_power_reading(self, address, username, password):
        """Get power reading from RSCM via Redfish API."""
        import logging
        import aiohttp
        import asyncio
        import base64
        logger = logging.getLogger("power_monitor")
        
        logger.info(f"Getting power reading for {address}")
        
        # Create a new session for this call
        session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(verify_ssl=False)
        )
        logger.info(f"Created new HTTP session for {address}")
        
        try:
            # Use ONLY the correct endpoint with port 8080
            endpoint = "/redfish/v1/PowerEquipment/PowerShelves/1/Oem/Microsoft/PowerMeter"
            
            # Prepare authentication headers - try both methods
            auth = aiohttp.BasicAuth(username, password)
            basic_auth_header = f"Basic {base64.b64encode(f'{username}:{password}'.encode()).decode()}"
            headers = {
                "Authorization": basic_auth_header,
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            # Try HTTPS on port 8080 first
            url = f"https://{address}:8080{endpoint}"
            try:
                logger.info(f"Trying endpoint: {url}")
                
                # First try with aiohttp's built-in auth
                async with session.get(url, auth=auth, timeout=10, ssl=False) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Extract the TotalInputPowerInWatts field
                        if "TotalInputPowerInWatts" in data:
                            power_watts = data.get("TotalInputPowerInWatts")
                            logger.info(f"Power reading from {url}: {power_watts}W")
                            return power_watts
                        else:
                            logger.warning(f"TotalInputPowerInWatts field not found in response from {url}")
                    elif response.status == 401:
                        logger.warning(f"Authentication failed (401) with built-in auth, trying explicit headers")
                        
                        # Try again with explicit auth headers
                        async with session.get(url, headers=headers, timeout=10, ssl=False) as headers_response:
                            if headers_response.status == 200:
                                data = await headers_response.json()
                                if "TotalInputPowerInWatts" in data:
                                    power_watts = data.get("TotalInputPowerInWatts")
                                    logger.info(f"Power reading from {url} (with headers): {power_watts}W")
                                    return power_watts
                            else:
                                logger.warning(f"HTTP {headers_response.status} from {url} with explicit headers")
                    else:
                        logger.warning(f"HTTP {response.status} from {url}")
            except asyncio.TimeoutError:
                logger.warning(f"Timeout accessing {url}")
            except Exception as e:
                logger.warning(f"Error accessing {url}: {e}")
            
            # If HTTPS fails, try HTTP
            url = f"http://{address}:8080{endpoint}"
            try:
                logger.info(f"Trying endpoint: {url}")
                # Try with built-in auth
                async with session.get(url, auth=auth, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Extract the TotalInputPowerInWatts field
                        if "TotalInputPowerInWatts" in data:
                            power_watts = data.get("TotalInputPowerInWatts")
                            logger.info(f"Power reading from {url}: {power_watts}W")
                            return power_watts
                    elif response.status == 401:
                        # Try again with explicit auth headers
                        async with session.get(url, headers=headers, timeout=10) as headers_response:
                            if headers_response.status == 200:
                                data = await headers_response.json()
                                if "TotalInputPowerInWatts" in data:
                                    power_watts = data.get("TotalInputPowerInWatts")
                                    logger.info(f"Power reading from {url} (with headers): {power_watts}W")
                                    return power_watts
                            else:
                                logger.warning(f"HTTP {headers_response.status} from {url} with explicit headers")
                    else:
                        logger.warning(f"HTTP {response.status} from {url}")
            except Exception as e:
                logger.warning(f"Error accessing {url}: {e}")
            
            logger.error(f"Failed to get power reading from {address} using endpoint {endpoint}")
            return None
        finally:
            # Always close the session
            if not session.closed:
                await session.close()
                logger.info(f"Closed HTTP session for {address}")

    async def test_connection(self, address, username, password):
        """Test connection to RSCM by first pinging it, then attempting to get a power reading."""
        try:
            # Call the more detailed method and just return the success status
            success, _ = await self.test_connection_with_power(address, username, password)
            return success
        except Exception as e:
            import logging
            logger = logging.getLogger("power_monitor")
            logger.error(f"Error in test_connection: {str(e)}")
            return False
        finally:
            # Important: Close the session properly to avoid the "Unclosed client session" warning
            if hasattr(self, 'session') and self.session and not self.session.closed:
                try:
                    await self.session.close()
                    logger.info(f"Closed HTTP session for {address}")
                except Exception:
                    pass

    async def test_connection_with_power(self, address, username, password):
        """Test connection to RSCM by first pinging it, then attempting to get a power reading."""
        import logging
        import subprocess
        import asyncio
        logger = logging.getLogger("power_monitor")
        
        # When called during monitoring, we can skip the ping test to improve performance
        # This check determines if we're in a test or monitoring context
        import inspect
        caller_frame = inspect.currentframe().f_back
        caller_function = caller_frame.f_code.co_name if caller_frame else "unknown"
        
        is_monitoring = caller_function == "monitor_all_racks"
        
        if not is_monitoring:
            # Add detailed logging only during a real test
            logger.info(f"START test_connection for {address}")
            
            # First check if the RSCM is reachable via ping
            logger.info(f"Pinging {address} to verify network connectivity...")
            
            ping_success = False
            
            # Run ping command based on platform
            try:
                # Use the subprocess module directly
                import platform
                if platform.system().lower() == "windows":
                    # Windows ping command with 2 packets and 1 second timeout
                    cmd = ["ping", "-n", "2", "-w", "1000", address]
                    logger.info(f"Running ping command: {' '.join(cmd)}")
                    
                    # Use subprocess.run with timeout
                    result = subprocess.run(
                        cmd, 
                        capture_output=True,
                        text=True,
                        timeout=5  # 5 seconds total timeout for the ping process
                    )
                    ping_success = (result.returncode == 0)
                    
                    if ping_success:
                        logger.info(f"Ping successful: {result.stdout.strip()}")
                    else:
                        logger.error(f"Ping failed: {result.stdout.strip()}")
                else:
                    # Unix ping command with 2 packets and 1 second timeout
                    cmd = ["ping", "-c", "2", "-W", "1", address]
                    logger.info(f"Running ping command: {' '.join(cmd)}")
                    
                    # Use subprocess.run with timeout
                    result = subprocess.run(
                        cmd, 
                        capture_output=True,
                        text=True,
                        timeout=5  # 5 seconds total timeout for the ping process
                    )
                    ping_success = (result.returncode == 0)
                    
                    if ping_success:
                        logger.info(f"Ping successful: {result.stdout.strip()}")
                    else:
                        logger.error(f"Ping failed: {result.stdout.strip()}")
                        
            except subprocess.TimeoutExpired:
                logger.error(f"Ping command timed out after 5 seconds")
            except Exception as e:
                logger.error(f"Error running ping: {str(e)}")
            
            # Continue even if ping fails - API might still be reachable
            if ping_success:
                logger.info(f"Ping to {address} was successful, proceeding with API test")
            else:
                logger.warning(f"Ping to {address} failed, but still trying API connection")
        
        # Now attempt to get power reading via the API
        if not is_monitoring:
            logger.info(f"Testing API connection to {address}...")
        
        try:
            # Create this special URL directly - don't use the get_power_reading code path
            # This avoids the authentication issues that happen in monitoring
            import aiohttp
            import base64
            
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
                headers = {
                    "Authorization": basic_auth_header,
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
                
                # Try with basic auth first
                async with session.get(url, auth=auth, timeout=10, ssl=False) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Extract the TotalInputPowerInWatts field
                        if "TotalInputPowerInWatts" in data:
                            power_watts = data.get("TotalInputPowerInWatts")
                            logger.info(f"Power reading from {url}: {power_watts}W")
                            return True, power_watts
                        else:
                            logger.warning(f"TotalInputPowerInWatts field not found in response")
                    else:
                        logger.warning(f"HTTP {response.status} from {url} with basic auth")
                        
                        # Try with explicit headers as fallback
                        async with session.get(url, headers=headers, timeout=10, ssl=False) as headers_response:
                            if headers_response.status == 200:
                                data = await headers_response.json()
                                if "TotalInputPowerInWatts" in data:
                                    power_watts = data.get("TotalInputPowerInWatts")
                                    logger.info(f"Power reading from {url} (with headers): {power_watts}W")
                                    return True, power_watts
                            else:
                                logger.warning(f"HTTP {headers_response.status} from {url} with explicit headers")
                                
                # If we get here, both attempts failed
                if not is_monitoring:
                    logger.error(f"API test FAILED for {address}: No power reading returned")
                return False, None
                
            finally:
                # Always close the session
                if not session.closed:
                    await session.close()
                    if not is_monitoring:
                        logger.info(f"Closed HTTP session for {address}")
                        
        except Exception as e:
            error_msg = str(e) if str(e) else "Unknown error occurred"
            if not is_monitoring:
                logger.error(f"Error in API test: {error_msg}")
            return False, None

# Keep the original APIClient for compatibility, but mark it as deprecated
class APIClient:
    """Generic API client (deprecated, use RedfishAPIClient instead)."""
    
    def __init__(self, base_url):
        """Initialize with base URL."""
        self.base_url = base_url
        import warnings
        warnings.warn("APIClient is deprecated, use RedfishAPIClient instead", DeprecationWarning)

    def get_data(self, endpoint):
        """Get data from the specified endpoint."""
        import requests
        response = requests.get(f"{self.base_url}/{endpoint}")
        response.raise_for_status()
        return response.json()

    def post_data(self, endpoint, data):
        """Post data to the specified endpoint."""
        import requests
        response = requests.post(f"{self.base_url}/{endpoint}", json=data)
        response.raise_for_status()
        return response.json()