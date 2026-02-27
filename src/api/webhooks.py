from fastapi import APIRouter, Request, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from typing import Dict, Any
import logging

from providers.factory import ProviderFactory
from models.events import PREvent

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webhooks"])


async def get_raw_body(request: Request) -> bytes:
    """Extract raw request body for signature verification."""
    return await request.body()


@router.post(
    "/webhooks/github",
    status_code=status.HTTP_202_ACCEPTED,
    summary="GitHub webhook endpoint",
    description="Receive and process GitHub pull request webhooks"
)
async def github_webhook(
    request: Request,
    raw_body: bytes = Depends(get_raw_body)
) -> Dict[str, str]:
    """Handle GitHub webhook events."""
    try:
        payload = await request.json()
        headers = dict(request.headers)
        
        # Get signature from header
        signature = headers.get("x-hub-signature-256", "")
        
        # Create adapter and verify
        adapter = ProviderFactory.create("github")
        
        if not adapter.verify_signature(raw_body, signature):
            logger.warning("Invalid GitHub webhook signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature"
            )
        
        # Parse webhook event
        event = adapter.parse_webhook(payload, headers)
        
        if event is None:
            logger.debug("Event filtered out - not a relevant PR event")
            return {"status": "ignored", "message": "Event not relevant"}
        
        logger.info(f"Received GitHub PR event: {event.repo_owner}/{event.repo_name}#{event.pr_number}")
        
        # TODO: Publish to Pub/Sub for async processing
        # await publish_review_request(event)
        
        return {"status": "accepted", "event_id": f"{event.provider}:{event.pr_number}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing GitHub webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post(
    "/webhooks/gitlab",
    status_code=status.HTTP_202_ACCEPTED,
    summary="GitLab webhook endpoint",
    description="Receive and process GitLab merge request webhooks"
)
async def gitlab_webhook(
    request: Request,
    raw_body: bytes = Depends(get_raw_body)
) -> Dict[str, str]:
    """Handle GitLab webhook events."""
    try:
        payload = await request.json()
        headers = dict(request.headers)
        
        # Get signature/token from header
        signature = headers.get("x-gitlab-token", "")
        
        # Create adapter and verify
        adapter = ProviderFactory.create("gitlab")
        
        if not adapter.verify_signature(raw_body, signature):
            logger.warning("Invalid GitLab webhook signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature"
            )
        
        # Parse webhook event
        event = adapter.parse_webhook(payload, headers)
        
        if event is None:
            logger.debug("Event filtered out - not a relevant MR event")
            return {"status": "ignored", "message": "Event not relevant"}
        
        logger.info(f"Received GitLab MR event: {event.repo_owner}/{event.repo_name}!{event.pr_number}")
        
        # TODO: Publish to Pub/Sub for async processing
        
        return {"status": "accepted", "event_id": f"{event.provider}:{event.pr_number}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing GitLab webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post(
    "/webhooks/bitbucket",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Bitbucket webhook endpoint",
    description="Receive and process Bitbucket pull request webhooks"
)
async def bitbucket_webhook(
    request: Request,
    raw_body: bytes = Depends(get_raw_body)
) -> Dict[str, str]:
    """Handle Bitbucket webhook events."""
    try:
        payload = await request.json()
        headers = dict(request.headers)
        
        # Bitbucket doesn't always use signatures, use event key for validation
        signature = headers.get("x-hook-uuid", "")
        
        # Create adapter and verify
        adapter = ProviderFactory.create("bitbucket")
        
        if not adapter.verify_signature(raw_body, signature):
            logger.warning("Invalid Bitbucket webhook signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature"
            )
        
        # Parse webhook event
        event = adapter.parse_webhook(payload, headers)
        
        if event is None:
            logger.debug("Event filtered out - not a relevant PR event")
            return {"status": "ignored", "message": "Event not relevant"}
        
        logger.info(f"Received Bitbucket PR event: {event.repo_owner}/{event.repo_name}#{event.pr_number}")
        
        # TODO: Publish to Pub/Sub for async processing
        
        return {"status": "accepted", "event_id": f"{event.provider}:{event.pr_number}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Bitbucket webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
