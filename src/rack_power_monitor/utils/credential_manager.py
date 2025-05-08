"""
Credential management for RSCM access.
Handles secure storage and retrieval of credentials.
"""
import os
import base64
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger("power_monitor")

class CredentialManager:
    """Manages credentials for RSCM access."""
    
    def __init__(self, app_secret=None):
        """Initialize the credential manager.
        
        Args:
            app_secret: A secret key to use for encryption
        """
        self.key = None
        self.cipher_suite = None
        self._initialize_encryption(app_secret)
    
    def _initialize_encryption(self, app_secret=None):
        """Initialize encryption with the provided or default secret."""
        try:
            # Use provided secret or create one based on machine-specific data
            if not app_secret:
                # Get or create machine-specific salt
                salt_path = os.path.join(os.path.expanduser('~'), '.rack_monitor_salt')
                if os.path.exists(salt_path):
                    with open(salt_path, 'rb') as f:
                        salt = f.read()
                else:
                    # Generate and save a salt if one doesn't exist
                    salt = os.urandom(16)
                    os.makedirs(os.path.dirname(salt_path), exist_ok=True)
                    with open(salt_path, 'wb') as f:
                        f.write(salt)
                
                # Use a hash of the machine name as a base for the key
                machine_id = os.environ.get('COMPUTERNAME', 'default_machine')
                machine_bytes = machine_id.encode('utf-8')
                
                # Derive a key using PBKDF2
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=salt,
                    iterations=100000,
                )
                self.key = base64.urlsafe_b64encode(kdf.derive(machine_bytes))
            else:
                # Use the provided app secret
                # Ensure it's the right format for Fernet
                if isinstance(app_secret, str):
                    app_secret = app_secret.encode('utf-8')
                
                # Derive a key from the app secret
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=b'rack_monitor_salt',
                    iterations=100000,
                )
                self.key = base64.urlsafe_b64encode(kdf.derive(app_secret))
                
            # Create the cipher suite for encryption/decryption
            self.cipher_suite = Fernet(self.key)
            logger.info("Credential encryption initialized")
                
        except Exception as e:
            logger.error(f"Failed to initialize encryption: {e}")
            # Fallback to a basic encryption if the more secure method fails
            self.key = base64.urlsafe_b64encode(b'rack_monitor_fallback_key_12345678901234')
            self.cipher_suite = Fernet(self.key)
    
    def encrypt_password(self, password):
        """Encrypt a password.
        
        Args:
            password: The plaintext password to encrypt
            
        Returns:
            str: The encrypted password, base64 encoded
        """
        if not password:
            return ""
            
        try:
            if isinstance(password, str):
                password = password.encode('utf-8')
                
            encrypted = self.cipher_suite.encrypt(password)
            return base64.urlsafe_b64encode(encrypted).decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to encrypt password: {e}")
            return ""
    
    def decrypt_password(self, encrypted_password):
        """Decrypt an encrypted password.
        
        Args:
            encrypted_password: The encrypted password, base64 encoded
            
        Returns:
            str: The decrypted password
        """
        if not encrypted_password:
            return ""
            
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_password)
            decrypted = self.cipher_suite.decrypt(encrypted_bytes)
            return decrypted.decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to decrypt password: {e}")
            return ""
    
    def get_rscm_credentials(self, username, encrypted_password):
        """Get RSCM credentials.
        
        Args:
            username: The username
            encrypted_password: The encrypted password
            
        Returns:
            tuple: (username, password) if successful, else (None, None)
        """
        password = self.decrypt_password(encrypted_password)
        if username and password:
            return username, password
        else:
            logger.error("No valid credentials available")
            return None, None