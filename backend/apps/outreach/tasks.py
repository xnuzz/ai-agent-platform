from celery import shared_task

from apps.common.enums import CampaignStatus


@shared_task(name="outreach.send_campaign_batch")
def send_campaign_batch(campaign_id: str) -> dict:
    from .services import run_campaign_batch

    return run_campaign_batch(campaign_id)


@shared_task(name="outreach.resume_active_campaigns")
def resume_active_campaigns() -> int:
    """Picks up ACTIVE campaigns that stopped on the daily send limit."""
    from .models import Campaign

    ids = list(Campaign.objects.filter(status=CampaignStatus.ACTIVE, workspace__is_active=True)
               .values_list("id", flat=True))
    for cid in ids:
        send_campaign_batch.delay(str(cid))
    return len(ids)
