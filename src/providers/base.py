from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from models.events import PREvent, ReviewComment


class ProviderAdapter(ABC):
    """Abstract base class for provider-specific adapters.
    
    All provider adapters (GitHub, GitLab, Bitbucket) must inherit from this class
    and implement the abstract methods.
    """
    
    def __init__(self, webhook_secret: str, api_token: Optional[str] = None):
        self.webhook_secret = webhook_secret
        self.api_token = api_token
    
    @abstractmethod
    def parse_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> Optional[PREvent]:
        """Parse webhook payload and return normalized PREvent.
        
        Args:
            payload: The webhook payload as dictionary
            headers: The request headers
            
        Returns:
            PREvent if the payload is relevant, None otherwise
        """
        pass
    
    @abstractmethod
    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify webhook signature to ensure authenticity.
        
        Args:
            payload: Raw request body
            signature: Signature from request header
            
        Returns:
            True if signature is valid, False otherwise
        """
        pass
    
    @abstractmethod
    async def fetch_pr(self, event: PREvent) -> Dict[str, Any]:
        """Fetch PR details including diff.
        
        Args:
            event: The normalized PR event
            
        Returns:
            Dictionary containing PR diff and metadata
        """
        pass
    
    @abstractmethod
    async def post_comment(
        self, 
        event: PREvent, 
        comments: List[ReviewComment],
        summary: str = ""
    ) -> bool:
        """Post review comments to the PR.
        
        Args:
            event: The normalized PR event
            comments: List of review comments to post
            summary: Overall review summary
            
        Returns:
            True if comments were posted successfully
        """
        pass
    
    @abstractmethod
    def get_event_type(self, headers: Dict[str, str]) -> Optional[str]:
        """Extract event type from headers.
        
        Args:
            headers: Request headers
            
        Returns:
            Event type string or None
        """
        pass
