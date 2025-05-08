"""
Azure Key Vault integration for securely retrieving credentials.
"""
import logging
import os
from azure.identity import DefaultAzureCredential, ClientSecretCredential, ManagedIdentityCredential, AzureCliCredential
from azure.keyvault.secrets import SecretClient
from azure.core.exceptions import ClientAuthenticationError

logger = logging.getLogger("power_monitor")

class AzureCredentialManager:
    """Manages Azure authentication and credential retrieval."""
    
    def __init__(self, vault_url="https://wus3-dev-rm-kv-001.vault.azure.net/", auth_method="Default"):
        """Initialize the credential manager.
        
        Args:
            vault_url: The URL of the Azure Key Vault
            auth_method: The authentication method to use
        """
        self.vault_url = vault_url
        self.auth_method = auth_method
        self.secret_client = None
        self.credential = None
        self.fallback_password = None
        
        # Check for environment variable with fallback password
        if 'RSCM_PASSWORD' in os.environ:
            self.fallback_password = os.environ['RSCM_PASSWORD']
            logger.info("Found RSCM fallback password in environment variables")
    
    def initialize(self):
        """Initialize the Azure credential and secret client."""
        try:
            # Get Azure credential based on auth method
            if self.auth_method == "Environment":
                from azure.identity import EnvironmentCredential
                self.credential = EnvironmentCredential()
            elif self.auth_method == "Managed Identity":
                self.credential = ManagedIdentityCredential()
            elif self.auth_method == "CLI":
                self.credential = AzureCliCredential()
            elif self.auth_method == "Visual Studio":
                from azure.identity import VisualStudioCodeCredential
                self.credential = VisualStudioCodeCredential()
            else:
                # Default uses all available methods
                self.credential = DefaultAzureCredential()
            
            # Create the secret client
            self.secret_client = SecretClient(
                vault_url=self.vault_url, 
                credential=self.credential
            )
            
            # Test the connection by retrieving a simple property
            vault_props = self.secret_client.get_secret_properties("SCHIE-Lab-Rack-Manager")
            if vault_props:
                logger.info("Azure credential manager initialized successfully")
                return True
                
        except Exception as e:
            logger.warning(f"Failed to initialize Azure credential manager: {e}")
            return False
    
    def get_rscm_credentials(self, secret_name="SCHIE-Lab-Rack-Manager", username="root", fallback=None):
        """Get RSCM credentials from Azure Key Vault.
        
        Args:
            secret_name: The name of the secret in Azure Key Vault
            username: The default username to use
            fallback: Optional fallback password if Azure auth fails
            
        Returns:
            tuple: (username, password) if successful, else (None, None)
        """
        password = None
        
        # Try Azure Key Vault first
        try:
            if not self.secret_client:
                if not self.initialize():
                    logger.warning("Azure Key Vault authentication failed, trying fallback")
                else:
                    # Get the secret from Azure Key Vault
                    secret = self.secret_client.get_secret(secret_name)
                    password = secret.value
                    logger.info("Retrieved password from Azure Key Vault")
            else:
                # Get the secret from Azure Key Vault
                secret = self.secret_client.get_secret(secret_name)
                password = secret.value
                logger.info("Retrieved password from Azure Key Vault")
                
        except Exception as e:
            logger.warning(f"Failed to get password from Azure Key Vault: {e}")
        
        # If Azure failed, try fallback options
        if not password:
            # First try the provided fallback
            if fallback:
                password = fallback
                logger.info("Using provided fallback password")
            # Then try environment variable
            elif self.fallback_password:
                password = self.fallback_password
                logger.info("Using environment variable fallback password")
            else:
                logger.error("No password available from Azure or fallback")
                return None, None
            
        return username, password